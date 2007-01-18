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


from flumotion.twisted import pb as fpb
from flumotion.common import log, planet
from flumotion.admin import admin


def get_admin_for_object(object):
    if object.get('parent'):
        return get_admin_for_object(object.get('parent'))
    else:
        return object.admin

# this is looking for a home.
def _make_watched(type, *mutators):
    class Watched(type):
        def __init__(self):
            type.__init__(self)
            self.watch_id = 0
            self.watch_procs = {} # id -> proc

        def watch(self, proc):
            self.watch_id += 1
            self.watch_procs[self.watch_id] = proc
            return self.watch_id

        def unwatch(self, id):
            del self.watch_procs[id]

        def notify_changed(self):
            for proc in self.watch_procs.values():
                proc(self)

    def mutate(method):
        def do_mutate(self, *args, **kwargs):
            method(self, *args, **kwargs)
            self.notify_changed()
        setattr(Watched, method.__name__, do_mutate)
    for i in mutators:
        mutate(getattr(type, i))

    return Watched

WatchedList = _make_watched(list, 'append', 'insert', 'remove', 'pop',
                            'sort', 'reverse')
WatchedDict = _make_watched(dict, '__setitem__', '__delitem__', 'pop',
                            'popitem', 'update')


class MultiAdminModel(log.Loggable):
    logCategory = 'multiadmin'

    def __init__(self):
        # public
        self.admins = WatchedDict() # {managerId: AdminModel}
        # private
        self.listeners = []

    # Listener implementation
    def emit(self, signal_name, *args, **kwargs):
        self.debug('emit %r %r %r' % (signal_name, args, kwargs))
        assert signal_name != 'handler'
        for c in self.listeners:
            if getattr(c, 'model_handler', None):
                c.model_handler(c, signal_name, *args, **kwargs)
            elif getattr(c, 'model_%s' % signal_name):
                getattr(c, 'model_%s' % signal_name)(*args, **kwargs)
            else:
                s = 'No model_%s in %r and no model_handler' % (signal_name, c)
                raise NotImplementedError(s)

    def addListener(self, obj):
        assert not obj in self.listeners
        self.listeners.append(obj)

    # Public
    def addManager(self, host, port, use_insecure, authenticator,
                   tenacious=False):
        def connected_cb(admin):
            planet = admin.planet
            self.info('Connected to manager %s (planet %s)'
                      % (admin.managerId, planet.get('name')))
            self.admins[admin.managerId] = admin
            self.emit('addPlanet', admin, planet)

        def disconnected_cb(admin):
            self.info('Disconnected from manager')
            if admin.managerId in self.admins:
                self.emit('removePlanet', admin, admin.planet)
                del self.admins[admin.managerId]
            else:
                self.warning('Could not find admin model %r' % admin)

        def connection_refused_cb(admin):
            self.info('Connection to %s:%d refused.' % (host, port))

        def connection_failed_cb(admin, string):
            self.info('Connection to %s:%d failed: %s' % (host, port, string))

        a = admin.AdminModel(authenticator)

        a.connectToHost(host, port, use_insecure, keep_trying=tenacious)
        a.connect('connected', connected_cb)
        a.connect('disconnected', disconnected_cb)
        a.connect('connection-refused', connection_refused_cb)
        a.connect('connection-failed', connection_failed_cb)
        return a

    def close_admin(self, admin):
        admin.shutdown()

    def for_each_component(self, object, proc):
        '''Call a procedure on each component that is a child of OBJECT'''
        # ah, for multimethods...
        if isinstance(object, planet.AdminPlanetState):
            self.for_each_component(object.get('atmosphere'), proc)
            for f in object.get('flows'):
                self.for_each_component(f, proc)
        elif (isinstance(object, planet.AdminAtmosphereState) or
              isinstance(object, planet.AdminFlowState)):
            for c in object.get('components'):
                self.for_each_component(c, proc)
        elif isinstance(object, planet.AdminComponentState):
            proc(object)

    def do_component_op(self, object, op):
        '''Call a method on the remote component object associated with
        a component state'''
        admin = get_admin_for_object(object)
        def do_op(object):
            admin.callRemote('component'+op, object)
        self.for_each_component(object, do_op)
