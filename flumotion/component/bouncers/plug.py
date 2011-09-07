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

import time

from flumotion.component.plugs import base

__all__ = ['BouncerPlug']
__version__ = "$Rev$"


class BouncerPlug(base.ComponentPlug):
    """
    I am the base class for all bouncer plugs.
    """
    logCategory = 'bouncer-plug'

    def start(self, component):
        self._idCounter = 0
        self._idFormat = time.strftime('%Y%m%d%H%M%S-%%d')
        self._keycards = {} # keycard id -> Keycard
        return base.ComponentPlug.start(self, component)

    def authenticate(self, keycard):
        raise NotImplementedError("Subclass does not override authenticate")

    def set_expire_function(self, expire):
        self.expire = expire

    def generateKeycardId(self):
        # FIXME: what if it already had one ?
        # FIXME: deal with wraparound ?
        keycardId = self._idFormat % self._idCounter
        self._idCounter += 1
        return keycardId

    def addKeycard(self, keycard):
        """
        Adds a keycard to the keycards store.
        Can be called with the same keycard more than one time.
        If the keycard has already been added successfully,
        adding it again will succeed and return True.

        @param keycard: the keycard to add.
        @return: if the plug accepts the keycard.
        """
        # give keycard an id and store it in our hash
        if keycard.id in self._keycards:
            self.debug("%r in %r", keycard.id, self._keycards)
            # already in there
            return True

        keycardId = self.generateKeycardId()
        keycard.id = keycardId

        if hasattr(keycard, 'ttl') and keycard.ttl <= 0:
            self.debug("no ttlz")
            self.log('immediately expiring keycard %r', keycard)
            return False

        self._addKeycard(keycard)
        return True

    def _addKeycard(self, keycard):
        """
        Adds a keycard without checking.
        Used by sub-class knowing what they do.
        """
        self._keycards[keycard.id] = keycard
        self.on_keycardAdded(keycard)

        self.debug("added keycard with id %s, ttl %r", keycard.id,
                   getattr(keycard, 'ttl', None))

    def removeKeycard(self, keycard):
        del self._keycards[keycard.id]
        self.on_keycardRemoved(keycard)
        self.info("removed keycard with id %s" % keycard.id)

    def removeKeycardId(self, keycardId):
        self.debug("removing keycard with id %s" % keycardId)
        keycard = self._keycards[keycardId]
        self.removeKeycard(keycard)

    def expireKeycardId(self, keycardId):
        self.log("expiring keycard with id %r", keycardId)
        self.expire((keycardId, ))

    def expireKeycardIds(self, keycardIds):
        self.log("expiring keycards with ids %r", keycardIds)
        self.expire(keycardIds)

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


class TrivialBouncerPlug(BouncerPlug):

    def authenticate(self, keycard):
        keycard.state = keycards.AUTHENTICATED
        return keycard
