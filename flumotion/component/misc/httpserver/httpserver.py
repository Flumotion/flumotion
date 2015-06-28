# -*- test-case-name: flumotion.test.test_component_httpserver -*-
# vi:si:et:sw=4:sts=4:ts=4

# Flumotion - a streaming media server
# Copyright (C) 2004,2005,2006,2007,2008,2009 Fluendo, S.L.
# Copyright (C) 2010,2011 Flumotion Services, S.A.
# All rights reserved.
#
# This file may be distributed and/or modified under the terms of
# the GNU Lesser General Public License version 2.1 as published by
# the Free Software Foundation.
# This file is distributed without any warranty; without even the implied
# warranty of merchantability or fitness for a particular purpose.
# See "LICENSE.LGPL" in the source distribution for more information.
#
# Headers in this file shall remain intact.

import os
import string
import time

from twisted.web import server, http
from twisted.web.resource import Resource
from twisted.internet import defer, reactor, error
from twisted.cred import credentials
from zope.interface import implements

from flumotion.common import log, messages, errors, netutils, interfaces
from flumotion.common.i18n import N_, gettexter
from flumotion.component import component
from flumotion.component.base import http as httpbase
from flumotion.component.component import moods
from flumotion.component.misc.httpserver import httpfile, \
        localprovider, localpath
from flumotion.component.misc.httpserver import serverstats
from flumotion.component.misc.porter import porterclient
from flumotion.twisted import fdserver

__version__ = "$Rev$"
T_ = gettexter()

UPTIME_UPDATE_INTERVAL = 5

FILEPROVIDER_SOCKET = 'flumotion.component.misc.httpserver' \
                      '.fileprovider.FileProviderPlug'


class CancellableRequest(server.Request):

    def __init__(self, channel, queued):
        server.Request.__init__(self, channel, queued)
        now = time.time()
        self.lastTimeWritten = now # Used by HTTPFileStreamer for timeout
        # we index some things by the fd, so we need to store it so we
        # can still use it (in the connectionLost() handler and in
        # finish()) after transport's fd has been closed
        self.fd = self.transport.fileno()

        self._component = channel.factory.component
        self._transfer = None
        self._provider = None
        self._startTime = now
        self._completionTime = None
        self._rangeFirstByte = None
        self._rangeLastByte = None
        self._resourceSize = None
        self._bytesWritten = 0L

        # Create the request statistic handler
        self.stats = serverstats.RequestStatistics(self._component.stats)

        self._component.requestStarted(self)

    def setResponseRange(self, first, last, size):
        self._rangeFirstByte = first
        self._rangeLastByte = last
        self._resourceSize = size

    def write(self, data):
        server.Request.write(self, data)
        size = len(data)
        self._bytesWritten += size
        self.lastTimeWritten = time.time()
        # Update statistics
        self.stats.onDataSent(size)

    def finish(self):
        # it can happen that this method will be called with the
        # transport's fd already closed (if the connection is lost
        # early in the request handling)
        server.Request.finish(self)
        # We sent Connection: close, so we must close the connection
        self.transport.loseConnection()
        self.requestCompleted(self.fd)

    def connectionLost(self, reason):
        # this is called _after_ the self.transport.fileno() is not
        # valid anymore, so we use the stored fd number
        server.Request.connectionLost(self, reason)
        self.requestCompleted(self.fd)

    def requestCompleted(self, fd):
        if self._completionTime is None:
            self._completionTime = time.time()
            # Update statistics
            self.stats.onCompleted(self._resourceSize)
            duration = self._completionTime - self._startTime
            self._component.requestFinished(self, self.stats.bytesSent,
                                            duration, fd)

    def getLogFields(self):
        headers = self.getAllHeaders()
        duration = (self._completionTime or time.time()) - self._startTime
        requestFields = {'ip': self.getClientIP(),
                         'method': self.method,
                         'uri': self.uri,
                         'get-parameters': self.args,
                         'clientproto': self.clientproto,
                         'response': self.code,
                         'bytes-sent': self._bytesWritten,
                         'referer': headers.get('referer', None),
                         'user-agent': headers.get('user-agent', None),
                         'time-connected': duration,
                         'resource-size': self._resourceSize,
                         'range-first': self._rangeFirstByte,
                         'range-last': self._rangeLastByte}
        if self._provider:
            # The request fields have higher priority than provider fields
            providerFields = self._provider.getLogFields()
            providerFields.update(requestFields)
            requestFields = providerFields
        return requestFields


