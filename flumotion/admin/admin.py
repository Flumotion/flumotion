# -*- Mode: Python -*-
# vi:si:et:sw=4:sts=4:ts=4

# Flumotion - a video streaming server
# Copyright (C) 2004 Fluendo
#
# admin/admin.py: model for admin clients
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
from twisted.internet import error, defer
from twisted.python import rebuild, reflect

from flumotion.common import interfaces, errors
from flumotion.utils import log, reload
from flumotion.utils.gstutils import gsignal
from flumotion.twisted import pbutil

class AdminModel(pb.Referenceable, gobject.GObject, log.Loggable):
    """
    I live in the admin client.
    I am a data model for any admin view implementing a UI.
    I send signals when things happen.
    I only communicate names of objects to views, not actual objects.
    Manager calls on us through L{flumotion.manager.admin.AdminAvatar}
    """
    gsignal('connected')
    gsignal('connection-refused')
    gsignal('ui-state-changed', str, object)
    gsignal('reloading', str)
    gsignal('update')
    
    logCategory = 'adminmodel'

    def __init__(self):
        self.__gobject_init__()
        self.factory = pbutil.FMClientFactory()
        self.debug("logging in to ClientFactory")
        d = self.factory.login(pbutil.Username('admin'), self,
                               pb.IPerspective,
                               interfaces.IAdminComponent)
        d.addCallback(self._gotPerspective)
        d.addErrback(self._loginErrback)
        self.components = {} # dict of components

    def _gotPerspective(self, perspective):
        self.debug("gotPerspective: %s" % perspective)
        self.remote = perspective

    def _loginErrback(self, failure):
        r = failure.trap(error.ConnectionRefusedError)
        self.debug("emitting connection-refused")
        self.emit('connection-refused')
        self.debug("emitted connection-refused")

    # default Errback
    def _defaultErrback(self, failure):
        self.debug('received failure: %s' % failure.getErrorMessage())
        return failure

    ### pb.Referenceable methods
    def remote_log(self, category, type, message):
        self.log('remote: %s: %s: %s' % (type, category, message))
        
    def remote_componentAdded(self, component):
        self.debug('componentAdded %s' % component.name)
        self.components[component.name] = component
        self.emit('update')
        
    def remote_componentRemoved(self, component):
        # FIXME: this asserts, no method, when server dies
        # component will be a RemoteComponentView, so we can only use a
        # member, not a method to get the name
        self.debug('componentRemoved %s' % component.name)
        del self.components[component.name]
        self.emit('update')
        
    def remote_initial(self, components):
        self.debug('remote_initial %s' % components)
        for component in components:
            self.components[component.name] = component
        self.emit('connected')

    def remote_shutdown(self):
        self.debug('shutting down')

    def remote_uiStateChanged(self, name, state):
        """
        Called when the component's UI needs to be updated with new state.
        Model will emit the 'ui-state-changed' signal.

        @param name: name of component whose state has changed.
        @param state: new state of component.
        """
        self.emit('ui-state-changed', name, state)
        
    ### model functions
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

        self.info("rebuilding '%s'" % name)
        rebuild.rebuild(sys.modules[name])

        d = defer.execute(reload)

        d = d.addCallback(lambda result, self: self.reloadManager(), self)
        d.addErrback(self._defaultErrback)
        # stack callbacks so that a new one only gets sent after the previous
        # one has completed
        for name in self.components.keys():
            d = d.addCallback(lambda result, name: self.reloadComponent(name), name)
            d.addErrback(self._defaultErrback)
        return d

    def reloadManager(self):
        """
        Tell the manager to reload its code.

        @rtype: deferred
        """
        def _reloaded(result, self):
            self.info("reloaded manager code")

        self.emit('reloading', 'manager')
        self.info("reloading manager code")
        d = self.remote.callRemote('reloadManager')
        d.addCallback(_reloaded, self)
        d.addErrback(self._defaultErrback)
        return d

    def reloadComponent(self, name):
        """
        Tell the manager to reload code for a component.

        @type component: string
        @param component: name of the component to reload.

        @rtype: deferred
        """
        def _reloaded(result, self, component):
            self.info("reloaded component %s code" % component.name)

        self.info("reloading component %s code" % name)
        self.emit('reloading', name)
        d = self.remote.callRemote('reloadComponent', name)
        component = self.components[name]
        d.addCallback(_reloaded, self, component)
        d.addErrback(self._defaultErrback)
        return d

    # FIXME: add a second argument to get the type of UI;
    # gtk or http for example
    def getUIEntry(self, component):
        self.info('calling remote getUIEntry %s' % component)
        return self.remote.callRemote('getUIEntry', component)

    def getUIFileList(self, component):
        self.debug('calling remote getUIFileList %s' % component)
        return self.remote.callRemote('getUIFileList', component)

    # FIXME: this should not be allowed to be called, move away
    # by abstracting callers further
    # returns a dict of name -> component
    def get_components(self):
        return self.components
    
gobject.type_register(AdminModel)
