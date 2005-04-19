# -*- Mode: Python -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# Flumotion - a streaming media server
# Copyright (C) 2004,2005 Fluendo, S.L. (www.fluendo.com). All rights reserved.

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
import md5

import gobject

from twisted.spread import pb
from twisted.internet import error, defer, reactor
from twisted.cred import error as crederror
from twisted.python import rebuild, reflect

from flumotion.common import bundle, common, errors, interfaces, log
from flumotion.common import keycards, worker, planet, medium
# serializable worker and component state
from flumotion.twisted import flavors
from flumotion.twisted.defer import defer_generator_method

from flumotion.configure import configure
from flumotion.common import reload
from flumotion.twisted import credentials
from flumotion.twisted import pb as fpb

from flumotion.common.pygobject import gsignal, gproperty


class AdminClientFactory(fpb.ReconnectingFPBClientFactory):
    def __init__(self, medium, user, passwd):
        fpb.ReconnectingFPBClientFactory.__init__(self)

        self.user = user
        self.passwd = passwd
        self.medium = medium
        self.maxDelay = 20

        # FIXME: try more than one auth method
        #keycard = keycards.KeycardUACPP(user, passwd, 'localhost')
        keycard = keycards.KeycardUACPCC(user, 'localhost')
        # FIXME: decide on an admin name ?
        keycard.avatarId = "admin"
 
        # start logging in
        self.startLogin(keycard, medium, interfaces.IAdminMedium)

    # vmethod implementation
    def gotDeferredLogin(self, d):
        yield d

        try:
            result = d.value()
            assert result
            # if it's not a reference, we need to respond to a
            # challenge...
            if not isinstance(result, pb.RemoteReference):
                keycard = result
                keycard.setPassword(self.passwd)
                self.log("_loginCallback: responding to challenge")
                d = self.login(keycard, self.medium, interfaces.IAdminMedium)
                yield d
                result = d.value()

            self.medium.setRemoteReference(result)

        except error.ConnectionRefusedError:
            self.debug("emitting connection-refused")
            self.medium.emit('connection-refused')
            self.debug("emitted connection-refused")

        except crederror.UnauthorizedLogin:
            # FIXME: unauthorized login emit !
            self.debug("emitting connection-refused")
            self.medium.emit('connection-refused')
            self.debug("emitted connection-refused")

        except Exception, e:
            self.medium._defaultErrback(e)

    gotDeferredLogin = defer_generator_method(gotDeferredLogin)
        
