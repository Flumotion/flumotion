# -*- Mode: Python -*-
# vi:si:et:sw=4:sts=4:ts=4

# Flumotion - a streaming media server
# Copyright (C) 2004,2005,2006,2007,2008,2009 Fluendo, S.L.
# Copyright (C) 2010,2011 Flumotion Services, S.A.
# All rights reserved.
#
# This file may be distributed and/or modified under the terms of
# the GNU Lesser General Public License version 2.1 as published by
# the Free Software Foundation.
# This file is distributed without any warranty; without even the implied
# warranty of merchantability or fitness for a particular purpose.
# See "LICENSE.LGPL" in the source distribution for more information.
#
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

import random
import time

from twisted.internet import defer, reactor

from flumotion.common import keycards, errors, python, poller
from flumotion.common.componentui import WorkerComponentUIState

from flumotion.component import component
from flumotion.twisted import credentials

__all__ = ['Bouncer']
__version__ = "$Rev$"

# How many keycards to expire in a single synchronous deferred expiration call.
EXPIRE_BLOCK_SIZE = 100


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

    def remote_expireKeycardIds(self, keycardIds):
        """
        Called by bouncer views to expire multiple keycards.
        """
        return self.comp.expireKeycardIds(keycardIds)

    def remote_setEnabled(self, enabled):
        return self.comp.setEnabled(enabled)

    def remote_getEnabled(self):
        return self.comp.getEnabled()


