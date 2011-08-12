# -*- Mode: Python; -*-
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

"""serializable objects from worker through manager to admin.
Used by planet, flow, job and component.
"""

from twisted.spread import pb
from twisted.internet import defer
from zope.interface import implements

from flumotion.twisted import flavors
from flumotion.common import enum, log

__version__ = "$Rev$"


class ManagerPlanetState(flavors.StateCacheable):
    """
    I represent the state of a planet in the manager.

    I have the following keys:

     - name
     - manager
     - atmosphere:   L{ManagerAtmosphereState}
     - flows (list): list of L{ManagerFlowState}
    """
    # FIXME: why is there a 'parent' key ?

    def __init__(self):
        flavors.StateCacheable.__init__(self)
        self.addKey('name')
        self.addKey('version')
        self.addKey('parent')
        self.addKey('manager')
        self.addKey('atmosphere')
        self.addListKey('flows')
        self.addDictKey('messages')

        # we always have at least one atmosphere
        self.set('atmosphere', ManagerAtmosphereState())
        self.get('atmosphere').set('parent', self)

    def getComponents(self):
        """
        Return a list of all component states in this planet
        (from atmosphere and all flows).

        @rtype: list of L{ManagerComponentState}
        """
        ret = []

        a = self.get('atmosphere')
        if a:
            ret.extend(a.get('components'))

        flows = self.get('flows')
        if flows:
            for flow in flows:
                ret.extend(flow.get('components'))

        return ret


class AdminPlanetState(flavors.StateRemoteCache):
    """
    I represent the state of a planet in an admin client.
    See L{ManagerPlanetState}.
    """

    def invalidate(self):
        for flow in self.get('flows'):
            flow.invalidate()

        self.get('atmosphere').invalidate()

        flavors.StateRemoteCache.invalidate(self)

pb.setUnjellyableForClass(ManagerPlanetState, AdminPlanetState)


class ManagerAtmosphereState(flavors.StateCacheable):
    """
    I represent the state of an atmosphere in the manager.
    The atmosphere contains components that do not participate in a flow,
    but provide services to flow components.

    I have the following keys:

     - name:              string, "atmosphere"
     - parent:            L{ManagerPlanetState}
     - components (list): list of L{ManagerComponentState}
    """

    def __init__(self):
        flavors.StateCacheable.__init__(self)
        self.addKey('parent')
        self.addListKey('components')
        self.addKey('name')
        self.set('name', 'atmosphere')

    def empty(self):
        """
        Clear out all component entries.

        @returns: a DeferredList that will fire when all notifications
                  are done.
        """
        # make a copy, so we can iterate safely while modifying
        components = self.get('components')[:]

        dList = [self.remove('components', c) for c in components]
        return defer.DeferredList(dList)


class AdminAtmosphereState(flavors.StateRemoteCache):
    """
    I represent the state of an atmosphere in an admin client.
    See L{ManagerAtmosphereState}.
    """

    def invalidate(self):
        for component in self.get('components'):
            component.invalidate()

        flavors.StateRemoteCache.invalidate(self)

pb.setUnjellyableForClass(ManagerAtmosphereState, AdminAtmosphereState)


class ManagerFlowState(flavors.StateCacheable):
    """
    I represent the state of a flow in the manager.

    I have the following keys:

     - name:              string, name of the flow
     - parent:            L{ManagerPlanetState}
     - components (list): list of L{ManagerComponentState}
    """

    def __init__(self, **kwargs):
        """
        ManagerFlowState constructor. Any keyword arguments are
        intepreted as initial key-value pairs to set on the new
        ManagerFlowState.
        """
        flavors.StateCacheable.__init__(self)
        self.addKey('name')
        self.addKey('parent')
        self.addListKey('components')
        for k, v in kwargs.items():
            self.set(k, v)

    def empty(self):
        """
        Clear out all component entries
        """
        # take a copy of the list because we're modifying while running
        components = self.get('components')[:]

        dList = [self.remove('components', c) for c in components]
        return defer.DeferredList(dList)


class AdminFlowState(flavors.StateRemoteCache):
    """
    I represent the state of a flow in an admin client.
    See L{ManagerFlowState}.
    """

    def invalidate(self):
        for component in self.get('components'):
            component.invalidate()

        flavors.StateRemoteCache.invalidate(self)

pb.setUnjellyableForClass(ManagerFlowState, AdminFlowState)

# moods
# FIXME. make epydoc like this
"""
@cvar moods: an enum representing the mood a component can be in.
"""
moods = enum.EnumClass(
    'Moods',
    ('happy', 'hungry', 'waking', 'sleeping', 'lost', 'sad'))
moods.can_stop = staticmethod(lambda m: m != moods.sleeping)
moods.can_start = staticmethod(lambda m: m == moods.sleeping)

_jobStateKeys = ['mood', 'manager-ip', 'pid', 'workerName']
_jobStateListKeys = ['messages', ]

# FIXME: maybe make Atmosphere and Flow subclass from a ComponentGroup class ?