class Site(server.Site):
    requestFactory = CancellableRequest

    def __init__(self, resource, component):
        server.Site.__init__(self, resource)

        self.component = component


class StatisticsUpdater(object):
    """
    I wrap a statistics ui state entry, to allow updates.
    """

    def __init__(self, state, key):
        self._state = state
        self._key = key

    def update(self, name, value):
        if value != self._state.get(self._key).get(name, None):
            self._state.setitem(self._key, name, value)


class HTTPFileMedium(component.BaseComponentMedium):

    def __init__(self, comp):
        """
        @type comp: L{HTTPFileStreamer}
        """
        component.BaseComponentMedium.__init__(self, comp)

    def authenticate(self, bouncerName, keycard):
        """
        @rtype: L{twisted.internet.defer.Deferred} firing a keycard or None.
        """
        return self.callRemote('authenticate', bouncerName, keycard)

    def keepAlive(self, bouncerName, issuerName, ttl):
        """
        @rtype: L{twisted.internet.defer.Deferred}
        """
        return self.callRemote('keepAlive', bouncerName, issuerName, ttl)

    def removeKeycardId(self, bouncerName, keycardId):
        """
        @rtype: L{twisted.internet.defer.Deferred}
        """
        return self.callRemote('removeKeycardId', bouncerName, keycardId)

    def remote_expireKeycard(self, keycardId):
        return self.comp.httpauth.expireKeycard(keycardId)

    def remote_expireKeycards(self, keycardId):
        return self.comp.httpauth.expireKeycards(keycardId)

    def remote_getStreamData(self):
        return self.comp.getStreamData()

    def remote_getLoadData(self):
        return self.comp.getLoadData()

    def remote_updatePorterDetails(self, path, username, password):
        return self.comp.updatePorterDetails(path, username, password)

    def remote_rotateLog(self):
        return self.comp.rotateLog()

    def remote_reloadMimeTypes(self):
        self.debug('reloading mime types')
        return localpath.reloadMimeTypes()


