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
"""

import md5
import random

from twisted.python import components
from twisted.internet import defer
from twisted.cred import error

from flumotion.common import interfaces, keycards
from flumotion.common.componentui import WorkerComponentUIState

from flumotion.component import component
from flumotion.twisted import flavors, credentials

__all__ = ['Bouncer']

class BouncerMedium(component.BaseComponentMedium):

    logCategory = 'bouncermedium'
    def remote_authenticate(self, keycard):
        """
        Authenticates the given keycard.

        @type  keycard: L{flumotion.common.keycards.Keycard}
        """
        return self.comp.authenticate(keycard)

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

    def init(self):
        self._idCounter = 0
        self._keycards = {} # keycard id -> Keycard
        self._keycardDatas = {} # keycard id -> data in uiState
        self.uiState.addListKey('keycards')

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

        self.enabled = enabled

    def authenticate(self, keycard):
        if not self.typeAllowed(keycard):
            self.warning('keycard %r is not an allowed keycard class', keycard)
            return None

        if self.enabled:
            return self.do_authenticate(keycard)
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

    def addKeycard(self, keycard):
        # give keycard an id and store it in our hash
        if self._keycards.has_key(keycard.id):
            # already in there
            return
            
        # FIXME: what if it already had one ?
        # FIXME: deal with wraparound ?
        id = "%016x" % self._idCounter
        self._idCounter += 1

        keycard.id = id
        self._keycards[id] = keycard
        data = keycard.getData()
        self._keycardDatas[id] = data

        self.uiState.append('keycards', data)
        self.debug("added keycard with id %s" % keycard.id)

    def removeKeycard(self, keycard):
        id = keycard.id
        if not self._keycards.has_key(id):
            raise KeyError

        del self._keycards[id]

        data = self._keycardDatas[id]
        self.uiState.remove('keycards', data)
        del self._keycardDatas[id]
        self.debug("removed keycard with id %s" % id)

    def removeKeycardId(self, id):
        self.debug("removing keycard with id %s" % id)
        if not self._keycards.has_key(id):
            raise KeyError

        keycard = self._keycards[id]
        self.removeKeycard(keycard)

    def expireAllKeycards(self):
        return defer.DeferredList(
            [self.expireKeycardId(id) for id in self._keycards])

    def expireKeycardId(self, id):
        self.debug("expiring keycard with id %r" % id)
        if not self._keycards.has_key(id):
            raise KeyError

        keycard = self._keycards[id]

        d = self.medium.callRemote(
            'expireKeycard', keycard.requesterId, keycard.id)
        # we don't need to remove the keycard ourselves, since that's done
        # by the requester when the client is definately gone

        return d

class TrivialBouncer(Bouncer):
    """
    A very trivial bouncer implementation.

    Useful as a concrete bouncer class for which all users are accepted whenever
    the bouncer is enabled.
    """
    keycardClasses = (keycards.KeycardGeneric,)

    def do_authenticate(self, keycard):
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
        failure.trap(error.UnauthorizedLogin)
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
                    string = str(random.randint(pow(10,10), pow(10, 11)))
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


