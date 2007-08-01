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

"""
model abstraction for administration clients supporting different views
"""

import sys

from twisted.spread import pb
from twisted.internet import error, defer, reactor
from twisted.cred import error as crederror
from twisted.python import rebuild, reflect, failure
from zope.interface import implements

from flumotion.common import common, errors, interfaces, log
from flumotion.common import keycards, worker, planet, medium, package
from flumotion.common import messages, signals
# serializable worker and component state
from flumotion.twisted import flavors
from flumotion.twisted.defer import defer_generator_method

from flumotion.configure import configure
from flumotion.common import reload, connection
from flumotion.twisted import credentials
from flumotion.twisted import pb as fpb

from flumotion.common.messages import N_
T_ = messages.gettexter('flumotion')

class AdminClientFactory(fpb.ReconnectingFPBClientFactory):
    perspectiveInterface = interfaces.IAdminMedium

    def __init__(self, medium, extraTenacious=False, maxDelay=20):
        """
        @type medium:   AdminModel
        """
        fpb.ReconnectingFPBClientFactory.__init__(self)
        self.medium = medium
        self.maxDelay = maxDelay

        self.extraTenacious = extraTenacious
        self.hasBeenConnected = 0

    def clientConnectionMade(self, broker):
      self.hasBeenConnected = 1

      fpb.ReconnectingFPBClientFactory.clientConnectionMade(self, broker)

    def clientConnectionFailed(self, connector, reason):
        """
        @param reason: L{twisted.spread.pb.failure.Failure}
        """
        if reason.check(error.DNSLookupError):
            self.debug('DNS lookup error')
            if not self.extraTenacious:
                self.medium.connectionFailed(reason)
            return
        elif (reason.check(error.ConnectionRefusedError)
              or reason.check(error.ConnectError)):
            # If we're logging in for the first time, we want to make this a
            # real error; we present a dialog, etc. 
            # However, if we fail later on (e.g. manager shut down, and 
            # hasn't yet been restarted), we want to keep trying to reconnect,
            # so we just log a message.
            self.debug("Error connecting to %s: %s", connector.getDestination(),
                log.getFailureMessage(reason))
            if self.hasBeenConnected:
                self.log("we've been connected before though, so going "
                         "to retry")
                # fall through
            elif self.extraTenacious:
                self.log("trying again due to +100 tenacity")
                # fall through
            else:
                self.log("telling medium about connection failure")
                self.medium.connectionFailed(reason)
                # return
                return

        fpb.ReconnectingFPBClientFactory.clientConnectionFailed(self, 
            connector, reason)

    # vmethod implementation
    def gotDeferredLogin(self, d):
        yield d

        try:
            try:
                result = d.value()
                assert result
            except Exception, e:
                if self.extraTenacious:
                    self.debug('connection problem: %s', 
                               log.getExceptionMessage(e))
                    self.debug('we are tenacious, so trying again later')
                    self.disconnect()
                    yield None
                else:
                    raise

            self.medium.setRemoteReference(result)

        except errors.ConnectionFailedError:
            self.debug("emitting connection-failed")
            self.medium.emit('connection-failed', "I failed my master")
            self.debug("emitted connection-failed")

        except errors.ConnectionRefusedError:
            self.debug("emitting connection-refused")
            self.medium.emit('connection-refused')
            self.debug("emitted connection-refused")

        except crederror.UnauthorizedLogin:
            # FIXME: unauthorized login emit !
            self.debug("emitting connection-refused")
            self.medium.emit('connection-refused')
            self.debug("emitted connection-refused")

        except Exception, e:
            self.medium.emit('connection-error', e)
            self.medium._defaultErrback(failure.Failure(e))

    gotDeferredLogin = defer_generator_method(gotDeferredLogin)
        