class ManagerComponentState(flavors.StateCacheable):
    """
    I represent the state of a component in the manager.
    I have my own state, and also proxy state from the L{ManagerJobState}
    when the component is actually created in a worker.

    I have the following keys of my own:

     - name:              str, name of the component, unique in the parent
     - parent:            L{ManagerFlowState} or L{ManagerAtmosphereState}
     - type:              str, type of the component
     - moodPending:       int, the mood value the component is being set to
     - workerRequested:   str, name of the worker this component is
                          requested to be started on.
     - config:            dict, the configuration dict for this component

    It also has a special key, 'mood'. This acts as a proxy for the mood
    in the L{WorkerJobState}, when there is a job attached (the job's copy
    is authoritative when it connects), and is controlled independently at
    other times.

    I proxy the following keys from the serialized L{WorkerJobState}:
      - mood, manager-ip, pid, workerName
      - messages (list)
    """

    def __init__(self):
        flavors.StateCacheable.__init__(self)
        # our additional keys
        self.addKey('name')
        self.addKey('type')
        self.addKey('parent')
        self.addKey('moodPending')
        self.addKey('workerRequested')
        self.addKey('config') # dictionary
        self.addKey('lastKnownPid')

        # proxied from job state or combined with our state (mood)
        for k in _jobStateKeys:
            self.addKey(k)
        for k in _jobStateListKeys:
            self.addListKey(k)
        self._jobState = None

    def __repr__(self):
        return "<%s.%s name=%r>" % (self.__module__,
                                    self.__class__.__name__,
                                    self._dict['name'])

    def setJobState(self, jobState):
        """
        Set the job state I proxy from.

        @type jobState: L{ManagerJobState}
        """
        self._jobState = jobState
        for key in _jobStateKeys:
            # only set non-None values
            if key == 'mood':
                continue
            v = jobState.get(key)
            if v != None:
                self.set(key, v)
        for key in _jobStateListKeys:
            valueList = jobState.get(key)
            if valueList != None:
                for v in valueList:
                    self.append(key, v)
        # set mood last; see #552
        self.set('mood', jobState.get('mood'))

        # only proxy keys we want proxied; eaterNames and feederNames
        # are ignored for example
        proxiedKeys = _jobStateKeys + _jobStateListKeys

        def proxy(attr):

            def event(state, key, value):
                if key in proxiedKeys:
                    getattr(self, attr)(key, value)
            return event

        jobState.addListener(self, set_=proxy('set'), append=proxy('append'),
                             remove=proxy('remove'))

    def set(self, key, value):
        # extend set so we can log mood changes
        if key == 'mood':
            log.info('componentstate', 'mood of %s changed to %s',
                     self.get('name'), moods.get(value).name)
        flavors.StateCacheable.set(self, key, value)
        if key == 'mood' and value == self.get('moodPending'):
            # we have reached our pending mood
            self.set('moodPending', None)

    def setMood(self, moodValue):
        if self._jobState and moodValue != moods.sad.value:
            log.warning('componentstate', 'cannot set component mood to '
                        'something other than sad when we have a '
                        'jobState -- fix your code!')
        elif moodValue == self.get('mood'):
            log.log('componentstate', '%s already in mood %d',
                    self.get('name'), moodValue)
        else:
            log.debug('componentstate',
                      'manager sets mood of %s from %s to %d',
                      self.get('name'), self.get('mood'), moodValue)
            self.set('mood', moodValue)

    def clearJobState(self, shutdownRequested):
        """
        Remove the job state.
        """
        # Clear messages proxied from job
        for m in self._jobState.get('messages'):
            self.remove('messages', m)

        self.set('lastKnownPid', self._jobState.get('pid'))

        self._jobState.removeListener(self)
        self._jobState = None

        # Clearing a job state means that a component logged out. If the
        # component logs out due to an explicit manager request, go to
        # sleeping. Otherwise if the component is sad, leave the mood as
        # it is, or otherwise go to lost, because it got disconnected
        # for an unknown reason (probably network related).
        if shutdownRequested:
            log.debug('componentstate', "Shutdown was requested, %s"
                      " now sleeping", self.get('name'))
            self.setMood(moods.sleeping.value)
        elif self.get('mood') != moods.sad.value:
            log.debug('componentstate', "Shutdown was NOT requested,"
                      " %s now lost, last know pid is: %r",
                      self.get('name'), self.get('lastKnownPid'))
            self.setMood(moods.lost.value)


class AdminComponentState(flavors.StateRemoteCache):
    """
    I represent the state of a component in the admin client.
    See L{ManagerComponentState}.
    """

    def __repr__(self):
        return "<%s.%s name=%r>" % (self.__module__,
                                    self.__class__.__name__,
                                    self._dict['name'])

pb.setUnjellyableForClass(ManagerComponentState, AdminComponentState)

# state of an existing component running in a job process
# exchanged between worker and manager


class WorkerJobState(flavors.StateCacheable):
    """
    I represent the state of a job in the worker, running a component.

    I have the following keys:

     - mood:              int, value of the mood this component is in
     - ip:                string, IP address of the worker
     - pid:               int, PID of the job process
     - workerName:        string, name of the worker I'm running on
     - messages:          list of L{flumotion.common.messages.Message}

    In addition, if I am the state of a FeedComponent, then I also
    have the following keys:

     - eaterNames:        list of feedId being eaten by the eaters
     - feederNames:       list of feedId being fed by the feeders

    @todo: change eaterNames and feederNames to eaterFeedIds and ...
    """

    def __init__(self):
        flavors.StateCacheable.__init__(self)
        for k in _jobStateKeys:
            self.addKey(k)
        for k in _jobStateListKeys:
            self.addListKey(k)


class ManagerJobState(flavors.StateRemoteCache):
    """
    I represent the state of a job in the manager.
    See L{WorkerJobState}.
    """
    pass

pb.setUnjellyableForClass(WorkerJobState, ManagerJobState)
