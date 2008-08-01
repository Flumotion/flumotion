# -*- Mode: Python -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# Flumotion - a streaming media server
# Copyright (C) 2004,2005,2006,2007 Fluendo, S.L. (www.fluendo.com).
# All rights reserved.

# This file may be distributed and/or modified under the terms of
# the GNU General Public License version 2 as published by
# the Free Software Foundation.
# This file is distributed without any warranty; without even the implied
# warranty of merchantability or fitness for a particular purpose.
# See "LICENSE.GPL" in the source distribution for more information.

# Licensees having purchased or holding a valid Flumotion Advanced
# Streaming Server license may use this file in accordance with the
# Flumotion Advanced Streaming Server Commercial License Agreement.
# See "LICENSE.Flumotion" in the source distribution for more information.

# Headers in this file shall remain intact.

"""
Base class and implementation for bouncer components, who perform
authentication services for other components.

Bouncers receive keycards, defined in L{flumotion.common.keycards}, and
then authenticate them.

Passing a keycard over a PB connection will copy all of the keycard's
attributes to a remote side, so that bouncer authentication can be
coupled with PB. Bouncer implementations have to make sure that they
never store sensitive data as an attribute on a keycard.

Keycards have three states: REQUESTING, AUTHENTICATED, and REFUSED. When
a keycard is first passed to a bouncer, it has the state REQUESTING.
Bouncers should never read the 'state' attribute on a keycard for any
authentication-related purpose, since it comes from the remote side.
Typically, a bouncer will only set the 'state' attribute to
AUTHENTICATED or REFUSED once it has the information to make such a
decision.

Authentication of keycards is performed in the authenticate() method,
which takes a keycard as an argument. The Bouncer base class'
implementation of this method will perform some common checks (e.g., is
the bouncer enabled, is the keycard of the correct type), and then
dispatch to the do_authenticate method, which is expected to be
overridden by subclasses.

Implementations of do_authenticate should eventually return a keycard
with the state AUTHENTICATED or REFUSED. It is acceptable for this
method to return either a keycard or a deferred that will eventually
return a keycard.

FIXME: Currently, a return value of 'None' is treated as rejecting the
keycard. This is unintuitive.

Challenge-response authentication may be implemented in
do_authenticate(), by returning a keycard still in the state REQUESTING
but with extra attributes annotating the keycard. The remote side would
then be expected to set a response on the card, resubmit, at which point
authentication could be performed. The exact protocol for this depends
on the particular keycard class and set of bouncers that can
authenticate that keycard class.

It is expected that a bouncer implementation keeps references on the
currently active set of authenticated keycards. These keycards can then
be revoked at any time by the bouncer, which will be effected through an
'expireKeycard' call. When the code that requested the keycard detects
that the keycard is no longer necessary, it should notify the bouncer
via calling 'removeKeycardId'.

The above process is leak-prone, however; if for whatever reason, the
remote side is unable to remove the keycard, the keycard will never be
removed from the bouncer's state. For that reason there is a more robust
method: if the keycard has a 'ttl' attribute, then it will be expired
automatically after 'keycard.ttl' seconds have passed. The remote side
is then responsible for periodically telling the bouncer which keycards
are still valid via the 'keepAlive' call, which resets the TTL on the
given set of keycards.

Note that with automatic expiry via the TTL attribute, it is still
preferred, albeit not strictly necessary, that callers of authenticate()
call removeKeycardId when the keycard is no longer used.
"""

import md5
import random
import time

from twisted.internet import defer, reactor

from flumotion.common import interfaces, keycards, errors
from flumotion.common.poller import Poller
from flumotion.common.componentui import WorkerComponentUIState

from flumotion.component import component
from flumotion.twisted import flavors, credentials

__all__ = ['Bouncer']
__version__ = "$Rev$"