# FIXME: stop using signals, we can provide a richer interface with actual
# objects and real interfaces for the views a model communicates with
class AdminModel(medium.PingingMedium, signals.SignalMixin):
    """
    I live in the admin client.
    I am a data model for any admin view implementing a UI to
    communicate with one manager.
    I send signals when things happen.

    Manager calls on us through L{flumotion.manager.admin.AdminAvatar}
    """
    __signals__ = ('connected', 'disconnected', 'connection-refused',
                   'connection-failed', 'connection-error', 'reloading',
                   'message', 'update')

    logCategory = 'adminmodel'

    implements(interfaces.IAdminMedium, flavors.IStateListener)

    # Public instance variables (read-only)
    planet = None

    def __init__(self):
        # All of these instance variables are private. Cuidado cabrones!
        self.connectionInfo = None
        self.keepTrying = None

        self.managerId = '<uninitialized>'

        self.state = 'disconnected'
        self.clientFactory = None

        self._deferredConnect = None

        self._components = {} # dict of components
        self.planet = None
        self._workerHeavenState = None
        
    def connectToManager(self, connectionInfo, keepTrying=False):
        'Connect to a host.'
        assert self.clientFactory is None

        self.connectionInfo = connectionInfo

        # give the admin an id unique to the manager -- if a program is
        # adminning multiple managers, this id should tell them apart
        # (and identify duplicates)
        self.managerId = str(connectionInfo)

        self.info('Connecting to manager %s with %s',
                  self.managerId, connectionInfo.use_ssl and 'SSL' or 'TCP')

        self.clientFactory = AdminClientFactory(self,
                                                extraTenacious=keepTrying,
                                                maxDelay=20)
        self.clientFactory.startLogin(connectionInfo.authenticator)

        if connectionInfo.use_ssl:
            common.assertSSLAvailable()
            from twisted.internet import ssl
            reactor.connectSSL(connectionInfo.host, connectionInfo.port,
                               self.clientFactory, ssl.ClientContextFactory())
        else:
            reactor.connectTCP(connectionInfo.host, connectionInfo.port,
                               self.clientFactory)

        def connected(model, d):
            # model is really "self". yay gobject?
            d.callback(model)

        def disconnected(model, d):
            # can happen after setRemoteReference but before
            # getPlanetState or getWorkerHeavenState returns
            if not keepTrying:
                d.errback(errors.ConnectionFailedError('Lost connection'))

        def connection_refused(model, d):
            if not keepTrying:
                d.errback(errors.ConnectionRefusedError())

        def connection_failed(model, reason, d):
            if not keepTrying:
                d.errback(errors.ConnectionFailedError(reason))

        def connection_error(model, exception):
            if not keepTrying:
                d.errback(exception)

        d = defer.Deferred()
        ids = []
        ids.append(self.connect('connected', connected, d))
        ids.append(self.connect('disconnected', disconnected, d))
        ids.append(self.connect('connection-refused', connection_refused, d))
        ids.append(self.connect('connection-failed', connection_failed, d))
        ids.append(self.connect('connection-error', connection_error, d))

        def success(model):
            map(self.disconnect, ids)
            self._deferredConnect = None
            return model

        def failure(f):
            map(self.disconnect, ids)
            self._deferredConnect = None
            return f

        d.addCallbacks(success, failure)
        self._deferredConnect = d
        return d

    def shutdown(self):
        self.debug('shutting down')
        if self.clientFactory is not None:
            # order not semantically important, but this way we avoid a
            # "reconnecting in X seconds" in the log
            self.clientFactory.stopTrying()
            self.clientFactory.disconnect()
            self.clientFactory = None

        if self._deferredConnect is not None:
            # this can happen with keepTrying=True
            self.debug('cancelling connection attempt')
            self._deferredConnect.errback(errors.ConnectionCancelledError())

    def reconnect(self, keepTrying=False):
        """Close any existing connection to the manager and
        reconnect."""
        self.debug('asked to log in again')
        self.shutdown()
        return self.connectToManager(self.connectionInfo, keepTrying)

    # default Errback
    # FIXME: we can set it up with a list of types not to warn for ?
    def _defaultErrback(self, failure):
        self.debug('Possibly unhandled deferred failure: %r (%s)' % (
            failure, failure.getErrorMessage()))
        return failure

    # FIXME: give these three sensible names
    def adminInfoStr(self):
        return self.managerId

    def connectionInfoStr(self):
        return '%s:%s (%s)' % (self.connectionInfo.host,
                               self.connectionInfo.port,
                               self.connectionInfo.use_ssl
                               and 'https' or 'http')

    # used in fgc
    def managerInfoStr(self):
        assert self.planet
        return '%s (%s)' % (self.planet.get('name'), self.managerId)

    def connectionFailed(self, failure):
        # called by client factory
        if failure.check(error.DNSLookupError):
            message = ("Could not look up host '%s'."
                       % self.connectionInfo.host)
        elif (failure.check(error.ConnectionRefusedError)
              or failure.check(error.ConnectionRefusedError)):
            message = ("Could not connect to host '%s' on port %d."
                       % (self.connectionInfo.host,
                          self.connectionInfo.port))
        else:
            message = ("Unexpected failure.\nDebug information: %s"
                       % log.getFailureMessage (failure))
        self.debug('emitting connection-failed')
        self.emit('connection-failed', message)
        self.debug('emitted connection-failed')

    def setRemoteReference(self, remoteReference):
        self.debug("setRemoteReference %r" % remoteReference)
        def writeConnection():
            i = self.connectionInfo
            if not (i.authenticator.username
                    and i.authenticator.password):
                self.log('not caching connection information')
                return
            s = ''.join(['<connection>',
                         '<host>%s</host>' % i.host,
                         '<manager>%s</manager>' % self.planet.get('name'),
                         '<port>%d</port>' % i.port,
                         '<use_insecure>%d</use_insecure>'
                         % ((not i.use_ssl) and 1 or 0),
                         '<user>%s</user>' % i.authenticator.username,
                         '<passwd>%s</passwd>' % i.authenticator.password,
                         '</connection>'])
            
            import os
            import md5
            sum = md5.new(s).hexdigest()
            f = os.path.join(configure.registrydir, '%s.connection' % sum)
            try:
                h = open(f, 'w')
                h.write(s)
                h.close()
            except Exception, e:
                self.info('failed to write connection cache file %s: %s',
                          f, log.getExceptionMessage(e))

        # chain up
        medium.PingingMedium.setRemoteReference(self, remoteReference)

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

        d = self.callRemote('getWorkerHeavenState')
        yield d
        self._workerHeavenState = d.value()
        self.debug('got worker state')

        writeConnection()

        self.debug('Connected to manager and retrieved all state')
        self.state = 'connected'
        self.emit('connected')
    setRemoteReference = defer_generator_method(setRemoteReference)

    # IStateListener interface
    def stateSet(self, state, key, value):
        self.debug("state set on %r: key %s" % (state, key))

    def stateAppend(self, state, key, value):
        self.debug("state append on %r: key %s" % (state, key))

        # if a flow gets added to a planet, add ourselves as a listener

    def stateRemove(self, state, key, value):
        self.debug("state remove on %r: key %s" % (state, key))

    ### model functions; called by UI's to send requests to manager or comp

    ## view management functions
    # FIXME: what is this crap ? strings as enums ?
    def isConnected(self):
        return self.state == 'connected'

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
        def errback(failure):
            msg = None
            if failure.check(errors.NoMethodError):
                msg = "Remote method '%s' does not exist." % methodName
                msg += "\n" + failure.value
            else:
                msg = log.getFailureMessage(failure)

            # FIXME: we probably need a nicer way of getting component
            # messages shown from the admin model, but this allows us to
            # make sure every type of admin has these messages
            self.warning(msg)
            m = messages.Warning(T_(N_("Internal error in component.")),
                debug=msg)
            componentState.observe_append('messages', m)
            return failure

        d.addErrback(errback)
        # FIXME: dialog for other errors ?
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
            self.warning("method '%s' on component '%s' does not exist, "
                "component bug" % (methodName, name))
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
    def reloadAdmin(self):
        name = reflect.filenameToModuleName(__file__)

        self.info('Reloading admin code')
        self.debug("rebuilding '%s'" % name)
        rebuild.rebuild(sys.modules[name])
        self.debug("reloading '%s'" % name)
        reload.reload()
        self.info('Reloaded admin code')

    def reload(self):
        # XXX: reload admin.py too
        d = defer.execute(self.reloadAdmin)

        d = d.addCallback(lambda result, self: self.reloadManager(), self)
        d.addErrback(self._defaultErrback)
        # stack callbacks so that a new one only gets sent after the previous
        # one has completed
        for name in self._components.keys():
            d = d.addCallback(lambda result, name: self.reloadComponent(name), name)
            d.addErrback(self._defaultErrback)
        return d

    # used by other admin clients
    # FIXME: isn't it great how hard it is to guess what duckport is ?
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
    # FIXME: still have hard-coded os.path.join stuff in here for md5sum,
    # move to bundleloader ?
    def getEntry(self, componentState, type):
        """
        Do everything needed to set up the entry point for the given
        component and type, including transferring and setting up bundles.

        Caller is responsible for adding errbacks to the deferred.

        Returns: a deferred returning (entryPath, filename, methodName) with
                 entryPath: the full local path to the bundle's base
                 fileName:  the relative location of the bundled file
                methodName: the method to instantiate with
        """
        d = self.callRemote('getEntryByType', componentState, type)
        yield d

        fileName, methodName = d.value()
            
        self.debug("entry for %r of type %s is in file %s and method %s" % (
            componentState, type, fileName, methodName))
        d = self.bundleLoader.getBundles(fileName=fileName)
        yield d

        name, bundlePath = d.value()[-1]
        yield (bundlePath, fileName, methodName)
    getEntry = defer_generator_method(getEntry)

    ## worker remote methods
    def checkElements(self, workerName, elements):
        d = self.workerCallRemote(workerName, 'checkElements', elements)
        d.addErrback(self._defaultErrback)
        return d

    def checkImport(self, workerName, moduleName):
        d = self.workerCallRemote(workerName, 'checkImport', moduleName)
        d.addErrback(self._defaultErrback)
        return d
     
    def workerRun(self, workerName, moduleName, functionName, *args, **kwargs):
        """
        Run the given function and args on the given worker. If the
        worker does not already have the module, or it is out of date,
        it will be retrieved from the manager.

        @rtype: L{twisted.internet.defer.Deferred} firing an
                L{flumotion.common.messages.Result}
        """
        return self.workerCallRemote(workerName, 'runFunction', moduleName,
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
