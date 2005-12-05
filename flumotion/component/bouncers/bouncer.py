# -*- Mode: Python -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# Flumotion - a streaming media server
# Copyright (C) 2004,2005 Fluendo, S.L. (www.fluendo.com). All rights reserved.

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

from twisted.python import components
from twisted.cred import credentials

from flumotion.common import interfaces, keycards
from flumotion.common.componentui import WorkerComponentUIState

from flumotion.component import component
from flumotion.twisted import flavors

__all__ = ['Bouncer']

class BouncerMedium(component.BaseComponentMedium):

    logCategory = 'bouncermedium'
    def remote_authenticate(self, keycard):
        return self.comp.authenticate(keycard)

    # FIXME: rename to ...Id
    def remote_removeKeycard(self, keycardId):
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

       
    ### FIXME: having these methods means we need to properly separate
    # more component-related stuff
    def remote_link(self, eatersData, feadersData):
        self.warning("FIXME: remote_link should only be called for feedComponent")
        return []

class Bouncer(component.BaseComponent):
    keycardClasses = ()

    component_medium_class = BouncerMedium
    
    logCategory = 'bouncer'
    def setup(self, config):
        self._idCounter = 0
        self._keycards = {} # keycard id -> Keycard
        self._keycardDatas = {} # keycard id -> data in uiState
        self.uiState.addListKey('keycards')
        
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
         
    # FIXME: do we need this at all in the base class ?
    def authenticate(self, keycard):
        if not components.implements(keycard, credentials.ICredentials):
            self.warning('keycard %r does not implement ICredentials', keycard)
            raise AssertionError

        self.info('keycard %r refused because the base authenticate() should be overridden' % keycard)
        return None

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

    def expireKeycardId(self, id):
        self.debug("expiring keycard with id %r" % id)
        if not self._keycards.has_key(id):
            raise KeyError

        keycard = self._keycards[id]

        d = self.medium.callRemote(
            'expireKeycard', keycard.requesterName, keycard.id)
        # we don't need to remove the keycard ourselves, since that's done
        # by the requester when the client is definately gone

        return d
 
def createComponent(config):
    return Bouncer(config['name'])
