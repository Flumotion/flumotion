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

"""base view for displaying cursor components"""

from zope.interface import implements

from flumotion.common import log
from flumotion.twisted import flavors

__version__ = "$Rev$"


class BaseAdminText(log.Loggable):
    """
    I am a base class for all Text-based Admin views.
    I am a view on one component's properties.
    """

    implements(flavors.IStateListener)

    logCategory = "admintext"

    state = admin = 'hello pychecker'

    def __init__(self, state, admin):
        """
        @param state: state of component this is a UI for
        @type  state: L{flumotion.common.planet.AdminComponentState}
        @type  admin: L{flumotion.admin.admin.AdminModel}
        @param admin: the admin model that interfaces with the manager for us
        """
        self.state = state
        self.name = state.get('name')
        self.admin = admin
        self.debug('creating admin text for state %r' % state)

    def callRemote(self, methodName, *args, **kwargs):
        return self.admin.componentCallRemote(self.state, methodName,
                                              *args, **kwargs)

    ### child class methods to be overridden

    def setup(self):
        """
        Set up the admin view so it can display nodes.
        """
        raise NotImplementedError("Child class needs to implement setup")

    def uiStateChanged(self, stateObject):
        # default implementation
        pass

    def stateSet(self, object, key, value):
        self.uiStateChanged(object)

    def stateAppend(self, object, key, value):
        self.uiStateChanged(object)

    def stateRemove(self, object, key, value):
        self.uiStateChanged(object)

    # given an input text return possible completions

    def getCompletions(self, input):
        return []

    # run command, return string with result

    def runCommand(self, command):
        return ""
