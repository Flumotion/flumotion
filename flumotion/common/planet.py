# -*- Mode: Python; -*-
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

from twisted.spread import pb
from twisted.internet import defer

from flumotion.twisted import flavors
from flumotion.common import enum

class ManagerPlanetState(flavors.StateCacheable):
    def __init__(self):
        flavors.StateCacheable.__init__(self)
        self.addKey('name')
        self.addKey('parent')
        self.addKey('manager')
        self.addKey('atmosphere')
        self.addListKey('flows')

        # we always have at least one atmosphere
        self.set('atmosphere', ManagerAtmosphereState())

    def getComponents(self):
        """
        Return a list of component states in this planet.

        @rtype: list of L{ManagerComponentState}
        """
        list = []

        a = self.get('atmosphere')
        if a:
            list.extend(a.get('components'))

        flows = self.get('flows')
        if flows:
            for flow in flows:
                list.extend(flow.get('components'))

        return list


class AdminPlanetState(flavors.StateRemoteCache):
    pass

pb.setUnjellyableForClass(ManagerPlanetState, AdminPlanetState)

class ManagerAtmosphereState(flavors.StateCacheable):
    def __init__(self):
        flavors.StateCacheable.__init__(self)
        self.addKey('parent')
        self.addListKey('components')
        self.addKey('name')
        self.set('name', 'atmosphere')

    def empty(self):
        """
        Clear out all component entries.

        @returns: a DeferredList that will fire when all notifications are done.
        """
        list = [self.remove('components', c) for c in self.get('components')]
        return defer.DeferredList(list)

class AdminAtmosphereState(flavors.StateRemoteCache):
    pass

pb.setUnjellyableForClass(ManagerAtmosphereState, AdminAtmosphereState)

class ManagerFlowState(flavors.StateCacheable):
    def __init__(self):
        flavors.StateCacheable.__init__(self)
        self.addKey('name')
        self.addKey('parent')
        self.addListKey('components')

    def empty(self):
        """
        Clear out all component entries
        """
        # take a copy of the list because we're modifying while running
        components = self.get('components')[:]

        list = [self.remove('components', c) for c in components]
        return defer.DeferredList(list)

class AdminFlowState(flavors.StateRemoteCache):
    pass

pb.setUnjellyableForClass(ManagerFlowState, AdminFlowState)

# moods
moods = enum.EnumClass(
    'Moods',
    ('happy', 'hungry', 'waking', 'sleeping', 'lost', 'sad')
)

class ManagerComponentState(flavors.StateCacheable):

    __implements__ = flavors.IStateListener,
    
    def __init__(self):
        flavors.StateCacheable.__init__(self)
        # our additional keys
        self.addKey('name')
        self.addKey('type')
        self.addKey('parent')
        self.addKey('moodPending')
        self.addKey('workerRequested')
        self.addKey('config') # dictionary
        # combined from job state and our state
        self.addKey('mood')
        # proxied from job state
        self.addKey('ip')
        self.addKey('pid')
        self.addKey('workerName')
        self.addKey('message')
        self._jobState = None

    def __repr__(self):
        return "<ManagerComponentState %s>" % self._dict['name']
        #return "%r" % self._dict

    def setJobState(self, jobState):
        """
        @type jobState: L{ManagerJobState}
        """
        self._jobState = jobState
        for key in ['mood', 'ip', 'pid', 'workerName', 'message']:
            # only set non-None values, handling 'message' being None
            v = jobState.get(key)
            if v != None:
                self.set(key, v)
        jobState.addListener(self)

    def clearJobState(self):
        """
        Remove the job state.
        """
        self._jobState.removeListener(self)
        self._jobState = None

    # IStateListener interface
    def stateAppend(self, state, key, value):
        self.append(key, value)

    def stateRemove(self, state, key, value):
        self.remove(key, value)

    def stateSet(self, state, key, value):
        self.set(key, value)

class AdminComponentState(flavors.StateRemoteCache):
    pass

pb.setUnjellyableForClass(ManagerComponentState, AdminComponentState)

# state of an existing component running in a job process
# exchanged between worker and manager
class WorkerJobState(flavors.StateCacheable):
    def __init__(self):
        flavors.StateCacheable.__init__(self)
        self.addKey('mood')
        self.addKey('ip')
        self.addKey('pid')
        self.addKey('workerName')
        self.addKey('message')

class ManagerJobState(flavors.StateRemoteCache):
    pass

pb.setUnjellyableForClass(WorkerJobState, ManagerJobState)