# FIXME: stop using signals, we can provide a richer interface with actual
# objects and real interfaces for the views a model communicates with
class AdminModel(medium.BaseMedium, gobject.GObject):
    """
    I live in the admin client.
    I am a data model for any admin view implementing a UI to
    communicate with one manager.
    I send signals when things happen.

    Manager calls on us through L{flumotion.manager.admin.AdminAvatar}
    """
    gsignal('connected')
    gsignal('disconnected')
    gsignal('connection-refused')
    gsignal('ui-state-changed', str, object)
    gsignal('component-property-changed', str, str, object)
    gsignal('reloading', str)
    gsignal('message', str)
    gsignal('update')

    logCategory = 'adminmodel'

    __implements__ = interfaces.IAdminMedium, flavors.IStateListener,

    # Public instance variables (read-only)
    planet = None

    def __init__(self, username, password):
        self.__gobject_init__()
        
        # All of these instance variables are private. Cuidado cabrones!
        self.user = username
        self.passwd = password
        self.host = self.port = self.use_insecure = None

        self.state = 'disconnected'
        self.clientFactory = AdminClientFactory(self, username, password)
        # 20 secs max for an admin to reconnect
        self.clientFactory.maxDelay = 20

        self._components = {} # dict of components
        self.planet = None
        self._workerHeavenState = None
        
        self._views = [] # all UI views I am serving

        self._unbundler = bundle.Unbundler(configure.cachedir)

    def connectToHost(self, host, port, use_insecure=False):
        'Connect to a host.'
        self.host = host
        self.port = port
        self.use_insecure = use_insecure

        if use_insecure:
            self.info('Connecting to manager %s:%d with TCP' % (host, port))
            reactor.connectTCP(host, port, self.clientFactory)
        else:
            from twisted.internet import ssl
            self.info('Connecting to manager %s:%d with SSL' % (host, port))
            reactor.connectSSL(host, port, self.clientFactory,
                               ssl.ClientContextFactory())

    # default Errback
    def _defaultErrback(self, failure):
        self.debug('Unhandled deferred failure: %r (%s)' % (
            failure.type, failure.getErrorMessage()))
        return failure

    def reconnect(self):
        self.debug('asked to log in again')
        self.clientFactory.resetDelay()
        #self.clientFactory.retry(self.clientFactory.connector)

    def connectionInfoStr(self):
        return '%s:%s (%s)' % (self.host, self.port,
                               self.use_insecure and 'http' or 'https')

    def managerInfoStr(self):
        assert self.planet
        return '%s (%s:%s)' % (self.planet.get('name'), self.host, self.port)

    def setRemoteReference(self, remoteReference):
        def writeConnection():
            s = ''.join(['<connection>',
                         '<host>%s</host>' % self.host,
                         '<manager>%s</manager>' % self.planet.get('name'),
                         '<port>%d</port>' % self.port,
                         '<use_insecure>%d</use_insecure>' 
                         % (self.use_insecure and 1 or 0),
                         '<user>%s</user>' % self.user,
                         '<passwd>%s</passwd>' % self.passwd,
                         '</connection>'])
            
            sum = md5.new(s).hexdigest()
            f = os.path.join(configure.registrydir, '%s.connection' % sum)
            h = open(f, 'w')
            h.write(s)
            h.close()

        # chain up
        medium.BaseMedium.setRemoteReference(self, remoteReference)

        # fixme: push the disconnect notification upstream
        def remoteDisconnected(remoteReference):
            self.debug("emitting disconnected")
            self.state = 'disconnected'
            self.emit('disconnected')
            self.debug("emitted disconnected")
        self.remote.notifyOnDisconnect(remoteDisconnected)

        d = self.callRemote('getPlanetState')
        yield d
        self.planet = d.value()
        # monkey, Monkey, MONKEYPATCH!!!!!
        self.planet.admin = self
        self.debug('got planet state')
        self.callViews('setPlanetState', self.planet)

        d = self.callRemote('getWorkerHeavenState')
        yield d
        self._workerHeavenState = d.value()
        self.debug('got worker state')
        
        writeConnection()
        self.debug('Connected to manager and retrieved all state')
        self.state = 'connected'
        self.emit('connected')
    setRemoteReference = defer_generator_method(setRemoteReference)

    def callViews(self, methodName, *args, **kwargs):
        """
        Call a method on all views.
        """
        for view in self._views:
            if not hasattr(view, methodName):
                msg = 'view %r does not implement %s' % (view, methodName)
                self.warning(msg)
                raise errors.NoMethodError(msg)
            m = getattr(view, methodName)
            m(*args, **kwargs)

    ### pb.Referenceable methods
    def remote_log(self, category, type, message):
        self.log('remote: %s: %s: %s' % (type, category, message))
        
    def remote_componentCall(self, componentState, methodName, *args, **kwargs):
        self.callViews('componentCall',
            componentState, methodName, *args, **kwargs)

    # IStateListener interface
    def stateSet(self, state, key, value):
        self.debug("state set on %r: key %s" % (state, key))

    def stateAppend(self, state, key, value):
        self.debug("state append on %r: key %s" % (state, key))

        # if a flow gets added to a planet, add ourselves as a listener

    def stateRemove(self, state, key, value):
        self.debug("state remove on %r: key %s" % (state, key))

    def remote_shutdown(self):
        self.debug('shutting down')

    ### model functions; called by UI's to send requests to manager or comp

    ## view management functions
    # FIXME: what is this crap ? strings as enums ?
    def isConnected(self):
        return self.state == 'connected'

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
    def componentCallRemote(self, componentState, methodName, *args, **kwargs):
        """
        Call the given method on the given component with the given args.

        @param componentState: component to call the method on
        @type  componentState: L{flumotion.common.planet.AdminComponentState}
        @param methodName:     name of method to call; serialized to a
                               remote_methodName on the worker's medium
                           
        @rtype: L{twisted.internet.defer.Deferred}
        """
        assert isinstance(componentState, planet.AdminComponentState), \
            "componentState %r is of the wrong type calling %s" % (
                componentState, methodName)
        componentName = componentState.get('name')

        self.debug('Calling remote method %s on component %s' % (
            methodName, componentName))
        d = self.callRemote('componentCallRemote',
                            componentState, methodName,
                            *args, **kwargs)
        d.addCallback(self._callRemoteCallback, methodName, componentName)
        d.addErrback(self._callRemoteErrback, "component",
                     componentName, methodName)
        return d

    def _callRemoteCallback(self, result, methodName, componentName):
        self.debug('Called remote method %s on component %s successfully' % (
            methodName, componentName))
        return result
    
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
            self.debug("passing through failure on remote call to %s(%s): %r" %
                (name, methodName, failure))

        # FIXME: throw up some sort of dialog with debug info
        return failure

    ## component remote methods
    def setProperty(self, componentState, element, property, value):
        """
        @type  componentState: L{flumotion.common.planet.AdminComponentState}
        """
        return self.componentCallRemote(componentState, 'setElementProperty',
                                        element, property, value)

    def getProperty(self, componentState, element, property):
        """
        @type  componentState: L{flumotion.common.planet.AdminComponentState}
        """
        return self.componentCallRemote(componentState, 'getElementProperty',
                                        element, property)

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

    def reload_async(self, duckport):
        name = reflect.filenameToModuleName(__file__)

        self.info("rebuilding '%s'" % name)
        rebuild.rebuild(sys.modules[name])

        d = self.reloadManager()
        yield d
        try:
            d.value()
            duckport.write('Reloaded manager')
        except Exception, e:
            duckport.write('Failed to reload manager: %s' % e)

        for name in self._components.keys():
            d = self.reloadComponent(name)
            yield d
            try:
                d.value()
                duckport.write('Reloaded component %s' % name)
            except Exception, e:
                duckport.write('Failed to reload component %s: %s' % (name, e))
        duckport.close()
    reload_async = defer_generator_method(reload_async)

    def reloadManager(self):
        """
        Tell the manager to reload its code.

        @rtype: deferred
        """
        def _reloaded(result, self):
            self.info("reloaded manager code")

        self.emit('reloading', 'manager')
        self.info("reloading manager code")
        d = self.callRemote('reloadManager')
        d.addCallback(_reloaded, self)
        d.addErrback(self._defaultErrback)
        return d

    def reloadComponent(self, componentState):
        """
        Tell the manager to reload code for a component.

        @type  componentState: L{flumotion.common.planet.AdminComponentState}

        @rtype: L{twisted.internet.defer.Deferred}
        """
        def _reloaded(result, self, state):
            self.info("reloaded component %s code" % state.get('name'))

        name = componentState.get('name')
        self.info("reloading component %s code" % name)
        self.emit('reloading', name)
        d = self.callRemote('reloadComponent', componentState)
        d.addCallback(_reloaded, self, componentState)
        d.addErrback(self._defaultErrback)
        return d

    ## manager remote methods
    def loadConfiguration(self, xml_string):
        return self.callRemote('loadConfiguration', xml_string)

    def getConfiguration(self):
        return self.callRemote('getConfiguration')

    def cleanComponents(self):
        return self.callRemote('cleanComponents')

    # function to get remote code for admin parts
    # FIXME: rename slightly ?
    def getEntry(self, componentState, type):
        """
        Do everything needed to set up the entry point for the given
        component and type, including transferring and setting up bundles.

        Caller is responsible for adding errbacks to the deferred.

        Returns: a deferred returning (entryPath, filename, methodName)
        """
        
        def _getEntryCallback(result, componentState, type):
            # callback for getting the entry.  Will request bundle sums
            # based on filename given to me
            self.debug('_getEntryCallback: result %r' % (result, ))

            filename, methodName = result
            self.debug("entry point for %r of type %s is in file %s and method %s" % (componentState, type, filename, methodName))
            # request bundle sums
            d = self.callRemote('getBundleSums', filename=filename)
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
                dir = os.path.join(configure.cachedir, name, sum)
                if not os.path.exists(dir):
                    missing.append(name)
                else:
                    cachedPaths.append(dir)

            cachedPaths.reverse()
            missing.reverse()

            self.debug('_getBundleSumsCallback: %d bundles missing' %
                len(missing))
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
            unpacked = []
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
                unpacked.append(dir)

            # now make sure all cachedPaths are registered
            # FIXME: does it matter we already did some before ?
            self._registerCachedPaths(cachedPaths)

            # and now register our new contestants
            for dir in unpacked:
                self.debug("register PackagePath %s for unpacked bundle %s" % (
                    dir, name))
                common.registerPackagePath(dir)

            retval = (entryPath, filename, methodName)
            self.debug('_getBundleSumsCallback: returning %r' % (
                retval, ))
            return retval

        # start chain
        d = self.callRemote('getEntryByType', componentState, type)
        d.addCallback(_getEntryCallback, componentState, type)
        # our caller should handle errbacks
        # d.addErrback(self._defaultErrback)
        return d

    def _registerCachedPaths(self, paths):
        for dir in paths:
            self.debug("registering cached PackagePath %s" % dir)
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
            self.debug("unpacked %s to dir %s" % (bundleName, dir))

            return os.path.join(dir, bundledPath)

        # start chain
        d = self.callRemote('getBundleSums', filename=bundledPath)
        d.addCallback(_getBundleSumsCallback, bundledPath)
        d.addErrback(self._defaultErrback)
        return d

    ## worker remote methods
    def checkElements(self, workerName, elements):
        d = self.workerCallRemote(workerName, 'checkElements', elements)
        d.addErrback(self._defaultErrback)
        return d
    
    def workerRun(self, workerName, moduleName, functionName, *args, **kwargs):
        """
        Run the given function and args on the given worker. If the
        worker does not already have the module, or it is out of date,
        it will be retrieved from the manager.

        @rtype: L{twisted.internet.defer.Deferred}
        """
        return self.workerCallRemote(workerName, 'runProc', moduleName,
                                     functionName, *args, **kwargs)
    
    # FIXME: this should not be allowed to be called, move away
    # by abstracting callers further
    def get_components(self):
        # returns a dict of name -> component
        return self._components
    getComponents = get_components
    
    def _setWorkerHeavenState(self, state):
        self._workerHeavenState = state

    def getWorkerHeavenState(self):
        return self._workerHeavenState

gobject.type_register(AdminModel)
