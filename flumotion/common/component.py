# -*- Mode: Python; test-case-name: flumotion.test.test_common_component -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# flumotion/common/component.py: component state shared between manager and
# admin
#
# Flumotion - a streaming media server
# Copyright (C) 2004 Fluendo, S.L. (www.fluendo.com). All rights reserved.

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

### Generice Cacheable/RemoteCache for state objects
class StateCacheable(pb.Cacheable):
    """
    I am a cacheable state object.
    """
    def __init__(self):
        self._observers = []
        self._dict = {}

    # our methods
    def addKey(self, key, value=None):
        """
        Add a key to the state cache so it can be used with set.
        """
        self._dict[key] = value

    def get(self, key):
        """
        Get the state cache value for the given key.
        """
        if not key in self._dict.keys():
            raise KeyError('%s in %r' % (key, self))

        return self._dict[key]

    def set(self, key, value):
        """
        Set a given state key to the given value.
        Notifies observers of this Cacheable.
        """
        if not key in self._dict.keys():
            raise KeyError('%s in %r' % (key, self))

        self._dict[key] = value
        for o in self._observers: o.callRemote('set', key, value)
        
    # pb.Cacheable methods
    def getStateToCacheAndObserveFor(self, perspective, observer):
        self._observers.append(observer)
        return self._dict

    def stoppedObserving(self, perspective, observer):
        self._observers.remove(observer)

class StateRemoteCache(pb.RemoteCache):
    """
    I am a remote cache of a state object.
    """
    def __init__(self):
        self._listeners = []
        # no constructor
        # pb.RemoteCache.__init__(self)

    # our methods
    def get(self, key):
        """
        Get the state cache value for the given key.
        """
        if not key in self._dict.keys():
            raise KeyError('%s in %r' % (key, self))

        return self._dict[key]

    def _ensureListeners(self):
        # when this is created through serialization from a JobCS,
        # __init__ does not seem to get called, so create self._listeners
        if not hasattr(self, '_listeners'):
                self._listeners = []

    def addListener(self, listener):
        self._ensureListeners()
        self._listeners.append(listener)

    # pb.RemoteCache methods
    def setCopyableState(self, dict):
        self._dict = dict
        
    def observe_set(self, key, value):
        self._dict[key] = value
        # if we also subclass from Cacheable, then we're a proxy, so proxy
        if hasattr(self, 'set'):
            getattr(self, 'set')(key, value)

        # notify our local listeners
        self._ensureListeners()
        for l in self._listeners:
            l.stateChanged(self, key, value)

# component state proxy objects
class JobComponentState(StateCacheable):
    def __init__(self):
        StateCacheable.__init__(self)
        self.addKey('name')
        self.addKey('mood')
        self.addKey('pid')
        self.addKey('workerName')
        self.addKey('ip')

    def __repr__(self):
        return "%r" % self._dict

    def setName(self, name):
        self.set('name', name)

    def setMood(self, mood):
        self.set('mood', mood)

class ManagerComponentState(StateCacheable, StateRemoteCache):
    #def __init__(self):
    #    StateCacheable.__init__(self)
    #    StateRemoteCache.__init__(self)

    def __repr__(self):
        return "%r" % self._dict

class AdminComponentState(StateRemoteCache):
    pass

pb.setUnjellyableForClass(JobComponentState, ManagerComponentState)
pb.setUnjellyableForClass(ManagerComponentState, AdminComponentState)
