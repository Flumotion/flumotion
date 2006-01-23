# -*- Mode: Python; test-case-name: flumotion.test.test_flavors -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# Flumotion - a streaming media server
# Copyright (C) 2004,2005,2006 Fluendo, S.L. (www.fluendo.com).
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
Flumotion Twisted-like flavors

Inspired by L{twisted.spread.flavors}
"""

from twisted.internet import defer
from twisted.python import components
from twisted.spread import pb

# T1.3: suppress components warnings in Twisted 2.0
from flumotion.twisted import compat
compat.filterWarnings(components, 'ComponentsDeprecationWarning')

### Generice Cacheable/RemoteCache for state objects
class IStateListener(components.Interface):
    """
    I am an interface for objects that want to listen to changes on
    cached states.
    """
    def stateSet(self, object, key, value):
        """
        @type  object: L{StateRemoteCache}
        @param object: the state object having changed
        @type  key:    string
        @param key:    the key being set
        @param value:  the value the key is being set to
        
        The given key on the given object has been set to the given value.
        """

    def stateAppend(self, object, key, value):
        """
        @type  object: L{StateRemoteCache}
        @param object: the state object having changed
        @type  key:    string
        @param key:    the key being appended to
        @param value:  the value being appended to the list given by key

        The given value has been added to the list given by the key.
        """

    def stateRemove(self, object, key, value):
        """
        @type  object: L{StateRemoteCache}
        @param object: the state object having changed
        @type  key:    string
        @param key:    the key being removed from
        @param value:  the value being removed from the list given by key

        The given value has been removed from the list given by the key.
        """

class StateCacheable(pb.Cacheable):
    """
    I am a cacheable state object.

    I cache key-value pairs, where values can be either single objects
    or list of objects.
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

    # don't use [] as the default value, it creates only one reference and
    # reuses it
    def addListKey(self, key, value=None):
        """
        Add a key for a list of objects to the state cache.
        """
        if not value:
            value = []
        self._dict[key] = value

    def hasKey(self, key):
        return key in self._dict.keys()

    def keys(self):
        return self._dict.keys()

    def get(self, key, otherwise=None):
        """
        Get the state cache value for the given key.

        Return otherwise in case where key is present but value None.
        """
        if not key in self._dict.keys():
            raise KeyError('%s in %r' % (key, self))

        v = self._dict[key]
        # not v would also trigger empty lists
        if v == None:
            return otherwise

        return v

    def set(self, key, value):
        """
        Set a given state key to the given value.
        Notifies observers of this Cacheable through observe_set.
        """
        if not key in self._dict.keys():
            raise KeyError('%s in %r' % (key, self))

        self._dict[key] = value
        list = [o.callRemote('set', key, value) for o in self._observers]
        return defer.DeferredList(list)
        
    def append(self, key, value):
        """
        Append the given object to the given list.
        Notifies observers of this Cacheable through observe_append.
        """
        if not key in self._dict.keys():
            raise KeyError('%s in %r' % (key, self))

        self._dict[key].append(value)
        list = [o.callRemote('append', key, value) for o in self._observers]
        return defer.DeferredList(list)
 
    def remove(self, key, value):
        """
        Remove the given object from the given list.
        Notifies observers of this Cacheable through observe_remove.
        """
        if not key in self._dict.keys():
            raise KeyError('%s in %r' % (key, self))

        try:
            self._dict[key].remove(value)
        except ValueError:
            raise ValueError('value %r not in list %r for key %r' % (
                value, self._dict[key], key))
        list = [o.callRemote('remove', key, value) for o in self._observers]
        dl = defer.DeferredList(list)
        return dl
 
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
    def hasKey(self, key):
        return key in self._dict.keys()

    def keys(self):
        return self._dict.keys()

    def get(self, key, otherwise=None):
        """
        Get the state cache value for the given key.

        Return otherwise in case where key is present but value None.
        """
        if not key in self._dict.keys():
            raise KeyError('%s in %r' % (key, self))

        v = self._dict[key]
        # compare to actual None, otherwise we also get zero-like values
        if v == None:
            return otherwise

        return v

    def _ensureListeners(self):
        # when this is created through serialization from a JobCS,
        # __init__ does not seem to get called, so create self._listeners
        if not hasattr(self, '_listeners'):
                self._listeners = []

    def addListener(self, listener):
        if not components.implements(listener, IStateListener):
            raise NotImplementedError(
                '%r instance does not implement IStateListener' % listener)

        self._ensureListeners()
        self._listeners.append(listener)

    def removeListener(self, listener):
        if not components.implements(listener, IStateListener):
            raise NotImplementedError(
                '%r instance does not implement IStateListener' % listener)

        self._ensureListeners()
        if listener not in self._listeners:
            raise KeyError(
                '%r instance not registered as a listener' % listener)
        self._listeners.remove(listener)

    # pb.RemoteCache methods
    def setCopyableState(self, dict):
        self._dict = dict
        
    def observe_set(self, key, value):
        self._dict[key] = value
        # if we also subclass from Cacheable, then we're a proxy, so proxy
        if hasattr(self, 'set'):
            StateCacheable.set(self, key, value)

        # notify our local listeners
        self._ensureListeners()
        for l in self._listeners:
            l.stateSet(self, key, value)

    def observe_append(self, key, value):
        # if we also subclass from Cacheable, then we're a proxy, so proxy
        if hasattr(self, 'append'):
            StateCacheable.append(self, key, value)
        else:
            self._dict[key].append(value)

        # notify our local listeners
        self._ensureListeners()
        for l in self._listeners:
            l.stateAppend(self, key, value)

    def observe_remove(self, key, value):
        # if we also subclass from Cacheable, then we're a proxy, so proxy
        if hasattr(self, 'remove'):
            StateCacheable.remove(self, key, value)
        else:
            self._dict[key].remove(value)

        # notify our local listeners
        self._ensureListeners()
        for l in self._listeners:
            l.stateRemove(self, key, value)