class HTTPFileStreamer(component.BaseComponent, log.Loggable):
    implements(interfaces.IStreamingComponent)

    componentMediumClass = HTTPFileMedium

    REQUEST_TIMEOUT = 30 # Time out requests after this many seconds of
                         # inactivity

    def init(self):
        self.mountPoint = None
        self.type = None
        self.port = None
        self.hostname = None
        self.stats = None
        self._rateControlPlug = None
        self._fileProviderPlug = None
        self._metadataProviderPlug = None
        self._loggers = []
        self._requestModifiers = []
        self._logfilter = None
        self.httpauth = None
        self._startTime = time.time()
        self._uptimeCallId = None
        self._allowBrowsing = False

        self._description = 'On-Demand Flumotion Stream'

        self._singleFile = False
        self._connected_clients = {} # fd -> CancellableRequest
        self._total_bytes_written = 0

        self._pbclient = None

        self._twistedPort = None
        self._timeoutRequestsCallLater = None

        self._pendingDisconnects = {}
        self._rootResource = None

        # FIXME: maybe we want to allow the configuration to specify
        # additional mime -> File class mapping ?
        self._mimeToResource = {
            'video/x-flv': httpfile.FLVFile,
            'video/mp4': httpfile.MP4File,
        }

        self.uiState.addKey('stream-url', None)
        self.uiState.addKey('server-uptime', 0)
        self.uiState.addKey('file-provider', None)
        self.uiState.addKey('allow-browsing', False)
        self.uiState.addDictKey('request-statistics')
        self.uiState.addDictKey('provider-statistics')

    def do_check(self):
        props = self.config['properties']
        self.fixRenamedProperties(props, [
            ('issuer', 'issuer-class'),
            ('porter_socket_path', 'porter-socket-path'),
            ('porter_username', 'porter-username'),
            ('porter_password', 'porter-password'),
            ('mount_point', 'mount-point')])

        path = props.get('path', None)
        plugs = self.plugs.get(FILEPROVIDER_SOCKET, [])
        if plugs:
            if path:
                self.warning("The component property 'path' should not be used"
                             " in conjunction with a file provider plug.")
                # For now we don't want the admin to show a warning messages
                #msg = messages.Warning(T_(N_(
                #            "The component property 'path' should not be used"
                #            " in conjunction with a file provider plug.")))
                #self.addMessage(msg)

        if props.get('type', 'master') == 'slave':
            for k in 'socket-path', 'username', 'password':
                if not 'porter-' + k in props:
                    msg = 'slave mode, missing required property porter-%s' % k
                    return defer.fail(errors.ConfigError(msg))
            if plugs or not path:
                return
            if os.path.isfile(path):
                self._singleFile = True
            elif os.path.isdir(path):
                self._singleFile = False
            else:
                msg = "the file or directory specified in 'path': %s does " \
                    "not exist or is neither a file nor directory" % path
                return defer.fail(errors.ConfigError(msg))

    def have_properties(self, props):
        desc = props.get('description', None)
        if desc:
            self._description = desc

        # always make sure the mount point starts with /
        mountPoint = props.get('mount-point', '/')
        if not mountPoint.startswith('/'):
            mountPoint = '/' + mountPoint
        self.mountPoint = mountPoint
        self.hostname = props.get('hostname', None)
        if not self.hostname:
            self.hostname = netutils.guess_public_hostname()

        self.type = props.get('type', 'master')
        self.port = props.get('port', 8801)
        self._allowBrowsing = props.get('allow-browsing', False)
        if self.type == 'slave':
            # already checked for these in do_check
            self._porterPath = props['porter-socket-path']
            self._porterUsername = props['porter-username']
            self._porterPassword = props['porter-password']
        socket = 'flumotion.component.plugs.request.RequestLoggerPlug'
        self._loggers = self.plugs.get(socket, [])
        socket = \
          'flumotion.component.plugs.requestmodifier.RequestModifierPlug'
        self._requestModifiers = self.plugs.get(socket, [])

        self.httpauth = httpbase.HTTPAuthentication(self)
        if 'avatarId' in self.config:
            self.httpauth.setRequesterId(self.config['avatarId'])
        if 'bouncer' in props:
            self.httpauth.setBouncerName(props['bouncer'])
        if 'issuer-class' in props:
            self.warning("The component property 'issuer-class' has been"
                         "deprecated.")
            msg = messages.Warning(T_(N_(
                        "The component property 'issuer-class' has "
                        "been deprecated.")))
            self.addMessage(msg)

        if 'allow-default' in props:
            self.httpauth.setAllowDefault(props['allow-default'])
        if 'ip-filter' in props:
            logFilter = http.LogFilter()
            for f in props['ip-filter']:
                logFilter.addIPFilter(f)
            self._logfilter = logFilter
        socket = \
          'flumotion.component.misc.httpserver.ratecontrol.RateControllerPlug'
        plugs = self.plugs.get(socket, [])
        if plugs:
            # Rate controller factory plug; only one supported.
            self._rateControlPlug = self.plugs[socket][-1]

        plugs = self.plugs.get(FILEPROVIDER_SOCKET, [])
        if plugs:
            # FileProvider factory plug; only one supported.
            self._fileProviderPlug = plugs[-1]
        else:
            # Create a default local provider using path property
            # Delegate the property checks to the plug
            plugProps = {"properties": {"path": props.get('path', None)}}
            self._fileProviderPlug = localprovider.FileProviderLocalPlug(
                plugProps)

        socket = ('flumotion.component.misc.httpserver'
                 '.metadataprovider.MetadataProviderPlug')
        plugs = self.plugs.get(socket, [])
        if plugs:
            self._metadataProviderPlug = plugs[-1]

        # Update uiState
        self.uiState.set('stream-url', self.getUrl())
        self.uiState.set('allow-browsing', self._allowBrowsing)

    def do_setup(self):
        self.have_properties(self.config['properties'])

        root = self._rootResource
        if root is None:
            root = self._getDefaultRootResource()

        if root is None:
            raise errors.WrongStateError(
                "a resource or path property must be set")

        site = Site(root, self)
        self._timeoutRequestsCallLater = reactor.callLater(
            self.REQUEST_TIMEOUT, self._timeoutRequests)

        # Create statistics handler and start updating ui state
        self.stats = serverstats.ServerStatistics()
        updater = StatisticsUpdater(self.uiState, "request-statistics")
        self.stats.startUpdates(updater)
        updater = StatisticsUpdater(self.uiState, "provider-statistics")
        self._fileProviderPlug.startStatsUpdates(updater)
        self._updateUptime()

        d = defer.Deferred()
        if self.type == 'slave':
            # Streamer is slaved to a porter.
            if self._singleFile:
                self._pbclient = porterclient.HTTPPorterClientFactory(
                    site, [self.mountPoint], d)
            else:
                self._pbclient = porterclient.HTTPPorterClientFactory(
                    site, [], d,
                    prefixes=[self.mountPoint])
            creds = credentials.UsernamePassword(self._porterUsername,
                self._porterPassword)
            self._pbclient.startLogin(creds, self._pbclient.medium)
            self.info("Logging to porter on socketPath %s", self._porterPath)
            # This will eventually cause d to fire
            c = fdserver.FDConnector(self._porterPath,
                self._pbclient, 10, checkPID=False, reactor=reactor)
            c.connect()
        else:
            # File Streamer is standalone.
            try:
                self.debug('Going to listen on port %d' % self.port)
                iface = ""
                # we could be listening on port 0, in which case we need
                # to figure out the actual port we listen on
                self._twistedPort = reactor.listenTCP(self.port,
                    site, interface=iface)
                self.port = self._twistedPort.getHost().port
                self.info('Listening on interface %r on port %d',
                          iface, self.port)
            except error.CannotListenError:
                t = 'Port %d is not available.' % self.port
                self.warning(t)
                m = messages.Error(T_(N_(
                    "Network error: TCP port %d is not available."),
                                      self.port))
                self.addMessage(m)
                self.setMood(moods.sad)
                return defer.fail(errors.ComponentSetupHandledError(t))
            # fire callback so component gets happy
            d.callback(None)
        # we are responsible for setting component happy

        def setComponentHappy(result):
            self.httpauth.scheduleKeepAlive()
            self.setMood(moods.happy)
            return result
        d.addCallback(setComponentHappy)
        return d

    def do_stop(self):
        if self.stats:
            self.stats.stopUpdates()
        if self._fileProviderPlug:
            self._fileProviderPlug.stopStatsUpdates()
        if self.httpauth:
            self.httpauth.stopKeepAlive()
        if self._timeoutRequestsCallLater:
            self._timeoutRequestsCallLater.cancel()
            self._timeoutRequestsCallLater = None
        if self._uptimeCallId:
            self._uptimeCallId.cancel()
            self._uptimeCallId = None
        if self._twistedPort:
            self._twistedPort.stopListening()

        l = [self.remove_all_clients()]
        if self.type == 'slave' and self._pbclient:
            if self._singleFile:
                l.append(self._pbclient.deregisterPath(self.mountPoint))
            else:
                l.append(self._pbclient.deregisterPrefix(self.mountPoint))
        return defer.DeferredList(l)

    def updatePorterDetails(self, path, username, password):
        """
        Provide a new set of porter login information, for when we're in slave
        mode and the porter changes.
        If we're currently connected, this won't disconnect - it'll just change
        the information so that next time we try and connect we'll use the
        new ones
        @param path: new path
        @param username: new username
        @param password: new password
        """
        if self.type != 'slave':
            raise errors.WrongStateError(
                "Can't specify porter details in master mode")

        self._porterUsername = username
        self._porterPassword = password

        creds = credentials.UsernamePassword(self._porterUsername,
                                             self._porterPassword)
        self._pbclient.startLogin(creds, self.medium)

        self._updatePath(path)

    def _updatePath(self, path):
        # If we've changed paths, we must do some extra work.
        if path == self._porterPath:
            return
        self._porterPath = path

        # Stop trying to connect with the old connector.
        self._pbclient.stopTrying()

        self._pbclient.resetDelay()
        c = fdserver.FDConnector(self._porterPath, self._pbclient, 10,
            checkPID=False, reactor=reactor)
        c.connect()

    def _timeoutRequests(self):
        self._timeoutRequestsCallLater = None

        now = time.time()
        for request in self._connected_clients.values():
            if now - request.lastTimeWritten > self.REQUEST_TIMEOUT:
                self.debug("Timing out connection on request for [fd %5d]",
                    request.fd)
                # Apparently this is private API. However, calling
                # loseConnection is not sufficient - it won't drop the
                # connection until the send queue is empty, which might never
                # happen for an uncooperative client
                request.channel.transport.connectionLost(
                    errors.TimeoutException())

        # FIXME: ideally, we shouldn't create another callLater if the
        # component is shutting down, to leave the environment clean
        # and tidy (right now, let's hope the process will be stopped
        # eventually anyway)
        self._timeoutRequestsCallLater = reactor.callLater(
            self.REQUEST_TIMEOUT, self._timeoutRequests)

    def _getDefaultRootResource(self):
        node = self._fileProviderPlug.getRootPath()
        if node is None:
            return None

        self.debug('Starting with mount point "%s"' % self.mountPoint)
        factory = httpfile.MimedFileFactory(self.httpauth,
            mimeToResource=self._mimeToResource,
            rateController=self._rateControlPlug,
            requestModifiers=self._requestModifiers,
            metadataProvider=self._metadataProviderPlug)

        root = factory.create(node)
        if self.mountPoint != '/':
            root = self._createRootResourceForPath(self.mountPoint, root)

        return root

    def _createRootResourceForPath(self, path, fileResource):
        if path.endswith('/'):
            path = path[:-1]

        root = Resource()
        children = string.split(path[1:], '/')
        parent = root
        for child in children[:-1]:
            resource = Resource()
            self.debug("Putting Resource at %s", child)
            parent.putChild(child, resource)
            parent = resource
        self.debug("Putting resource %r at %r", fileResource, children[-1])
        parent.putChild(children[-1], fileResource)
        return root

    def remove_client(self, fd):
        """
        Remove a client when requested.

        Used by keycard expiry.
        """
        if fd in self._connected_clients:
            request = self._connected_clients[fd]
            self.debug("Removing client for fd %d", fd)
            request.unregisterProducer()
            request.channel.transport.loseConnection()
        else:
            self.debug("No client with fd %d found", fd)

    def remove_all_clients(self):
        l = []
        for fd in self._connected_clients:
            d = defer.Deferred()
            self._pendingDisconnects[fd] = d
            l.append(d)

            request = self._connected_clients[fd]
            request.unregisterProducer()
            request.channel.transport.loseConnection()

        self.debug("Waiting for %d clients to finish", len(l))
        return defer.DeferredList(l)

    def requestStarted(self, request):
        # request does not yet have proto and uri
        fd = request.transport.fileno() # ugly!
        self._connected_clients[fd] = request
        self.debug("[fd %5d] (ts %f) request %r started",
                   fd, time.time(), request)

    def requestFinished(self, request, bytesWritten, timeConnected, fd):

        # PROBE: finishing request; see httpstreamer.resources
        self.debug('[fd %5d] (ts %f) finishing request %r',
                   request.transport.fileno(), time.time(), request)

        self.httpauth.cleanupAuth(fd)
        ip = request.getClientIP()
        if not self._logfilter or not self._logfilter.isInRange(ip):
            fields = request.getLogFields()
            fields.update({'time': time.gmtime(),
                           'username': '-'}) # FIXME: put the httpauth name
            l = []
            for logger in self._loggers:
                l.append(defer.maybeDeferred(
                    logger.event, 'http_session_completed', fields))
            d = defer.DeferredList(l)
        else:
            d = defer.succeed(None)

        del self._connected_clients[fd]

        self._total_bytes_written += bytesWritten

        def firePendingDisconnect(_):
            self.debug("Logging completed")
            if fd in self._pendingDisconnects:
                pending = self._pendingDisconnects.pop(fd)
                self.debug("Firing pending disconnect deferred")
                pending.callback(None)

            # PROBE: finished request; see httpstreamer.resources
            self.debug('[fd %5d] (ts %f) finished request %r',
                       fd, time.time(), request)

        d.addCallback(firePendingDisconnect)

    def getDescription(self):
        return self._description

    def getUrl(self):
        port = self.port

        if self.type == 'slave' and self._pbclient:
            if not self._pbclient.remote_port:
                return ""
            port = self._pbclient.remote_port

        if (not port) or (port == 80):
            port_str = ""
        else:
            port_str = ":%d" % port

        return "http://%s%s%s" % (self.hostname, port_str, self.mountPoint)

    def getStreamData(self):
        socket = 'flumotion.component.plugs.streamdata.StreamDataProviderPlug'
        if socket in self.plugs:
            plug = self.plugs[socket][-1]
            return plug.getStreamData()
        else:
            return {'protocol': 'HTTP',
                    'description': self._description,
                    'url': self.getUrl()}

    def getClients(self):
        """
        Return the number of connected clients
        """
        return len(self._connected_clients)

    def getBytesSent(self):
        """
        Current Bandwidth
        """
        bytesTransferred = self._total_bytes_written
        for request in self._connected_clients.values():
            if request._transfer:
                bytesTransferred += request._transfer.bytesWritten
        return bytesTransferred

    def getLoadData(self):
        """
        Return a tuple (deltaadded, deltaremoved, bytes_transferred,
        current_clients, current_load) of our current bandwidth and
        user values. The deltas and current_load are NOT currently
        implemented here, we set them as zero.
        """
        return (0, 0, self.getBytesSent(), self.getClients(), 0)

    def rotateLog(self):
        """
        Close the logfile, then reopen using the previous logfilename
        """
        for logger in self._loggers:
            self.debug('rotating logger %r' % logger)
            logger.rotate()

    def setRootResource(self, resource):
        """Attaches a root resource to this component. The root resource is the
        once which will be used when accessing the mount point.
        This is normally called from a plugs start() method.
        @param resource: root resource
        @type resource: L{twisted.web.resource.Resource}
        """
        rootResource = self._createRootResourceForPath(
            self.getMountPoint(), resource)

        self._rootResource = rootResource

    def getMountPoint(self):
        """Get the mount point of this component
        @returns: the mount point
        """
        # This is called early, before do_setup()
        return self.config['properties'].get('mount-point')

    def _updateUptime(self):
        uptime = time.time() - self._startTime
        self.uiState.set("server-uptime", uptime)
        self._uptimeCallId = reactor.callLater(UPTIME_UPDATE_INTERVAL,
                                               self._updateUptime)
