# -*- test-case-name: flumotion.test.test_component_httpserver -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# Flumotion - a streaming media server
# Copyright (C) 2004,2005,2006,2007,2008 Fluendo, S.L. (www.fluendo.com).
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
from flumotion.component.misc.httpserver import httpfile
from flumotion.component.misc.porter import porterclient
from flumotion.twisted import fdserver

__version__ = "$Rev$"
T_ = gettexter()


class CancellableRequest(server.Request):

    def __init__(self, channel, queued):
        server.Request.__init__(self, channel, queued)

        self._component = channel.factory.component
        self._completed = False
        self._transfer = None

        self._bytes_written = 0
        self._start_time = time.time()
        self._lastTimeWritten = self._start_time

        # we index some things by the fd, so we need to store it so we
        # can still use it (in the connectionLost() handler and in
        # finish()) after transport's fd has been closed
        self._fd = self.transport.fileno()

        self._component.requestStarted(self)

    def write(self, data):
        server.Request.write(self, data)

        self._bytes_written += len(data)
        self._lastTimeWritten = time.time()

    def finish(self):
        # it can happen that this method will be called with the
        # transport's fd already closed (if the connection is lost
        # early in the request handling)
        server.Request.finish(self)
        # We sent Connection: close, so we must close the connection
        self.transport.loseConnection()
        self.requestCompleted(self._fd)

    def connectionLost(self, reason):
        # this is called _after_ the self.transport.fileno() is not
        # valid anymore, so we use the stored fd number
        server.Request.connectionLost(self, reason)
        self.requestCompleted(self._fd)

    def requestCompleted(self, fd):
        if not self._completed:
            self._component.requestFinished(self, self._bytes_written,
                time.time() - self._start_time, fd)
            self._completed = True


