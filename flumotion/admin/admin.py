# -*- Mode: Python -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# flumotion/admin/admin.py: model for admin clients
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

"""
Model abstraction for admin clients.
The model can support different views.
"""

import os
import sys

import gobject

from twisted.spread import pb
from twisted.internet import error, defer
from twisted.cred import error as crederror
from twisted.python import rebuild, reflect

from flumotion.common import bundle, common, errors, interfaces, log, keycards
from flumotion.utils import reload
from flumotion.utils.gstutils import gsignal
from flumotion.twisted import credentials
from flumotion.twisted import pb as fpb

# FIXME: this is a Medium
class AdminModel(pb.Referenceable, gobject.GObject, log.Loggable):
    """
    I live in the admin client.
    I am a data model for any admin view implementing a UI.
    I send signals when things happen.
    I only communicate names of objects to views, not actual objects.
    Manager calls on us through L{flumotion.manager.admin.AdminAvatar}
    """
    gsignal('connected')
    gsignal('disconnected')
    gsignal('connection-refused')
    gsignal('ui-state-changed', str, object)
    gsignal('reloading', str)
    gsignal('update')
    
    logCategory = 'adminmodel'

    __implements__ = interfaces.IAdminMedium,

    def __init__(self, username, password):
        self._components = {} # dict of components
        self._workers = []
        
        self.remote = None

        self.__gobject_init__()
        self.clientFactory = fpb.ReconnectingFPBClientFactory()
        # 20 secs max for an admin to reconnect
        self.clientFactory.maxDelay = 20

        self.debug("logging in to ClientFactory")

        # FIXME: one without address maybe ? or do we want manager to set it ?
        # or do we set our guess and let manager correct ?
        # FIXME: try both, one by one, and possibly others
        #keycard = keycards.KeycardUACPP(username, password, 'localhost')
        keycard = keycards.KeycardUACPCC(username, 'localhost')
        # FIXME: decide on an admin name ?
        keycard.avatarId = "admin"
 
        # start logging in
        self.clientFactory.startLogin(keycard, self, interfaces.IAdminMedium)

        # override gotDeferredLogin so we can add callbacks.
        def gotDeferredLogin(d):
            # add a callback to respond to the challenge
            d.addCallback(self._loginCallback, password)
            d.addCallback(self.setRemoteReference)
            d.addErrback(self._accessDeniedErrback)
            d.addErrback(self._connectionRefusedErrback)
            d.addErrback(self._defaultErrback)

        # if this ever breaks, do real subclassing
        self.clientFactory.gotDeferredLogin = gotDeferredLogin


    ### our methods
    def _loginCallback(self, result, password):
        self.log("_loginCallback(result=%r, password=%s)" % (result, password))
        assert result
        # if we have a reference, we're in
        if isinstance(result, pb.RemoteReference):
            return result
        # else, we need to respond to the challenge
        keycard = result
        keycard.setPassword(password)
        self.log("_loginCallback: responding to challenge")
        d = self.clientFactory.login(keycard, self, interfaces.IAdminMedium)
        return d
        
    def _connectionRefusedErrback(self, failure):
        r = failure.trap(error.ConnectionRefusedError)
        self.debug("emitting connection-refused")
        self.emit('connection-refused')
        self.debug("emitted connection-refused")

    def _accessDeniedErrback(self, failure):
        r = failure.trap(crederror.UnauthorizedLogin)
        # FIXME: unauthorized login emit !
        self.debug("emitting connection-refused")
        self.emit('connection-refused')
        self.debug("emitted connection-refused")

    # default Errback
    def _defaultErrback(self, failure):
        self.debug('Unhandled deferred failure: %r (%s)' % (
            failure.type, failure.getErrorMessage()))
        return failure

    ### IMedium methods
    def setRemoteReference(self, remoteReference):
        self.debug("setRemoteReference: %s" % remoteReference)
        self.remote = remoteReference
        self.remote.notifyOnDisconnect(self._remoteDisconnected)

    def _remoteDisconnected(self, remoteReference):
        self.debug("emitting disconnected")
        self.emit('disconnected')
        self.debug("emitted disconnected")

    def hasRemoteReference(self):
        return self.remote is not None


    ### pb.Referenceable methods
    def remote_log(self, category, type, message):
        self.log('remote: %s: %s: %s' % (type, category, message))
        
    def remote_componentAdded(self, component):
        self.debug('componentAdded %s' % component.name)
        self._components[component.name] = component
        self.emit('update')
        
    def remote_componentStateChanged(self, component, state):
        """
        @param component: component that changed state.
        @param state: new state of component.
        """
        self.debug('componentStateChanged %s' % component.name)
        self._components[component.name] = component
        self.emit('update')
         
    def remote_componentRemoved(self, component):
        # FIXME: this asserts, no method, when server dies
        # component will be a RemoteComponentView, so we can only use a
        # member, not a method to get the name
        self.debug('componentRemoved %s' % component.name)
        del self._components[component.name]
        self.emit('update')
        
    def remote_initial(self, components, workers):
        self.debug('remote_initial(components=%s)' % components)
        for component in components:
            self._components[component.name] = component
        self._workers = workers
        
        self.emit('connected')

    def remote_shutdown(self):
        self.debug('shutting down')

    def remote_uiStateChanged(self, name, state):
        """
        Called when the component's UI needs to be updated with new state.
        Model will emit the 'ui-state-changed' signal.

        @param name: name of component whose state has changed
        @param state: new state of component
        """
        self.emit('ui-state-changed', name, state)
        
    ### model functions
    def reconnect(self):
        self.debug('asked to log in again')
        self.clientFactory.resetDelay()
        #self.clientFactory.retry(self.clientFactory.connector)
        
    def setProperty(self, component, element, property, value):
        if not self.remote:
            self.warning('No remote object')
            return
        return self.remote.callRemote('setComponentElementProperty',
                                      component, element, property, value)

    def getProperty(self, component, element, property):
        return self.remote.callRemote('getComponentElementProperty',
                                      component, element, property)

    # XXX: make this consistent with the newly added worker call remote
    def callComponentRemote(self, component_name, method_name, *args, **kwargs):
        return self.remote.callRemote('callComponentRemote',
                                      component_name, method_name, *args, **kwargs)

    def loadConfiguration(self, xml_string):
        return self.remote.callRemote('loadConfiguration', xml_string)
    
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

    def workerCallRemote(self, workerName, methodName, *args, **kwargs):
        """
        Call the the given method on the given worker with the given args.

        @param workerName: name of the worker to call the method on
        @param methodName: name of method to call; serialized to a
                           remote_methodName on the worker

                           
        @rtype: L{twisted.internet.defer.Deferred}
        """
        r = common.argRepr(args, kwargs, max=20)
        self.debug('calling remote method %s(%s) on worker %s' % (methodName, r,
                                                                 workerName))
        d = self.remote.callRemote('workerCallRemote', workerName,
            methodName, *args, **kwargs)
        d.addErrback(self._workerCallRemoteErrback, methodName)
        return d

    def _workerCallRemoteErrback(self, failure, methodName):
        # XXX: We should have a real error for this, since
        #      AttributeErrors can also happen inside the code we run
        failure.trap(AttributeError)
        self.debug('No remote method "%s"' % methodName)

    ## Worker methods
    def checkElements(self, workerName, elements):
        d = self.workerCallRemote(workerName, 'checkElements', elements)
        d.addErrback(self._defaultErrback)
        return d
    
    def workerRun(self, workerName, function, *args, **kwargs):
        """
        Run the given function and args on the given worker.

        @rtype: L{twisted.internet.defer.Deferred}
        """
        import inspect
        if not callable(function):
            raise TypeError, "need a callable"

        try:
            source = inspect.getsource(function)
        except IOError:
            return defer.fail(errors.FlumotionError('Could not find source'))
        
        functionName = function.__name__
        return self.workerCallRemote(workerName, 'runCode', source,
                                     functionName, *args, **kwargs)
    
    # FIXME: this is the new method to get the UI, by getting a bundle
    # and an entry point
    def getUIZip(self, component, domain, style):
        """
        Get the zip containing the given user interface from the manager.

        @type component: string
        @param component: name of the component to get the user interface for.
        @type style: string
        @param style: style of the UI to get.

        @rtype: deferred
        """
        self.info('calling remote getUIZip %s, %s, %s' % (component, domain, style))
        return self.remote.callRemote('getUIZip', component, domain, style)

    def getUIMD5Sum(self, component, domain, style):
        """
        Get the md5sum of the given user interface from the manager.

        @type component: string
        @param component: name of the component to get the user interface for
        @type domain: string
        @param domain: domain of the UI to get
        @type style: string
        @param style: style of the UI to get

        @rtype: deferred
        """
        self.info('calling remote getUIMD5Sum(%s, %s, %s)' % (
            component, domain, style))
        return self.remote.callRemote('getUIMD5Sum', component, domain, style)

    # FIXME: we probably want to return something else than the cache dir,
    # but for now this will do
    def getUI(self, component, domain, style):
        """
        Check if the UI is current enough, and if not, update it.

        @rtype: deferred
        @return: deferred returning the directory where the files are.
        """

        # callback functions
        # FIXME: check if it's ok to return either a deferred or a result    
        def _MD5SumCallback(result, self, component, domain, style):
            if not result:
                # no UI for this one
                return None
            md5sum = result
            self.info("received UI MD5 sum")
            self.debug("got UI MD5 sum: %s" % md5sum)
            dir = os.path.join(os.environ['HOME'], '.flumotion', 'cache', md5sum)
            if not os.path.exists(dir):
                d = self.getUIZip(component, domain, style)
                d.addErrback(self._defaultErrback)
                d.addCallback(_ZipCallback, self, component, domain, style)
                return d
            self.debug("UI is in dir %s" % dir)
            return dir

        def _ZipCallback(result, self, component, domain, style):
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
        d = self.getUIMD5Sum(component, domain, style)
        d.addErrback(self._defaultErrback)
        d.addCallback(_MD5SumCallback, self, component, domain, style)

        return d
        
    # FIXME: add a second argument to get the type of UI;
    # gtk or http for example
    def getUIEntry(self, component):
        self.info('calling remote getUIEntry %s' % component)
        return self.remote.callRemote('getUIEntry', component)

    def getUIFileList(self, component):
        self.debug('calling remote getUIFileList %s' % component)
        return self.remote.callRemote('getUIFileList', component)

    def cleanComponents(self):
        return self.remote.callRemote('cleanComponents')
        
    # FIXME: this should not be allowed to be called, move away
    # by abstracting callers further
    # returns a dict of name -> component
    def get_components(self):
        return self._components
    getComponents = get_components
    
    def getWorkers(self):
        return self._workers

    
gobject.type_register(AdminModel)
