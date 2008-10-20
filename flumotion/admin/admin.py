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

from twisted.internet import error, defer, reactor
from zope.interface import implements

from flumotion.common import common, errors, interfaces, log
from flumotion.common import medium
from flumotion.common import messages, signals
from flumotion.common import planet, worker # register jelly
from flumotion.common.i18n import N_, gettexter
from flumotion.configure import configure
from flumotion.twisted import pb as fpb

__version__ = "$Rev$"
T_ = gettexter()


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

        self._connector = None

    def startedConnecting(self, connector):
        self._connector = connector
        return fpb.ReconnectingFPBClientFactory.startedConnecting(
            self, connector)

    def clientConnectionMade(self, broker):
        self.hasBeenConnected = 1

        fpb.ReconnectingFPBClientFactory.clientConnectionMade(self, broker)

    def clientConnectionFailed(self, connector, reason):
        """
        @type  connector: implementation of
                          L{twisted.internet.interfaces.IConnector}
        @param reason:    L{twisted.spread.pb.failure.Failure}
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
            self.debug("Error connecting to %s: %s",
                       connector.getDestination(),
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

        def success(remote):
            self.medium.setRemoteReference(remote)

        def error(failure):
            if self.extraTenacious:
                self.debug('connection problem to %s: %s',
                    self._connector.getDestination(),
                    log.getFailureMessage(failure))
                self.debug('we are tenacious, so trying again later')
                self.disconnect()
            elif failure.check(errors.ConnectionFailedError):
                self.debug("emitting connection-failed")
                self.medium.emit('connection-failed', "I failed my master")
                self.debug("emitted connection-failed")
            elif failure.check(errors.ConnectionRefusedError):
                self.debug("emitting connection-refused")
                self.medium.emit('connection-refused')
                self.debug("emitted connection-refused")
            elif failure.check(errors.NotAuthenticatedError):
                # FIXME: unauthorized login emit !
                self.debug("emitting connection-refused")
                self.medium.emit('connection-refused')
                self.debug("emitted connection-refused")
            else:
                self.medium.emit('connection-error', failure)
                self.warning('connection error to %s:: %s',
                    self._connector.getDestination(),
                    log.getFailureMessage(failure))
            # swallow error

        d.addCallbacks(success, error)
        return d

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

    implements(interfaces.IAdminMedium)

    # Public instance variables (read-only)
    planet = None

    def __init__(self):
        # All of these instance variables are private. Cuidado cabrones!
        self.connectionInfo = None
        self.keepTrying = None
        self._writeConnection = True

        self.managerId = '<uninitialized>'

        self.connected = False
        self.clientFactory = None

        self._deferredConnect = None

        self._components = {} # dict of components
        self.planet = None
        self._workerHeavenState = None

    def disconnectFromManager(self):
        """
        Disconnects from the actual manager and frees the connection.
        """
        if self.clientFactory:
            # We are disconnecting, so we don't want to be
            # notified by the model about it.
            self.remote.dontNotifyOnDisconnect(self._remoteDisconnected)

            self.clientFactory.stopTrying()

            self.clientFactory.disconnect()
            self.clientFactory = None

    def connectToManager(self, connectionInfo, keepTrying=False,
                         writeConnection=True):
        """
        Connects to the specified manager.

        @param connectionInfo:  data for establishing the connection
        @type  connectionInfo:  a L{PBConnectionInfo}
        @param keepTrying:      when this is L{True} the Factory will try to
                                reconnect when it loses the connection
        @type  keepTrying:      bool
        @param writeConnection: when this is L{True} the connection is saved
                                for future uses on cache
        @type  writeConnection: bool

        @rtype: L{twisted.internet.defer.Deferred}
        """
        assert self.clientFactory is None

        self.connectionInfo = connectionInfo
        self._writeConnection = writeConnection

        # give the admin an id unique to the manager -- if a program is
        # adminning multiple managers, this id should tell them apart
        # (and identify duplicates)
        self.managerId = str(connectionInfo)
        self.logName = self.managerId

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

        def connection_error(model, failure, d):
            if not keepTrying:
                d.errback(failure)

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

    def bundleErrback(self, failure, fileName='<unknown>'):
        """
        Handle all coding mistakes that could be triggered by loading bundles.
        This is a convenience method to help in properly reporting problems.
        The EntrySyntaxError should be caught and wrapped in a UI message,
        with the message generated here as debug information.

        @param failure: the failure to be handled
        @type  failure: L{twisted.python.failure.Failure}
        @param filename: name of the file being loaded
        @type  filename: str

        @raises: L{errors.EntrySyntaxError}
        """
        try:
            raise failure.value
        except SyntaxError, e:
            # the syntax error can happen in the entry file, or any import
            where = getattr(e, 'filename', "<entry file>")
            lineno = getattr(e, 'lineno', 0)
            msg = "Syntax Error at %s:%d while executing %s" % (
                where, lineno, fileName)
            self.warning(msg)
            raise errors.EntrySyntaxError(msg)
        except NameError, e:
            msg = "NameError while executing %s: %s" % (
                fileName, " ".join(e.args))
            self.warning(msg)
            raise errors.EntrySyntaxError(msg)
        except ImportError, e:
            msg = "ImportError while executing %s: %s" % (fileName,
                " ".join(e.args))
            self.warning(msg)
            raise errors.EntrySyntaxError(msg)

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
        elif failure.check(error.ConnectionRefusedError):
            message = ("Could not connect to host '%s' on port %d."
                       % (self.connectionInfo.host,
                          self.connectionInfo.port))
        else:
            message = ("Unexpected failure.\nDebug information: %s"
                       % log.getFailureMessage(failure))
        self.debug('emitting connection-failed')
        self.emit('connection-failed', message)
        self.debug('emitted connection-failed')

    def setRemoteReference(self, remoteReference):
        self.debug("setRemoteReference %r", remoteReference)

        def gotPlanetState(planet):
            self.planet = planet
            # monkey, Monkey, MONKEYPATCH!!!!!
            self.planet.admin = self
            self.debug('got planet state')
            return self.callRemote('getWorkerHeavenState')

        def gotWorkerHeavenState(whs):
            self._workerHeavenState = whs
            self.debug('got worker state')

            self.debug('Connected to manager and retrieved all state')
            self.connected = True
            if self._writeConnection:
                writeConnection()
            self.emit('connected')

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
            md5sum = md5.new(s).hexdigest()
            f = os.path.join(configure.registrydir, '%s.connection' % md5sum)
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

        self.remote.notifyOnDisconnect(self._remoteDisconnected)

        d = self.callRemote('getPlanetState')
        d.addCallback(gotPlanetState)
        d.addCallback(gotWorkerHeavenState)
        return d

    ### model functions; called by UI's to send requests to manager or comp

    ## view management functions

    def isConnected(self):
        return self.connected

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
        d = self.callRemote('componentCallRemote',
                            componentState, methodName,
                            *args, **kwargs)

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

    def workerCallRemote(self, workerName, methodName, *args, **kwargs):
        """
        Call the the given method on the given worker with the given args.

        @param workerName: name of the worker to call the method on
        @param methodName: name of method to call; serialized to a
                           remote_methodName on the worker's medium

        @rtype: L{twisted.internet.defer.Deferred}
        """
        return self.callRemote('workerCallRemote', workerName,
                               methodName, *args, **kwargs)

    ## manager remote methods

    def loadConfiguration(self, xml_string):
        return self.callRemote('loadConfiguration', xml_string)

    def getConfiguration(self):
        return self.callRemote('getConfiguration')

    def cleanComponents(self):
        return self.callRemote('cleanComponents')

    ## worker remote methods

    def checkElements(self, workerName, elements):
        return self.workerCallRemote(workerName, 'checkElements', elements)

    def checkImport(self, workerName, moduleName):
        return self.workerCallRemote(workerName, 'checkImport', moduleName)

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

    def getWizardEntries(self, wizardTypes=None, provides=None, accepts=None):
        return self.callRemote('getWizardEntries',
                               wizardTypes, provides, accepts)

    def getWorkerHeavenState(self):
        return self._workerHeavenState

    def _remoteDisconnected(self, remoteReference):
        self.debug("emitting disconnected")
        self.connected = False
        self.emit('disconnected')
        self.debug("emitted disconnected")
