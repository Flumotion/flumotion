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
model abstraction for administration clients supporting different views
"""

import os
import sys

import gobject

from twisted.spread import pb
from twisted.internet import error, defer
from twisted.cred import error as crederror
from twisted.python import rebuild, reflect

from flumotion.common import bundle, common, errors, interfaces, log, keycards
from flumotion.configure import configure
from flumotion.utils import reload
from flumotion.utils.gstutils import gsignal
from flumotion.twisted import credentials
from flumotion.twisted import pb as fpb

# FIXME: this is a Medium
class AdminModel(pb.Referenceable, gobject.GObject, log.Loggable):
    """
    I live in the admin client.
    I am a data model for any admin view implementing a UI to
    communicate with one manager.
    I send signals when things happen.
    I only communicate names of objects to views, not actual objects.

    Manager calls on us through L{flumotion.manager.admin.AdminAvatar}
    """
    gsignal('connected')
    gsignal('disconnected')
    gsignal('connection-refused')
    gsignal('ui-state-changed', str, object)
    gsignal('component-property-changed', str, str, object)
    gsignal('reloading', str)
    gsignal('update')
    
    logCategory = 'adminmodel'

    __implements__ = interfaces.IAdminMedium,

    # appease pychecker
    _components = {}
    clientFactory = None

    def __init__(self, username, password):
        self._components = {} # dict of components
        self._workers = []
        
        self.remote = None

        self._views = [] # all UI views I am serving
        self._unbundler = bundle.Unbundler(configure.cachedir)

        self.clientFactory = fpb.ReconnectingFPBClientFactory()
        self.__gobject_init__()
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
        failure.trap(error.ConnectionRefusedError)
        self.debug("emitting connection-refused")
        self.emit('connection-refused')
        self.debug("emitted connection-refused")

    def _accessDeniedErrback(self, failure):
        failure.trap(crederror.UnauthorizedLogin)
        # FIXME: unauthorized login emit !
        self.debug("emitting connection-refused")
        self.emit('connection-refused')
        self.debug("emitted connection-refused")

    # default Errback
    def _defaultErrback(self, failure):
        self.debug('Unhandled deferred failure: %r (%s)' % (
            failure.type, failure.getErrorMessage()))
        return failure

    def reconnect(self):
        self.debug('asked to log in again')
        self.clientFactory.resetDelay()
        #self.clientFactory.retry(self.clientFactory.connector)

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
        
    def remote_componentCall(self, componentName, methodName, *args, **kwargs):
        for view in self._views:
            view.componentCall(componentName, methodName, *args, **kwargs)

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

    ### model functions; called by UI's to send requests to manager or comp

    ## view management functions
    def addView(self, view):
        # FIXME: implement an IAdminView interface
        """
        Add a view as a client to the model.
        """
        if not view in self._views:
            self._views.append(view)

    def removeView(self, view):
        # FIXME: implement an IAdminView interface
        """
        Remove a view as a client to the model.
        """
        if view in self._views:
            self._views.remove(view)
        
    ## generic remote call methods
    def callRemote(self, methodName, *args, **kwargs):
        """
        Call the given remote method on the manager-side AdminAvatar.
        """
        if not self.remote:
            raise errors.ManagerNotConnectedError
        return self.remote.callRemote(methodName, *args, **kwargs)

    def componentCallRemote(self, componentName, methodName, *args, **kwargs):
        """
        Call the the given method on the given component with the given args.

        @param componentName: name of the component to call the method on
        @param methodName:    name of method to call; serialized to a
                              remote_methodName on the worker's medium
                           
        @rtype: L{twisted.internet.defer.Deferred}
        """
        self.debug('Calling remote method %s on component %s' % (
            methodName, componentName))
        d = self.callRemote('componentCallRemote',
                            componentName, methodName,
                            *args, **kwargs)
        d.addErrback(self._callRemoteErrback, "component",
                     componentName, methodName)
        return d

    def workerCallRemote(self, workerName, methodName, *args, **kwargs):
        """
        Call the the given method on the given worker with the given args.

        @param workerName: name of the worker to call the method on
        @param methodName: name of method to call; serialized to a
                           remote_methodName on the worker's medium
                           
        @rtype: L{twisted.internet.defer.Deferred}
        """
        r = common.argRepr(args, kwargs, max=20)
        self.debug('calling remote method %s(%s) on worker %s' % (methodName, r,
                                                                 workerName))
        d = self.callRemote('workerCallRemote', workerName,
                            methodName, *args, **kwargs)
        d.addErrback(self._callRemoteErrback, "worker",
                     workerName, methodName)
        return d

    def _callRemoteErrback(self, failure, type, name, methodName):
        if failure.check(errors.NoMethodError):
            self.warning("method %s on %s does not exist, component bug" % (
                methodName, name))
        else:
            self.debug("unhandled failure on remote call to %s(%s): %r" % (
                name, methodName, failure))

        # FIXME: throw up some sort of dialog with debug info
        return failure

    ## component remote methods
    def setProperty(self, component, element, property, value):
        return self.componentCallRemote('setElementProperty',
                                        element, property, value)

    def getProperty(self, component, element, property):
        return self.componentCallRemote('getElementProperty',
                                        component, element, property)

    ## reload methods for everything
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

    ## manager remote methods
    def loadConfiguration(self, xml_string):
        return self.remote.callRemote('loadConfiguration', xml_string)

    def cleanComponents(self):
        return self.remote.callRemote('cleanComponents')

    # function to get remote code for admin parts
    # FIXME: rename slightly ?
    def getEntry(self, componentName, type):
        """
        Do everything needed to set up the entry point for the given
        component and type, including transferring and setting up bundles.

        Returns: a deferred returning (entryPath, filename, methodName)
        """
        
        def _getEntryCallback(result, componentName, type):
            # callback for getting the entry.  Will request bundle sums
            # based on filename given to me
            self.debug('_getEntryCallback: result %r' % (result, ))

            filename, methodName = result
            self.debug("entry point for %s of type %s is in file %s and method %s" % (componentName, type, filename, methodName))
            # request bundle sums
            d = self.callRemote('getBundleSumsByFile', filename)
            d.addCallback(_getBundleSumsCallback, filename, methodName)
            d.addErrback(self._defaultErrback)
            return d

        def _getBundleSumsCallback(result, filename, methodName):
            # callback receiving bundle sums.  Will remote call to get
            # all missing zip files
            sums = result # ordered from highest to lowest dependency
            entryName, entrySum = sums[0]
            self.debug('_getBundleSumsCallback: %d sums received' % len(sums))

            # get path where entry bundle is stored
            entryPath = self._unbundler.unbundlePathByInfo(entryName, entrySum)

            # check which zips to request from manager
            cachedPaths = [] # list of cached paths to register later
            missing = [] # list of missing bundles

            for name, sum in sums:
                dir = os.path.join(configure.cachedir, sum)
                cachedPaths.append(dir)
                if not os.path.exists(dir):
                    missing.append(name)

            cachedPaths.reverse()
            missing.reverse()

            if missing:
                self.debug('_getBundleSumsCallback: requesting zips %r' %
                    missing)
                d = self.callRemote('getBundleZips', missing)
                d.addCallback(_getBundleZipsCallback, entryPath, missing,
                    cachedPaths, filename, methodName)
                d.addErrback(self._defaultErrback)
                return d
            else:
                retval = (entryPath, filename, methodName)
                self.debug('_getBundleSumsCallback: returning %r' % (
                    retval, ))
                self._registerCachedPaths(cachedPaths)
                return retval

        def _getBundleZipsCallback(result, entryPath, missing, cachedPaths,
            filename, methodName):
            # callback to receive zips.  Will set up zips, register package
            # paths and finally
            # return physical location of entry file and method
            self.debug('_getBundleZipsCallback: received %d zips' % len(result))
            # we use missing because that way we get the
            # list of dependencies from lowest to highest and register
            # package paths in the correct order; since we need to
            # register package paths one by one for the namedAny's
            # FIXME: missing can contain duplicate entries, remove ?
            for name in missing:
                if name not in result.keys():
                    msg = "Missing bundle %s was not received" % name
                    self.warning(msg)
                    raise errors.NoBundleError(msg)

                zip = result[name]
                b = bundle.Bundle(name)
                b.setZip(zip)
                dir = self._unbundler.unbundle(b)
                self.debug("unpacked bundle %s to dir %s" % (name, dir))
                self.debug("unpacked bundle %s, registering PackagePath %s" % (
                    dir, name))
                common.registerPackagePath(dir)

            # now make sure all cachedPaths are registered
            # FIXME: does it matter we already did some before ?
            self._registerCachedPaths(cachedPaths)

            retval = (entryPath, filename, methodName)
            self.debug('_getBundleSumsCallback: returning %r' % (
                retval, ))
            return retval

        # start chain
        d = self.callRemote('getEntryByType', componentName, type)
        d.addCallback(_getEntryCallback, componentName, type)
        d.addErrback(self._defaultErrback)
        return d

    def _registerCachedPaths(self, paths):
        for dir in paths:
            common.registerPackagePath(dir)

    def getBundledFile(self, bundledPath):
        """
        Do everything needed to get the given bundled file.

        Returns: a deferred returning the absolute path to a local copy
        of the given file.
        """
        def _getBundleSumsCallback(result, bundledPath):
            # callback receiving bundle sums.  Will remote call to get
            # the zip if it's missing
            sums = result
            bundleName, bundleSum = sums[0]
            self.debug('bundledPath %s is in bundle %s' % (bundledPath,
                bundleName))

            # get path where this bundle is cached
            cachePath = self._unbundler.unbundlePathByInfo(bundleName,
                bundleSum)

            if not os.path.exists(cachePath):
                self.debug('_getBundleSumsCallback: requesting zip %s' %
                    bundleName)
                d = self.callRemote('getBundleZips', (bundleName, ))
                d.addCallback(_getBundleZipsCallback, bundleName, bundledPath)
                d.addErrback(self._defaultErrback)
                self.debug("found %s in dir %s" % (bundleName, cachePath))
                return d
            else:
                return os.path.join(cachePath, bundledPath)

        def _getBundleZipsCallback(result, bundleName, bundledPath):
            # callback to receive zip.  Will set up zips and finally
            # return physical location of bundledPath
            self.debug('_getBundleZipsCallback: received %d zips' % len(result))
            zip = result[bundleName]
            b = bundle.Bundle()
            b.setZip(zip)
            dir = self._unbundler.unbundle(b)
            self.debug("unpacked %s to dir %s" % (name, dir))

            return os.path.join(dir, bundledPath)

        # start chain
        d = self.callRemote('getBundleSumsByFile', bundledPath)
        d.addCallback(_getBundleSumsCallback, bundledPath)
        d.addErrback(self._defaultErrback)
        return d

    ## worker remote methods
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
    
    # FIXME: this should not be allowed to be called, move away
    # by abstracting callers further
    # returns a dict of name -> component
    def get_components(self):
        return self._components
    getComponents = get_components
    
    def getWorkers(self):
        return self._workers

gobject.type_register(AdminModel)
