# -*- Mode: Python -*-
# vi:si:et:sw=4:sts=4:ts=4

# Flumotion - a video streaming server
# Copyright (C) 2004 Fluendo
# 
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
# 
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Street #330, Boston, MA 02111-1307, USA.

import sys

import gobject
from twisted.spread import pb
from twisted.internet import error
from twisted.python import rebuild, reflect

from flumotion.common import interfaces, errors
from flumotion.utils import log, reload
from flumotion.utils.gstutils import gsignal
from flumotion.twisted import pbutil

class AdminInterface(pb.Referenceable, gobject.GObject, log.Loggable):
    """Lives in the admin client.
       Manager calls on us through admin.Admin.
       I can call on manager admin.Admin objects.
    """
    gsignal('connected')
    gsignal('connection-refused')
    gsignal('ui-state-changed', str, object)
    gsignal('update', object)
    
    logCategory = 'adminclient'

    def __init__(self):
        self.__gobject_init__()
        self.factory = pbutil.FMClientFactory()
        self.debug("logging in to ClientFactory")
        cb = self.factory.login(pbutil.Username('admin'), self,
                                pb.IPerspective,
                                interfaces.IAdminComponent)
        cb.addCallback(self._gotPerspective)
        cb.addErrback(self._loginErrback)

    def _gotPerspective(self, perspective):
        self.debug("gotPerspective: %s" % perspective)
        self.remote = perspective

    def _loginErrback(self, failure):
        r = failure.trap(error.ConnectionRefusedError)
        self.debug("emitting connection-refused")
        self.emit('connection-refused')
        self.debug("emitted connection-refused")

    ### pb.Referenceable methods
    def remote_log(self, category, type, message):
        self.log('remote: %s: %s: %s' % (type, category, message))
        
    def remote_componentAdded(self, component):
        self.debug('componentAdded %s' % component.name)
        self.clients.append(component)
        self.emit('update', self.clients)
        
    def remote_componentRemoved(self, component):
        # FIXME: this asserts, no method, when server dies
        # component will be a RemoteComponentView, so we can only use a
        # member, not a method to get the name
        self.debug('componentRemoved %s' % component.name)
        self.clients.remove(component)
        self.emit('update', self.clients)
        
    def remote_initial(self, clients):
        self.debug('remote_initial %s' % clients)
        self.clients = clients
        self.emit('connected')

    def remote_shutdown(self):
        self.debug('shutting down')

    def remote_uiStateChanged(self, name, state):
        self.emit('ui-state-changed', name, state)
        
    def setProperty(self, component, element, property, value):
        if not self.remote:
            self.warning('No remote object')
            return
        return self.remote.callRemote('setComponentElementProperty',
                                      component, element, property, value)

    def getProperty(self, component, element, property):
        return self.remote.callRemote('getComponentElementProperty',
                                      component, element, property)

    def callComponentRemote(self, component_name, method_name, *args, **kwargs):
        return self.remote.callRemote('callComponentRemote',
                                      component_name, method_name, *args, **kwargs)
        
    def reload(self):
        # XXX: reload admin.py too
        name = reflect.filenameToModuleName(__file__)

        #self.log("rebuilding '%s'" % name)
        self.info("rebuilding '%s'" % name)
        rebuild.rebuild(sys.modules[name])

        reload()

        cb = self.reloadManager()
        # stack callbacks so that a new one only gets sent after the previous
        # one has completed
        for client in self.clients:
            cb = cb.addCallback(self.reloadComponent, client)
        return cb

    def reloadManager(self):
        def _reloaded(result, self):
            self.info("reloaded manager code")

        self.info("reloading manager code")
        cb = self.remote.callRemote('reloadManager')
        cb.addCallback(_reloaded, self)
        return cb

    def reloadComponent(self, result, client):
        def _reloaded(result, self, client):
            self.info("reloaded component %s code" % client.name)

        self.info("reloading component %s code" % client.name)
        cb = self.remote.callRemote('reloadComponent', client.name)
        cb.addCallback(_reloaded, self, client)
        return cb

    def getUIEntry(self, component):
        self.info('calling remote getUIEntry %s' % component)
        return self.remote.callRemote('getUIEntry', component)
    
gobject.type_register(AdminInterface)

 