class BouncerMedium(component.BaseComponentMedium):

    logCategory = 'bouncermedium'
    def remote_authenticate(self, keycard):
        """
        Authenticates the given keycard.

        @type  keycard: L{flumotion.common.keycards.Keycard}
        """
        return self.comp.authenticate(keycard)

    def remote_keepAlive(self, issuerName, ttl):
        """
        Resets the expiry timeout for keycards issued by issuerName.

        @param issuerName: the issuer for which keycards should be kept
                           alive; that is to say, keycards with the
                           attribute 'issuerName' set to this value will
                           have their ttl values reset.
        @type  issuerName: str
        @param ttl: the new expiry timeout
        @type  ttl: number
        """
        return self.comp.keepAlive(issuerName, ttl)

    def remote_removeKeycardId(self, keycardId):
        try:
            self.comp.removeKeycardId(keycardId)
        # FIXME: at least have an exception name please
        except KeyError:
            self.warning('Could not remove keycard id %s' % keycardId)

    def remote_expireKeycardId(self, keycardId):
        """
        Called by bouncer views to expire keycards.
        """
        return self.comp.expireKeycardId(keycardId)

    def remote_setEnabled(self, enabled):
        return self.comp.setEnabled(enabled)

    def remote_getEnabled(self):
        return self.comp.getEnabled()

class Bouncer(component.BaseComponent):
    """
    I am the base class for all bouncers.

    @cvar keycardClasses: tuple of all classes of keycards this bouncer can
                          authenticate, in order of preference
    @type keycardClasses: tuple of L{flumotion.common.keycards.Keycard}
                          class objects
    """
    keycardClasses = ()
    componentMediumClass = BouncerMedium
    logCategory = 'bouncer'

    KEYCARD_EXPIRE_INTERVAL = 2 * 60 # expire every 2 minutes

    def init(self):
        self._idCounter = 0
        self._idFormat = time.strftime('%Y%m%d%H%M%S-%%d')
        self._keycards = {} # keycard id -> Keycard
        self._keycardDatas = {} # keycard id -> data in uiState
        self.uiState.addListKey('keycards')

        self._expirer = Poller(self._expire,
                               self.KEYCARD_EXPIRE_INTERVAL,
                               start=False)
        self.enabled = True

    def setDomain(self, name):
        self.domain = name

    def getDomain(self):
        return self.domain

    def typeAllowed(self, keycard):
        """
        Verify if the keycard is an instance of a Keycard class specified
        in the bouncer's keycardClasses variable.
        """
        return isinstance(keycard, self.keycardClasses)

    def setEnabled(self, enabled):
        if not enabled and self.enabled:
            # If we were enabled and are being set to disabled, eject the warp
            # core^w^w^w^wexpire all existing keycards
            self.expireAllKeycards()
            self._expirer.stop()

        self.enabled = enabled

    def getEnabled(self):
        return self.enabled

    def do_stop(self):
        self.setEnabled(False)
        return defer.succeed(True)

    def _expire(self):
        for k in self._keycards.values():
            if hasattr(k, 'ttl'):
                k.ttl -= self._expirer.timeout
                if k.ttl <= 0:
                    self.expireKeycardId(k.id)

    def authenticate(self, keycard):
        if not self.typeAllowed(keycard):
            self.warning('keycard %r is not an allowed keycard class', keycard)
            return None

        if self.enabled:
            if not self._expirer.running and hasattr(keycard, 'ttl'):
                self.debug('installing keycard timeout poller')
                self._expirer.start()
            return defer.maybeDeferred(self.do_authenticate, keycard)
        else:
            self.debug("Bouncer disabled, refusing authentication")
            return None

    def do_authenticate(self, keycard):
        """
        Must be overridden by subclasses.

        Authenticate the given keycard.
        Return the keycard with state AUTHENTICATED to authenticate,
        with state REQUESTING to continue the authentication process,
        or None to deny the keycard, or a deferred which should have the same
        eventual value.
        """
        raise NotImplementedError("authenticate not overridden")

    def hasKeycard(self, keycard):
        return keycard in self._keycards.values()

    def generateKeycardId(self):
        # FIXME: what if it already had one ?
        # FIXME: deal with wraparound ?
        keycardId = self._idFormat % self._idCounter
        self._idCounter += 1
        return keycardId

    def addKeycard(self, keycard):
        # give keycard an id and store it in our hash
        if keycard.id in self._keycards:
            # already in there
            return

        keycardId = self.generateKeycardId()
        keycard.id = keycardId

        if hasattr(keycard, 'ttl') and keycard.ttl <= 0:
            self.log('immediately expiring keycard %r', keycard)
            return

        self._keycards[keycardId] = keycard
        data = keycard.getData()
        self._keycardDatas[keycardId] = data

        self.uiState.append('keycards', data)
        self.debug("added keycard with id %s, ttl %r", keycard.id,
                   getattr(keycard, 'ttl', None))

    def removeKeycard(self, keycard):
        if not keycard.id in self._keycards:
            raise KeyError

        del self._keycards[keycard.id]

        data = self._keycardDatas[keycard.id]
        self.uiState.remove('keycards', data)
        del self._keycardDatas[keycard.id]
        self.info("removed keycard with id %s" % keycard.id)

    def removeKeycardId(self, keycardId):
        self.debug("removing keycard with id %s" % keycardId)
        if not keycardId in self._keycards:
            raise KeyError

        keycard = self._keycards[keycardId]
        self.removeKeycard(keycard)

    def keepAlive(self, issuerName, ttl):
        for k in self._keycards.itervalues():
            if hasattr(k, 'issuerName') and k.issuerName == issuerName:
                k.ttl = ttl

    def expireAllKeycards(self):
        return defer.DeferredList(
            [self.expireKeycardId(keycardId)
                for keycardId in self._keycards.keys()])

    def expireKeycardId(self, keycardId):
        self.log("expiring keycard with id %r", keycardId)
        if not keycardId in self._keycards:
            raise KeyError

        keycard = self._keycards[keycardId]
        self.removeKeycardId(keycardId)

        if self.medium:
            return self.medium.callRemote('expireKeycard',
                                          keycard.requesterId, keycard.id)
        else:
            return defer.succeed(None)

