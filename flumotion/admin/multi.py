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

"""admin model used to connect to multiple managers"""

from twisted.internet import defer

from flumotion.common import log, planet, errors, startset, watched
from flumotion.admin import admin

__version__ = "$Rev$"


def get_admin_for_object(object):
    import warnings
    warnings.warn('Use getAdminForObject', DeprecationWarning, stacklevel=2)
    return getAdminForObject(object)


def getAdminForObject(object):
    if object.get('parent'):
        return get_admin_for_object(object.get('parent'))
    else:
        return object.admin


class MultiAdminModel(log.Loggable):
    logCategory = 'multiadmin'

    def __init__(self):
        self.admins = watched.WatchedDict() # {managerId: AdminModel}

        self._listeners = []
        self._reconnectHandlerIds = {} # managerId => [disconnect, id..]
        self._startSet = startset.StartSet(self.admins.has_key,
                                           errors.AlreadyConnectingError,
                                           errors.AlreadyConnectedError)

    # Listener implementation

    def emit(self, signal_name, *args, **kwargs):
        self.debug('emit %r %r %r' % (signal_name, args, kwargs))
        assert signal_name != 'handler'
        for c in self._listeners:
            if getattr(c, 'model_handler', None):
                c.model_handler(c, signal_name, *args, **kwargs)
            elif getattr(c, 'model_%s' % signal_name):
                getattr(c, 'model_%s' % signal_name)(*args, **kwargs)
            else:
                s = 'No model_%s in %r and no model_handler' % (signal_name, c)
                raise NotImplementedError(s)

    def addListener(self, obj):
        assert not obj in self._listeners
        self._listeners.append(obj)

    def removeListener(self, obj):
        self._listeners.remove(obj)

    def _managerConnected(self, admin):
        if admin.managerId not in self._reconnectHandlerIds:
            # the first time a manager is connected to, start listening
            # for reconnections; intertwingled with removeManager()
            ids = []
            ids.append(admin.connect('connected',
                                     self._managerConnected))
            ids.append(admin.connect('disconnected',
                                     self._managerDisconnected))
            self._reconnectHandlerIds[admin.managerId] = admin, ids

        adminplanet = admin.planet
        self.info('Connected to manager %s (planet %s)',
                  admin.managerId, adminplanet.get('name'))
        assert admin.managerId not in self.admins
        self.admins[admin.managerId] = admin
        self.emit('addPlanet', admin, adminplanet)

    def _managerDisconnected(self, admin):
        if admin.managerId in self.admins:
            self.emit('removePlanet', admin, admin.planet)
            del self.admins[admin.managerId]
        else:
            self.warning('Could not find admin model %r', admin)

    def addManager(self, connectionInfo, tenacious=False,
                   writeConnection=True):
        i = connectionInfo
        managerId = str(i)

        # This dance of deferreds is here so as to make sure that
        # removeManager can cancel a pending connection.

        # can raise errors.AlreadyConnectingError or
        # errors.AlreadyConnectedError
        try:
            startD = self._startSet.createStart(managerId)
        except Exception, e:
            return defer.fail(e)

        a = admin.AdminModel()
        connectD = a.connectToManager(i, tenacious,
                                      writeConnection=writeConnection)
        assert a.managerId == managerId

        def connect_callback(_):
            self._startSet.avatarStarted(managerId)

        def connect_errback(failure):
            self._startSet.avatarStopped(managerId, lambda _: failure)

        connectD.addCallbacks(connect_callback, connect_errback)

        def start_callback(_):
            self._managerConnected(a)

        def start_errback(failure):
            a.shutdown()
            return failure

        startD.addCallbacks(start_callback, start_errback)

        return startD

    def removeManager(self, managerId):
        self.info('disconnecting from %s', managerId)

        # Four cases:
        # (1) We have no idea about this managerId, the caller is
        # confused -- do nothing
        # (2) We started connecting to this managerId, but never
        # succeeded -- cancel pending connections
        # (3) We connected at least once, and are connected now -- we
        # have entries in the _reconnectHandlerIds and in self.admins --
        # disconnect from the signals, disconnect from the remote
        # manager, and don't try to reconnect
        # (4) We connected at least once, but are disconnected now -- we
        # have an entry in _reconnectHandlerIds but not self.admins --
        # disconnect from the signals, and stop trying to reconnect

        # stop listening to admin's signals, if the manager had actually
        # connected at some point
        if managerId in self._reconnectHandlerIds:
            admin, handlerIds = self._reconnectHandlerIds.pop(managerId)
            map(admin.disconnect, handlerIds) # (3) and (4)
            if managerId not in self.admins:
                admin.shutdown() # (4)

        if managerId in self.admins: # (3)
            admin = self.admins[managerId]
            admin.shutdown()
            self._managerDisconnected(admin)

        # Firing this has the side effect of errbacking on any pending
        # start, calling start_errback above if appropriate. (2)
        self._startSet.avatarStopped(
            managerId, lambda _: errors.ConnectionCancelledError())

        # always succeed, see (1)
        return defer.succeed(managerId)

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
