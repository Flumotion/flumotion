# -*- Mode: Python -*-
# vi:si:et:sw=4:sts=4:ts=4

# Flumotion - a video streamer server
# Copyright (C) 2004 Fluendo
#
# flumotion/component/bouncer.py: base class for bouncer components
#
# Flumotion - a streaming media server
# Copyright (C) 2004 Fluendo (www.fluendo.com)

# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
# See "LICENSE.GPL" in the source distribution for more information.

# This program is also licensed under the Flumotion license.
# See "LICENSE.Flumotion" in the source distribution for more information.

from twisted.python import components
from twisted.cred import credentials

from flumotion.common import interfaces, keycards
from flumotion.component import component

__all__ = ['Bouncer']

class BouncerMedium(component.BaseComponentMedium):
    def remote_authenticate(self, keycard):
        return self.comp.authenticate(keycard)

    def remote_removeKeycard(self, keycardId):
        self.comp.removeKeycard(keycardId)

    ### FIXME: having these methods means we need to properly separate
    # more component-related stuff
    def remote_link(self, eatersData, feadersData):
        self.warning("FIXME: remote_link should only be called for feedComponent")
        return []

class Bouncer(component.BaseComponent):

    __implements__ = interfaces.IAuthenticate,

    component_medium_class = BouncerMedium
    
    logCategory = 'bouncer'
    def __init__(self, name):
        component.BaseComponent.__init__(self, name)
        self._idCounter = 0
        self._keycards = {} # keycard id -> Keycard
        
    def setDomain(self, name):
        self.domain = name

    def getDomain(self):
        return self.domain
    
    def authenticate(self, keycard):
        if not components.implements(keycard, credentials.ICredentials):
            self.warn('keycard %r does not implement ICredentials', keycard)
            raise AssertionError

        # FIXME: make configurable
        if keycard.username == 'thomas' and keycard.password == 'plasmatv':
            self.info('keycard %r authenticated' % keycard)
            self._addKeycard(keycard)
            return keycard
        else:
            self.info('keycard %r refused' % keycard)
            return None

    def _addKeycard(self, keycard):
        # give keycard an id and store it in our hash
        id = self._idCounter
        self._idCounter += 1
        # FIXME: what if it already had one ?
        # FIXME: deal with wraparound ?
        keycard.id = keycard.componentName + ":%016x" % self._idCounter
        self._keycards[keycard.id] = keycard
        self.log("added keycard with id %s" % keycard.id)

    def removeKeycard(self, id):
        if not self._keycards.has_key(id):
            raise
        del self._keycards[id]
        self.log("removed keycard with id %s" % id)

def createComponent(config):
    return Bouncer(config['name'])
