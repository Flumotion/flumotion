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

from flumotion.common import interfaces
from flumotion.component import component

__all__ = ['Bouncer']

class BouncerMedium(component.BaseComponentMedium):
    def remote_authenticate(self, credentials):
        return self.comp.authenticate(credentials)

    ### FIXME: having these methods means we need to properly separate
    # more component-related stuff
    def remote_link(self, eatersData, feadersData):
        print "FIXME: remote_link should only be called for feedComponent"
        return []

class Bouncer(component.BaseComponent):

    __implements__ = interfaces.IAuthenticate,

    component_medium_class = BouncerMedium
    
    logCategory = 'bouncer'
    def __init__(self, name):
        component.BaseComponent.__init__(self, name)
        self.debug('I AM ALIVE')
        
    def setDomain(self, name):
        self.domain = name

    def getDomain(self):
        return self.domain
    
    def authenticate(self, credentials):
        if not components.implements(keycard, credentials.ICredentials):
            self.debug('GIVE ME SOME CREDITS')
            raise AssertionError

        self.info('YOU GO GIRL')
        return True

def createComponent(config):
    return Bouncer(config['name'])
