# -*- Mode: Python -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# flumotion/admin/admin.py: model for admin clients
#
# Flumotion - a streaming media server
# Copyright (C) 2004 Fluendo (www.fluendo.com)

# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
# See "LICENSE.GPL" in the source distribution for more information.

# This program is also licensed under the Flumotion license.
# See "LICENSE.Flumotion" in the source distribution for more information.

"""
Model abstraction for admin clients.
The model can support different views.
"""

import os
import sys

import gobject

from twisted.spread import pb
from twisted.internet import error, defer
from twisted.python import rebuild, reflect

from flumotion.common import bundle, errors, interfaces
from flumotion.utils import log, reload
from flumotion.utils.gstutils import gsignal
from flumotion.twisted import cred, pbutil

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
        self.clientFactory = pbutil.FMClientFactory()
        self.debug("logging in to ClientFactory")
        # FIXME: remove old AdminComponent iface before 0.0.1
        d = self.clientFactory.login(cred.Username('admin'), self,
            pb.IPerspective,
            interfaces.IAdminView)
        d.addCallback(self._gotPerspective)
        d.addErrback(self._loginErrback)
        self._components = {} # dict of components

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
        self._components[component.name] = component
        self.emit('update')
        
    def remote_componentRemoved(self, component):
        # FIXME: this asserts, no method, when server dies
        # component will be a RemoteComponentView, so we can only use a
        # member, not a method to get the name
        self.debug('componentRemoved %s' % component.name)
        del self._components[component.name]
        self.emit('update')
        
    def remote_initial(self, components):
        self.debug('remote_initial %s' % components)
        for component in components:
            self._components[component.name] = component
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

        d = defer.execute(reload.reload)

        d = d.addCallback(lambda result, self: self.reloadManager(), self)
        d.addErrback(self._defaultErrback)
        # stack callbacks so that a new one only gets sent after the previous
        # one has completed
        for name in self._components.keys():
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

        @type name: string
        @param name: name of the component to reload.

        @rtype: L{twisted.internet.defer.Deferred}
        """
        def _reloaded(result, self, component):
            self.info("reloaded component %s code" % component.name)

        self.info("reloading component %s code" % name)
        self.emit('reloading', name)
        d = self.remote.callRemote('reloadComponent', name)
        component = self._components[name]
        d.addCallback(_reloaded, self, component)
        d.addErrback(self._defaultErrback)
        return d

    # FIXME: this is the new method to get the UI, by getting a bundle
    # and an entry point
    def getUIZip(self, component, style):
        """
        Get the zip containing the given user interface from the manager.

        @type component: string
        @param component: name of the component to get the user interface for.
        @type style: string
        @param style: style of the UI to get.

        @rtype: deferred
        """
        self.info('calling remote getUIZip %s, %s' % (component, style))
        return self.remote.callRemote('getUIZip', component, style)

    def getUIMD5Sum(self, component, style):
        """
        Get the md5sum of the given user interface from the manager.

        @type component: string
        @param component: name of the component to get the user interface for.
        @type style: string
        @param style: style of the UI to get.

        @rtype: deferred
        """
        self.info('calling remote getUIMD5Sum %s, %s' % (component, style))
        return self.remote.callRemote('getUIMD5Sum', component, style)

    # FIXME: we probably want to return something else than the cache dir,
    # but for now this will do
    def getUI(self, component, style):
        """
        Check if the UI is current enough, and if not, update it.

        @rtype: deferred
        @return: deferred returning the directory where the files are.
        """

        # callback functions
        # FIXME: check if it's ok to return either a deferred or a result    
        def _MD5SumCallback(result, self, component, style):
            md5sum = result
            self.info("received UI MD5 sum")
            self.debug("got UI MD5 sum: %s" % md5sum)
            dir = os.path.join(os.environ['HOME'], '.flumotion', 'cache', md5sum)
            if not os.path.exists(dir):
                d = self.getUIZip(component, style)
                d.addErrback(self._defaultErrback)
                d.addCallback(_ZipCallback, self, component, style)
                return d
            self.debug("UI is in dir %s" % dir)
            return dir

        def _ZipCallback(result, self, component, style):
            # the result is the zip data
            self.info("received UI Zip")
            b = bundle.Bundle()
            b.setZip(result)
            cachedir = os.path.join(os.environ['HOME'], ".flumotion", "cache")
            unbundler = bundle.Unbundler(cachedir)
            dir = unbundler.unbundle(b)
            self.debug("UI is in dir %s" % dir)
            return dir

        self.debug("getting UI MD5 sum")
        d = self.getUIMD5Sum(component, style)
        d.addErrback(self._defaultErrback)
        d.addCallback(_MD5SumCallback, self, component, style)

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
        return self._components
    
gobject.type_register(AdminModel)