class Site(server.Site):
    requestFactory = CancellableRequest

    def __init__(self, resource, component):
        server.Site.__init__(self, resource)

        self.component = component


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

    def remote_getStreamData(self):
        return self.comp.getStreamData()

    def remote_getLoadData(self):
        return self.comp.getLoadData()

    def remote_updatePorterDetails(self, path, username, password):
        return self.comp.updatePorterDetails(path, username, password)

    def remote_rotateLog(self):
        return self.comp.rotateLog()


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
        self._rateControlPlug = None
        self._loggers = []
        self._logfilter = None
        self.httpauth = None

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
        }

        # store number of connected clients
        self.uiState.addKey("connected-clients", 0)
        self.uiState.addKey("bytes-transferred", 0)
        self.uiState.addKey('stream-url', None)

    def do_check(self):
        props = self.config['properties']
        self.fixRenamedProperties(props, [
            ('issuer', 'issuer-class'),
            ('porter_socket_path', 'porter-socket-path'),
            ('porter_username', 'porter-username'),
            ('porter_password', 'porter-password'),
            ('mount_point', 'mount-point')])

        if props.get('type', 'master') == 'slave':
            for k in 'socket-path', 'username', 'password':
                if not 'porter-' + k in props:
                    msg = 'slave mode, missing required property porter-%s' % k
                    return defer.fail(errors.ConfigError(msg))

            path = props.get('path', None)
            if path is None:
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

        self.filePath = props.get('path')
        self.type = props.get('type', 'master')
        self.port = props.get('port', 8801)
        if self.type == 'slave':
            # already checked for these in do_check
            self._porterPath = props['porter-socket-path']
            self._porterUsername = props['porter-username']
            self._porterPassword = props['porter-password']
        self._loggers = \
            self.plugs.get('flumotion.component.plugs.loggers.Logger', [])

        self.httpauth = httpbase.HTTPAuthentication(self)
        if 'bouncer' in props:
            self.httpauth.setBouncerName(props['bouncer'])
        if 'issuer-class' in props:
            self.httpauth.setIssuerClass(props['issuer-class'])
        if 'ip-filter' in props:
            logFilter = http.LogFilter()
            for f in props['ip-filter']:
                logFilter.addIPFilter(f)
            self._logfilter = logFilter

        socket = ('flumotion.component.misc.'
                  'httpserver.ratecontroller.RateController')
        plugs = self.plugs.get(socket, [])
        if plugs:
            # Rate controller factory plug; only one supported.
            self._rateControlPlug = self.plugs[socket][-1]

        # Update uiState
        self.uiState.set('stream-url', self.getUrl())

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
            self.debug("Starting porter login!")
            # This will eventually cause d to fire
            reactor.connectWith(fdserver.FDConnector, self._porterPath,
                self._pbclient, 10, checkPID=False)
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
                self.debug('Listening on port %d' % self.port)
            except error.CannotListenError:
                t = 'Port %d is not available.' % self.port
                self.warning(t)
                m = messages.Error(T_(N_(
                    "Network error: TCP port %d is not available."),
                                      self.port))
                self.addMessage(m)
                self.setMood(moods.sad)
                return defer.fail(errors.ComponentStartHandledError(t))
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
        if self.httpauth:
            self.httpauth.stopKeepAlive()
        if self._timeoutRequestsCallLater:
            self._timeoutRequestsCallLater.cancel()
            self._timeoutRequestsCallLater = None
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
        reactor.connectWith(fdserver.FDConnector, self._porterPath,
                            self._pbclient, 10, checkPID=False)

    def _timeoutRequests(self):
        now = time.time()
        for request in self._connected_clients.values():
            if now - request._lastTimeWritten > self.REQUEST_TIMEOUT:
                self.debug("Timing out connection")
                # Apparently this is private API. However, calling
                # loseConnection is not sufficient - it won't drop the
                # connection until the send queue is empty, which might never
                # happen for an uncooperative client
                request.channel.transport.connectionLost(
                    errors.TimeoutException())

        self._timeoutRequestsCallLater = reactor.callLater(
            self.REQUEST_TIMEOUT, self._timeoutRequests)

    def _getDefaultRootResource(self):
        if self.filePath is None:
            return None

        self.debug('Starting with mount point "%s"' % self.mountPoint)
        factory = httpfile.MimedFileFactory(self.httpauth,
            mimeToResource=self._mimeToResource,
            rateController=self._rateControlPlug)

        root = factory.create(self.filePath)
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
        fd = request.transport.fileno() # ugly!
        self._connected_clients[fd] = request
        self.uiState.set("connected-clients", len(self._connected_clients))

    def requestFinished(self, request, bytesWritten, timeConnected, fd):
        self.httpauth.cleanupAuth(fd)
        headers = request.getAllHeaders()

        ip = request.getClientIP()
        if not self._logfilter or not self._logfilter.isInRange(ip):
            args = {'ip': ip,
                    'time': time.gmtime(),
                    'method': request.method,
                    'uri': request.uri,
                    'username': '-', # FIXME: put the httpauth name
                    'get-parameters': request.args,
                    'clientproto': request.clientproto,
                    'response': request.code,
                    'bytes-sent': bytesWritten,
                    'referer': headers.get('referer', None),
                    'user-agent': headers.get('user-agent', None),
                    'time-connected': timeConnected}

            l = []
            for logger in self._loggers:
                l.append(defer.maybeDeferred(
                    logger.event, 'http_session_completed', args))
            d = defer.DeferredList(l)
        else:
            d = defer.succeed(None)

        del self._connected_clients[fd]

        self.uiState.set("connected-clients", len(self._connected_clients))

        self._total_bytes_written += bytesWritten
        self.uiState.set("bytes-transferred", self._total_bytes_written)

        def firePendingDisconnect(_):
            self.debug("Logging completed")
            if fd in self._pendingDisconnects:
                pending = self._pendingDisconnects.pop(fd)
                self.debug("Firing pending disconnect deferred")
                pending.callback(None)
        d.addCallback(firePendingDisconnect)

    def getDescription(self):
        return self._description

    def getUrl(self):
        return "http://%s:%d%s" % (self.hostname, self.port, self.mountPoint)

    def getStreamData(self):
        socket = 'flumotion.component.plugs.streamdata.StreamDataProvider'
        if self.plugs[socket]:
            plug = self.plugs[socket][-1]
            return plug.getStreamData()
        else:
            return {'protocol': 'HTTP',
                    'description': self._description,
                    'url': self.getUrl()}

    def getLoadData(self):
        """
        Return a tuple (deltaadded, deltaremoved, bytes_transferred,
        current_clients, current_load) of our current bandwidth and
        user values. The deltas and current_load are NOT currently
        implemented here, we set them as zero.
        """
        bytesTransferred = self._total_bytes_written
        for request in self._connected_clients.values():
            if request._transfer:
                bytesTransferred += request._transfer.bytesWritten

        return (0, 0, bytesTransferred, len(self._connected_clients), 0)

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
