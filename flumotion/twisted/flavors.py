# -*- Mode: Python; test-case-name: flumotion.test.test_flavors -*-
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
Flumotion Twisted-like flavors

Inspired by L{twisted.spread.flavors}
"""

from twisted.internet import defer
from twisted.spread import pb
from zope.interface import Interface
from flumotion.common import log

__version__ = "$Rev$"


### Generice Cacheable/RemoteCache for state objects


class IStateListener(Interface):
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


class IStateCacheableListener(Interface):
    """
    I am an interface for objects that want to listen to changes on
    cacheable states
    """

    def observerAppend(self, observer, num):
        """
        @type observer: L{twisted.spread.flavors.RemoteCacheObserver}
        @param observer: reference to the peer's L{RemoteCache}
                         that was added
        @type num: int
        @param num: number of observers present
        """

    def observerRemove(self, observer, num):
        """
        @type observer: L{twisted.spread.flavors.RemoteCacheObserver}
        @param observer: reference to the peer's L{RemoteCache}
                         that was removed
        @type num: int
        @param num: number of observers remaining
        """


class StateCacheable(pb.Cacheable):
    """
    I am a cacheable state object.

    I cache key-value pairs, where values can be either single objects
    or list of objects.
    """

    def __init__(self):
        self._observers = []
        self._hooks = []
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
        if value is None:
            value = []
        self._dict[key] = value

    # don't use {} as the default value, it creates only one reference and
    # reuses it

    def addDictKey(self, key, value=None):
        """
        Add a key for a dict value to the state cache.
        """
        if value is None:
            value = {}
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
        dList = [o.callRemote('set', key, value) for o in self._observers]
        return defer.DeferredList(dList)

    def append(self, key, value):
        """
        Append the given object to the given list.
        Notifies observers of this Cacheable through observe_append.
        """
        if not key in self._dict.keys():
            raise KeyError('%s in %r' % (key, self))

        self._dict[key].append(value)
        dList = [o.callRemote('append', key, value) for o in self._observers]
        return defer.DeferredList(dList)

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
        dList = [o.callRemote('remove', key, value) for o in self._observers]
        dl = defer.DeferredList(dList)
        return dl

    def setitem(self, key, subkey, value):
        """
        Set a value in the given dict.
        Notifies observers of this Cacheable through observe_setitem.
        """
        if not key in self._dict.keys():
            raise KeyError('%s in %r' % (key, self))

        self._dict[key][subkey] = value
        dList = [o.callRemote('setitem', key, subkey, value)
                for o in self._observers]
        return defer.DeferredList(dList)

    def delitem(self, key, subkey):
        """
        Removes an element from the given dict. Note that the key refers
        to the dict; it is the subkey (and its value) that will be removed.
        Notifies observers of this Cacheable through observe_delitem.
        """
        if not key in self._dict.keys():
            raise KeyError('%s in %r' % (key, self))

        try:
            value = self._dict[key].pop(subkey)
        except KeyError:
            raise KeyError('key %r not in dict %r for key %r' % (
                subkey, self._dict[key], key))
        dList = [o.callRemote('delitem', key, subkey, value) for o in
                self._observers]
        dl = defer.DeferredList(dList)
        return dl

    # pb.Cacheable methods

    def getStateToCacheAndObserveFor(self, perspective, observer):
        self._observers.append(observer)
        for hook in self._hooks:
            hook.observerAppend(observer, len(self._observers))
        return self._dict

    def stoppedObserving(self, perspective, observer):
        self._observers.remove(observer)
        for hook in self._hooks:
            hook.observerRemove(observer, len(self._observers))

    def addHook(self, hook):
        """
        A helper function that adds an object that would like to get
        informed by StateCacheable when observers has been added or
        removed.

        @param hook: an object who would like to receive state events
        @type hook:  object that implements
                     L{flumotion.twisted.flavors.IStateCacheableListener}
        """
        if hook in self._hooks:
            raise ValueError(
                "%r is already a hook of %r" % (hook, self))
        self._hooks.append(hook)

    def removeHook(self, hook):
        """
        Remove the object that listens to StateCacheable observer events

        @param hook: the object who would like to unsubscribe to state
                     events
        @type hook: object that implements
                    L{flumotion.twisted.flavors.IStateCacheableListener}
        """
        self._hooks.remove(hook)


# At some point, a StateRemoteCache will become invalid. The normal way
# would be losing the connection to the RemoteCacheable, although
# particular kinds of RemoteCache objects might have other ways
# (e.g. component removed from flow).
#
# We support listening for invalidation events. However, in order to
# ensure predictable program behavior, we can't do a notifyOnDisconnect
# directly on the broker. If we did that, program semantics would be
# dependent on the call order of the notifyOnDisconnect methods, which
# would likely lead to heisenbugs.
#
# Instead, invalidation will only be performed by the application, if at
# all, via an explicit call to invalidate().


class StateRemoteCache(pb.RemoteCache):
    """
    I am a remote cache of a state object.
    """

    def __init__(self):
        self._listeners = {}
        # no constructor
        # pb.RemoteCache.__init__(self)

    def __getitem__(self, key):
        return self.get(key)

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
            # FIXME: this means that callbacks will be fired in
            # arbitrary order; should be fired in order of connecting.
            # Use twisted.python.util.OrderedDict instead
            self._listeners = {}

    #F0.8: remove set=None and move set_=None there

    def addListener(self, listener, set=None, append=None, remove=None,
                    setitem=None, delitem=None, invalidate=None, set_=None):
        """
        Adds a listener to the remote cache.

        The caller will be notified of state events via the functions
        given as the 'set', 'append', and 'remove', 'setitem', and
        'delitem' keyword arguments.

        Always call this method using keyword arguments for the functions;
        calling them with positional arguments is not supported.

        Setting one of the event handlers to None will ignore that
        event. It is an error for all event handlers to be None.

        @param listener:   new listener object that wants to receive
                           cache state change notifications.
        @type  listener:   object implementing
                           L{flumotion.twisted.flavors.IStateListener}
        @param set_:       procedure to call when a value is set
        @type  set_:       procedure(object, key, value) -> None
        @param append:     procedure to call when a value is appended to a list
        @type  append:     procedure(object, key, value) -> None
        @param remove:     procedure to call when a value is removed from
                           a list
        @type  remove:     procedure(object, key, value) -> None
        @param setitem:    procedure to call when a value is set in a dict
        @type  setitem:    procedure(object, key, subkey, value) -> None
        @param delitem:    procedure to call when a value is removed
                           from a dict.
        @type  delitem:    procedure(object, key, subkey, value) -> None
        @param invalidate: procedure to call when this cache has been
                           invalidated.
        @type  invalidate: procedure(object) -> None
        """
        # F0.8: remove set
        if set:
            import warnings
            warnings.warn('Please use the set_ kwarg instead',
                DeprecationWarning, stacklevel=2)
            set_ = set

        if not (set_ or append or remove or setitem or delitem or invalidate):
            raise ValueError("At least one event handler has to be specified")

        self._ensureListeners()
        if listener in self._listeners:
            raise KeyError(
                "%r is already a listener of %r" % (listener, self))
        self._listeners[listener] = [set_, append, remove, setitem,
                                     delitem, invalidate]
        if invalidate and hasattr(self, '_cache_invalid'):
            invalidate(self)

    def removeListener(self, listener):
        self._ensureListeners()
        if listener not in self._listeners:
            raise KeyError(listener)
        del self._listeners[listener]

    # pb.RemoteCache methods

    def setCopyableState(self, dict):
        self._dict = dict

    def _notifyListeners(self, index, *args):
        # notify our local listeners; compute set of procs first, so as
        # to allow the listeners set to change during the calls
        self._ensureListeners()
        for proc in [tup[index] for tup in self._listeners.values()]:
            if proc:
                try:
                    proc(self, *args)
                except Exception, e:
                    # These are all programming errors
                    log.warning("stateremotecache",
                                'Exception in StateCache handler: %s',
                                log.getExceptionMessage(e))

    def observe_set(self, key, value):
        self._dict[key] = value
        # if we also subclass from Cacheable, then we're a proxy, so proxy
        if hasattr(self, 'set'):
            StateCacheable.set(self, key, value)

        self._notifyListeners(0, key, value)

    def observe_append(self, key, value):
        # if we also subclass from Cacheable, then we're a proxy, so proxy
        if hasattr(self, 'append'):
            StateCacheable.append(self, key, value)
        else:
            self._dict[key].append(value)

        self._notifyListeners(1, key, value)

    def observe_remove(self, key, value):
        # if we also subclass from Cacheable, then we're a proxy, so proxy
        if hasattr(self, 'remove'):
            StateCacheable.remove(self, key, value)
        else:
            try:
                self._dict[key].remove(value)
            except ValueError:
                raise ValueError("value %r not under key %r with values %r" %
                    (value, key, self._dict[key]))

        self._notifyListeners(2, key, value)

    def observe_setitem(self, key, subkey, value):
        # if we also subclass from Cacheable, then we're a proxy, so proxy
        if hasattr(self, 'setitem'):
            StateCacheable.setitem(self, key, subkey, value)
        else:
            self._dict[key][subkey] = value

        self._notifyListeners(3, key, subkey, value)

    def observe_delitem(self, key, subkey, value):
        # if we also subclass from Cacheable, then we're a proxy, so proxy
        if hasattr(self, 'delitem'):
            StateCacheable.delitem(self, key, subkey)
        else:
            try:
                del self._dict[key][subkey]
            except KeyError:
                raise KeyError("key %r not in dict %r for state dict %r" %
                    (subkey, self._dict[key], self._dict))

        self._notifyListeners(4, key, subkey, value)

    def invalidate(self):
        """Invalidate this StateRemoteCache.

        Calling this method will result in the invalidate callback being
        called for all listeners that passed an invalidate handler to
        addListener. This method is not called automatically; it is
        provided as a convenience to applications.
        """
        assert not hasattr(self, '_cache_invalid'), \
               'object has already been invalidated'
        # if we also subclass from Cacheable, there is currently no way
        # to remotely invalidate the cache. that's ok though, because
        # double-caches are currently only used by the manager, which
        # does not call invalidate() on its caches.
        self._cache_invalid = True

        self._notifyListeners(5)