class Bouncer(component.BaseComponent):
    """
    I am the base class for all bouncer components.

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

        self._expirer = poller.Poller(self._expire,
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

        def callAndPassthru(result, method, *args):
            method(*args)
            return result

        if not enabled and self.enabled:
            # If we were enabled and are being set to disabled, eject the warp
            # core^w^w^w^wexpire all existing keycards
            self.enabled = False
            self._expirer.stop()
            d = self.expireAllKeycards()
            d.addCallback(callAndPassthru, self.on_disabled)
            return d
        self.enabled = enabled
        d = defer.succeed(0)
        d.addCallback(callAndPassthru, self.on_enabled)
        return d

    def getEnabled(self):
        return self.enabled

    def do_stop(self):
        return self.setEnabled(False)

    def authenticate(self, keycard):
        if not self.typeAllowed(keycard):
            self.warning('keycard %r is not an allowed keycard class', keycard)
            return None

        if not self.do_validate(keycard):
            self.warning('keycard %r is not a valid keycard instance', keycard)
            return None

        if self.enabled:
            if not self._expirer.running and hasattr(keycard, 'ttl'):
                self.debug('installing keycard timeout poller')
                self._expirer.start()
            return defer.maybeDeferred(self.do_authenticate, keycard)
        else:
            self.debug("Bouncer disabled, refusing authentication")
            return None

    def do_expireKeycards(self, elapsed):
        """
        Override to expire keycards managed by sub-classes.

        @param elapsed: time in second since the last expiration call.
        @type elapsed: int
        @returns: if there is more keycard to expire. If False is returned,
                  the expirer poller MAY be stopped.
        @rtype: bool
        """
        for k in self._keycards.values():
            if hasattr(k, 'ttl'):
                k.ttl -= elapsed
                if k.ttl <= 0:
                    self.expireKeycardId(k.id)
        return len(self._keycards) > 0

    def do_validate(self, keycard):
        """
        Override to check keycards before authentication steps.
        Should return True if the keycard is valid, False otherwise.
        #FIXME: This belong to the base bouncer class

        @param keycard: the keycard that should be validated
                        before authentication
        @type keycard: flumotion.common.keycards.Keycard
        @returns: True if the keycard is accepted, False otherwise
        @rtype: bool
        """
        return True

    def do_authenticate(self, keycard):
        """
        Must be overridden by subclasses.

        Authenticate the given keycard.
        Return the keycard with state AUTHENTICATED to authenticate,
        with state REQUESTING to continue the authentication process,
        or REFUSED to deny the keycard or a deferred which should
        have the same eventual value.

        FIXME: Currently, a return value of 'None' is treated
        as rejecting the keycard. This is unintuitive.

        FIXME: in fact, for authentication sessions like challenge/response,
        returning a keycard with state REFUSED instead of None
        will not work properly and may enter in an asynchronous infinit loop.
        """
        raise NotImplementedError("authenticate not overridden")

    def on_keycardAdded(self, keycard):
        """
        Override to update sub-class specific data related to keycards.
        Called when the base bouncer accepts and references a new keycard.
        """

    def on_keycardRemoved(self, keycard):
        """
        Override to cleanup sub-class specific data related to keycards.
        Called when the base bouncer has cleanup his references to a keycard.
        """

    def on_enabled(self):
        """
        Override to initialize sub-class specific data
        when the bouncer is enabled.
        """

    def on_disabled(self):
        """
        Override to cleanup sub-class specific data
        when the bouncer is disabled.
        """

    def hasKeycard(self, keycard):
        return keycard in self._keycards.values()

    def generateKeycardId(self):
        # FIXME: what if it already had one ?
        # FIXME: deal with wraparound ?
        keycardId = self._idFormat % self._idCounter
        self._idCounter += 1
        return keycardId

    def addKeycard(self, keycard):
        """
        Adds a keycard to the bouncer.
        Can be called with the same keycard more than one time.
        If the keycard has already been added successfully,
        adding it again will succeed and return True.

        @param keycard: the keycard to add.
        @return: if the bouncer accepts the keycard.
        """
        # give keycard an id and store it in our hash
        if keycard.id in self._keycards:
            # already in there
            return True

        keycardId = self.generateKeycardId()
        keycard.id = keycardId

        if hasattr(keycard, 'ttl') and keycard.ttl <= 0:
            self.log('immediately expiring keycard %r', keycard)
            return False

        self._addKeycard(keycard)
        return True

    def removeKeycard(self, keycard):
        if not keycard.id in self._keycards:
            raise KeyError

        del self._keycards[keycard.id]
        self.on_keycardRemoved(keycard)

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
        return self.expireKeycardIds(self._keycards.keys())

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

    def expireKeycardIds(self, keycardIds):
        self.log("expiring keycards with id %r", keycardIds)
        d = defer.Deferred()
        self._expireNextKeycardBlock(0, keycardIds, d)
        return d

    def _expireNextKeycardBlock(self, total, keycardIds, finished):
        # We can't expire all keycards in a single blocking call because
        # there might be so many that the component goes lost.
        # This call will trigger expiring all keycards by chunking them
        # across separate deferreds.

        keycardBlock = keycardIds[:EXPIRE_BLOCK_SIZE]
        keycardIds = keycardIds[EXPIRE_BLOCK_SIZE:]
        idByReq = {}

        for keycardId in keycardBlock:
            if keycardId in self._keycards:
                keycard = self._keycards[keycardId]
                requesterId = keycard.requesterId
                idByReq.setdefault(requesterId, []).append(keycardId)
                self.removeKeycardId(keycardId)

        if not (idByReq and self.medium):
            # instead of serializing each block by chaining deferreds, which
            # can trigger maximum recursion depth, we just callback once
            # on the passed-in deferred
            finished.callback(total)
            return

        defs = [self.medium.callRemote('expireKeycards', rid, ids)
                for rid, ids in idByReq.items()]
        dl = defer.DeferredList(defs, consumeErrors=True)

        def countExpirations(results, total):
            return sum([v for s, v in results if s and v]) + total

        dl.addCallback(countExpirations, total)
        dl.addCallback(self._expireNextKeycardBlock, keycardIds, finished)

    def _addKeycard(self, keycard):
        """
        Adds a keycard without checking.
        Used by sub-class knowing what they do.
        """
        self._keycards[keycard.id] = keycard
        self.on_keycardAdded(keycard)

        self.debug("added keycard with id %s, ttl %r", keycard.id,
                   getattr(keycard, 'ttl', None))

    def _expire(self):
        if not self.do_expireKeycards(self._expirer.timeout):
            if self._expirer.running:
                self.debug('no more keycards, removing timeout poller')
                self._expirer.stop()


class AuthSessionBouncer(Bouncer):
    """
    I am a bouncer that handle pending authentication sessions.
    I am storing the last keycard of an authenticating session.
    """

    def init(self):
        # Keycards pending to be authenticated
        self._sessions = {} # keycard id -> (ttl, data)

    def on_disabled(self):
        # Removing all pending authentication
        self._sessions.clear()

    def do_extractKeycardInfo(self, keycard, oldData):
        """
        Extracts session info from a keycard.
        Used by updateAuthSession to store session info.
        Must be overridden by subclasses.
        """
        raise NotImplementedError()

    def hasAuthSession(self, keycard):
        """
        Tells if a keycard is related to a pending authentication session.
        It basically check if the id of the keycard is known.

        @param keycard: the keycard to check
        @type keycard: flumotion.common.keycards.Keycard
        @returns: if a pending authentication session associated
                  with the specified keycard exists.

        @rtype: bool
        """
        return (keycard.id is not None) and (keycard.id in self._sessions)

    def getAuthSessionInfo(self, keycard):
        """
        @return: the last updated keycard for the authentication session
                 associated with the specified keycard
        @rtype: flumotion.common.keycards.Keycard or None
        """
        data = keycard.id and self._sessions.get(keycard.id, None)
        return data and data[1]

    def startAuthSession(self, keycard):
        """
        Starts an authentication session with a keycard.
        The keycard id will be generated and set.
        The session info will be extracted from the keycard
        by calling the method do_extractKeycardInfo, and can
        be retrieved by calling getAuthSessionInfo.

        If a the keycard already have and id, and there is
        an authentication session with this id, the session info
        is updated from the keycard, and it return True.

        @param keycard: the keycard to update from.
        @type keycard: flumotion.common.keycards.Keycard
        @return: if the bouncer accepts the keycard.
        """
        # Check if there is already an authentication session
        if self.hasAuthSession(keycard):
            # Updating the authentication session data
            self._updateInfoFromKeycard(keycard)
            return True

        if keycard.id:
            self.warning("keycard %r already has an id, but no "
                         "authentication session", keycard)
            keycard.state = keycards.REFUSED
            return False

        if hasattr(keycard, 'ttl') and keycard.ttl <= 0:
            self.log('immediately expiring keycard %r', keycard)
            keycard.state = keycards.REFUSED
            return False

        # Generate an id for the authentication session
        keycardId = self.generateKeycardId()
        keycard.id = keycardId

        self._updateInfoFromKeycard(keycard)

        self.debug("started authentication session with with id %s, ttl %r",
                   keycard.id, getattr(keycard, 'ttl', None))
        return True

    def updateAuthSession(self, keycard):
        """
        Updates an authentication session with the last keycard.
        The session info will be extracted from the keycard
        by calling the method do_extractKeycardInfo, and can
        be retrieved by calling getAuthSessionInfo.

        @param keycard: the keycard to update from.
        @type keycard: flumotion.common.keycards.Keycard
        """
        # Check if there is already an authentication session
        if self.hasAuthSession(keycard):
            # Updating the authentication session data
            self._updateInfoFromKeycard(keycard)
        else:
            keycard.state = keycards.REFUSED

    def cancelAuthSession(self, keycard):
        """
        Cancels the authentication session associated
        with the specified keycard.
        Used when doing challenge/response authentication.
        @raise KeyError: when there is no session associated with the keycard.
        """
        keycard.state = keycards.REFUSED
        del self._sessions[keycard.id]

    def confirmAuthSession(self, keycard):
        """
        Confirms the authentication session represented
        by the specified keycard is authenticated.
        This will add the specified keycard to the
        bouncer keycard list like addKeycard would do
        but without changing the keycard id.
        The authentication session data is cleaned up.

        If the bouncer already have a keycard with the same id,
        the authentication is confirmed but the bouncer keycard
        is NOT updated. FIXME: is it what we want ? ? ?

        @param keycard: the keycard to add to the bouncer list.
        @type keycard: flumotion.common.keycards.Keycard
        @return: if the bouncer accepts the keycard.
        """
        keycardId = keycard.id

        if keycardId not in self._sessions:
            self.warning("unknown authentication session, or pending keycard "
                         "expired for id %s", keycardId)
            keycard.state = keycards.REFUSED
            return False

        del self._sessions[keycardId]

        # Check if there already an authenticated keycard with the same id
        if keycardId in self._keycards:
            self.debug("confirming an authentication session we already "
                       "know about with id %s", keycardId)
            keycard.state = keycards.AUTHENTICATED
            return True

        # check if the keycard already expired
        if hasattr(keycard, 'ttl') and keycard.ttl <= 0:
            self.log('immediately expiring keycard %r', keycard)
            keycard.state = keycards.REFUSED
            return False

        keycard.state = keycards.AUTHENTICATED
        self._addKeycard(keycard)
        return True

    def updateAuthSessionInfo(self, keycard, data):
        """
        Updates the authentication session data.
        Can be used bu subclasses to modify the data directly.
        """
        ttl, _oldData = self._sessions.get(keycard.id, (None, None))
        if ttl is None:
            ttl = getattr(keycard, 'ttl', None)
        self._sessions[keycard.id] = (ttl, data)

    def do_expireKeycards(self, elapsed):
        cont = Bouncer.do_expireKeycards(self, elapsed)
        for sessionId, (ttl, data) in self._sessions.items():
            if ttl is not None:
                ttl -= elapsed
                self._sessions[sessionId] = (ttl, data)
                if ttl <= 0:
                    del self._sessions[sessionId]

        return cont and len(self._sessions) > 0

    def _updateInfoFromKeycard(self, keycard):
        oldData = self.getAuthSessionInfo(keycard)
        newData = self.do_extractKeycardInfo(keycard, oldData)
        self.updateAuthSessionInfo(keycard, newData)


class TrivialBouncer(Bouncer):
    """
    A very trivial bouncer implementation.

    Useful as a concrete bouncer class for which all users are
    accepted whenever the bouncer is enabled.
    """
    keycardClasses = (keycards.KeycardGeneric, )

    def do_authenticate(self, keycard):
        if self.addKeycard(keycard):
            keycard.state = keycards.AUTHENTICATED
        else:
            keycard.state = keycards.REFUSED
        return keycard


class ChallengeResponseBouncer(AuthSessionBouncer):
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

    def do_extractKeycardInfo(self, keycard, oldData):
        return getattr(keycard, 'challenge', None)

    def _requestAvatarIdCallback(self, PossibleAvatarId, keycard):
        if not self.hasAuthSession(keycard):
            # The session expired
            keycard.state = keycards.REFUSED
            return None

        # authenticated, so return the keycard with state authenticated
        if not keycard.avatarId:
            keycard.avatarId = PossibleAvatarId
        self.info('authenticated login of "%s"' % keycard.avatarId)
        self.debug('keycard %r authenticated, id %s, avatarId %s' % (
            keycard, keycard.id, keycard.avatarId))
        self.confirmAuthSession(keycard)
        keycard.state = keycards.AUTHENTICATED
        return keycard

    def _requestAvatarIdErrback(self, failure, keycard):
        if not self.hasAuthSession(keycard):
            # The session expired
            keycard.state = keycards.REFUSED
            return None

        failure.trap(errors.NotAuthenticatedError)
        # FIXME: we want to make sure the "None" we return is returned
        # as coming from a callback, ie the deferred
        self.info('keycard %r refused, Unauthorized' % keycard)
        self.cancelAuthSession(keycard)
        keycard.state = keycards.REFUSED
        return None

    def do_authenticate(self, keycard):
        if isinstance(keycard, self.challengeResponseClasses):
            # Check if we need to challenge it
            if not self.hasAuthSession(keycard):
                if not self.startAuthSession(keycard):
                    # Keycard refused right away
                    keycard.state = keycards.REFUSED
                    return None
                self.debug('putting challenge on keycard %r' % keycard)
                keycard.challenge = credentials.cryptChallenge()
                if keycard.username in self._db:
                    keycard.salt = self._db[keycard.username]
                else:
                    # random-ish salt, otherwise it's too obvious
                    string = str(random.randint(pow(10, 10), pow(10, 11)))
                    md = python.md5()
                    md.update(string)
                    keycard.salt = md.hexdigest()[:2]
                    self.debug("user not found, inventing bogus salt")
                self.debug("salt %s, storing challenge for id %s"
                           % (keycard.salt, keycard.id))
                self.updateAuthSession(keycard)
                return keycard
            else:
                # Check if the challenge has been tampered with
                challenge = self.getAuthSessionInfo(keycard)
                if challenge != keycard.challenge:
                    self.info('keycard %r refused, challenge tampered with'
                              % keycard)
                    self.cancelAuthSession(keycard)
                    keycard.state = keycards.REFUSED
                    return None
        else:
            # Not a challenge/response authentication.
            # creating a temporary session to have a keycard id
            if not self.startAuthSession(keycard):
                # Keycard refused right away
                keycard.state = keycards.REFUSED
                return None

        # use the checker
        self.debug('submitting keycard %r to checker' % keycard)
        d = self._checker.requestAvatarId(keycard)
        d.addCallback(self._requestAvatarIdCallback, keycard)
        d.addErrback(self._requestAvatarIdErrback, keycard)
        return d