class TrivialBouncer(Bouncer):
    """
    A very trivial bouncer implementation.

    Useful as a concrete bouncer class for which all users are
    accepted whenever the bouncer is enabled.
    """
    keycardClasses = (keycards.KeycardGeneric, )

    def do_authenticate(self, keycard):
        self.addKeycard(keycard)
        keycard.state = keycards.AUTHENTICATED

        return keycard

class ChallengeResponseBouncer(Bouncer):
    """
    A base class for Challenge-Response bouncers
    """

    challengeResponseClasses = ()

    def init(self):
        self._checker = None
        self._challenges = {}
        self._db = {}

    def setChecker(self, checker):
        self._checker = checker

    def addUser(self, user, salt, *args):
        self._db[user] = salt
        self._checker.addUser(user, *args)

    def _requestAvatarIdCallback(self, PossibleAvatarId, keycard):
        # authenticated, so return the keycard with state authenticated
        keycard.state = keycards.AUTHENTICATED
        self.addKeycard(keycard)
        if not keycard.avatarId:
            keycard.avatarId = PossibleAvatarId
        self.info('authenticated login of "%s"' % keycard.avatarId)
        self.debug('keycard %r authenticated, id %s, avatarId %s' % (
            keycard, keycard.id, keycard.avatarId))

        return keycard

    def _requestAvatarIdErrback(self, failure, keycard):
        failure.trap(errors.NotAuthenticatedError)
        # FIXME: we want to make sure the "None" we return is returned
        # as coming from a callback, ie the deferred
        self.removeKeycard(keycard)
        self.info('keycard %r refused, Unauthorized' % keycard)
        return None

    def do_authenticate(self, keycard):
        # at this point we add it so there's an ID for challenge-response
        self.addKeycard(keycard)

        # check if the keycard is ready for the checker, based on the type
        if isinstance(keycard, self.challengeResponseClasses):
            # Check if we need to challenge it
            if not keycard.challenge:
                self.debug('putting challenge on keycard %r' % keycard)
                keycard.challenge = credentials.cryptChallenge()
                if keycard.username in self._db:
                    keycard.salt = self._db[keycard.username]
                else:
                    # random-ish salt, otherwise it's too obvious
                    string = str(random.randint(pow(10, 10), pow(10, 11)))
                    md = md5.new()
                    md.update(string)
                    keycard.salt = md.hexdigest()[:2]
                    self.debug("user not found, inventing bogus salt")
                self.debug("salt %s, storing challenge for id %s" % (
                    keycard.salt, keycard.id))
                # we store the challenge locally to verify against tampering
                self._challenges[keycard.id] = keycard.challenge
                return keycard

            if keycard.response:
                # Check if the challenge has been tampered with
                if self._challenges[keycard.id] != keycard.challenge:
                    self.removeKeycard(keycard)
                    self.info('keycard %r refused, challenge tampered with' %
                        keycard)
                    return None
                del self._challenges[keycard.id]

        # use the checker
        self.debug('submitting keycard %r to checker' % keycard)
        d = self._checker.requestAvatarId(keycard)
        d.addCallback(self._requestAvatarIdCallback, keycard)
        d.addErrback(self._requestAvatarIdErrback, keycard)
        return d
