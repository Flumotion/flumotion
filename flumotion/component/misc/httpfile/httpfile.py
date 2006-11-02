# -*- Mode: Python -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# Flumotion - a streaming media server
# Copyright (C) 2004,2005,2006 Fluendo, S.L. (www.fluendo.com).
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
import time
import string

from flumotion.component import component
from flumotion.common import log, messages, errors, netutils
from flumotion.component.component import moods
from flumotion.component.misc.porter import porterclient
from flumotion.component.base import http as httpbase
from twisted.web import resource, static, server, http
from twisted.web import error as weberror
from twisted.internet import defer, reactor, error
from flumotion.twisted import fdserver
from twisted.cred import credentials

from flumotion.common.messages import N_
T_ = messages.gettexter('flumotion')

# FIXME: argggggh, how hard is it to *document* a class or at least give
# a passing hint on *why* it gets created so someone has at least a
# fighting chance to fix problems with it ?
class RequestWrapper:
    request = None
    def __init__(self, request, finished):
        self.__dict__['request'] = request
        self.__dict__['__written'] = 0
        self.__dict__['__start_time'] = time.time()
        self.__dict__['__finished'] = finished

        # The HTTPChannel has a reference to the actual request object, and
        # we need to override connectionLost for incomplete requests. Be evil.
        request.connectionLost = self.connectionLost

    def __getattr__(self, key):
        return getattr(self.request, key)

    def __setattr__(self, key, val):
        if key in self.__dict__:
            self.__dict__[key] = val
        else:
            setattr(self.request, key, val)

    def write(self, data):
        self.__dict__['__written'] += len(data)
        return self.request.write(data)
        
    def finish(self):
        # We sent Connection: close, so honour that and actually close the
        # connection. That should cause connectionLost to be called, from where
        # we will then log the request.
        self.transport.loseConnection()
        self.__dict__['__finished'](self.request,
                                    self.__dict__['__written'],
                                    time.time() -
                                    self.__dict__['__start_time'])
        return self.request.finish()

    def connectionLost(self, reason):
        self.__dict__['__finished'](self.request,
                                    self.__dict__['__written'],
                                    time.time() -
                                    self.__dict__['__start_time'])

class File(static.File, log.Loggable):
    __pychecker__ = 'no-objattrs'

    def __init__(self, path, requestStarted, requestFinished, component):
        static.File.__init__(self, path)
        self._requestStarted = requestStarted
        self._requestFinished = requestFinished
        self.component = component

    def render(self, request):
        def terminateSimpleRequest(res, request):
            if res != server.NOT_DONE_YET:
                request.finish()

        rapper = RequestWrapper(request, self._requestFinished)
        self._requestStarted(rapper)

        d = self.component.startAuthentication(rapper)
        d.addCallback(self.renderAuthenticated, rapper)
        d.addCallback(terminateSimpleRequest, rapper)

        return server.NOT_DONE_YET

    def renderAuthenticated(self, res, request):
        """ 
        Now that we're authenticated (or authentication wasn't requested), 
        write the file (or appropriate other response) to the client.
        We override static.File to implement Range requests, and to get access
        to the transfer object to abort it later; the bulk of this is a direct
        copy, though.
        """
        self.restat()

        if self.type is None:
            self.type, self.encoding = static.getTypeAndEncoding(
                self.basename(), self.contentTypes, self.contentEncodings, 
                self.defaultType)

        if not self.exists():
            self.debug("Couldn't find resource %s", self.basename())
            return self.childNotFound.render(request)

        if self.isdir():
            return self.redirect(request)

        # Different headers not normally set in static.File...        
        # Specify that the client should close the connection; further 
        # requests on this server might actually go to a different process 
        # because of the porter
        request.setHeader('Connection', 'close')
        # We can do range requests, in bytes.
        request.setHeader('Accept-Ranges', 'bytes')

        if self.type:
            request.setHeader('content-type', self.type)
        if self.encoding:
            request.setHeader('content-encoding', self.encoding)

        try:
            f = self.openForReading()
        except IOError, e:
            import errno
            if e[0] == errno.EACCES:
                return weberror.ForbiddenResource().render(request)
            else:
                raise

        if request.setLastModified(self.getmtime()) is http.CACHED:
            return ''

        tsize = fsize = size = self.getFileSize()
        range = request.getHeader('range')
        start = 0
        if range is not None:
            # TODO: Add a unit test - or several - for this stuff.
            # We have a partial-data request...
            # Some variables... we start at byte offset 'start', end at byte 
            # offset 'end'. fsize is the number of bytes we're sending. tsize 
            # is the total size of the file. 'size' is the byte offset we will
            # stop at, plus 1.
            bytesrange = string.split(range, '=')
            if len(bytesrange) != 2:
                request.setResponseCode(http.REQUESTED_RANGE_NOT_SATISFIABLE)
                return ''

            start, end = string.split(bytesrange[1], '-', 1)
            if start:
                start = int(start)
                f.seek(start)
                if end:
                    end = int(end)
                else:
                    end = size - 1
                fsize = end - start + 1
            elif end:
                lastbytes = int(end)
                if size < lastbytes:
                    lastbytes = size
                start = size - lastbytes
                f.seek(start)
                fsize = lastbytes
                end = size - 1
            else:
                request.setResponseCode(http.REQUESTED_RANGE_NOT_SATISFIABLE)
                return ''
            size = end + 1

            request.setResponseCode(http.PARTIAL_CONTENT)
            request.setHeader('Content-Range', "bytes %d-%d/%d" % 
                (start, end, tsize))

        request.setHeader("Content-Length", str(fsize))

        if request.method == 'HEAD':
             return ''
           
        self.transfer = static.FileTransfer(f, size, request)
        self.component.addFileTransfer(request, start, self.transfer)

        return server.NOT_DONE_YET

    def directoryListing(self):
        # disallow directory listings
        return self.childNotFound

    def createSimilarFile(self, path):
        self.debug("createSimilarFile at %r", path)
        f = self.__class__(path, self._requestStarted, 
            self._requestFinished, self.component)
        f.processors = self.processors
        f.indexNames = self.indexNames[:]
        f.childNotFound = self.childNotFound
        return f

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

    def removeKeycardId(self, bouncerName, keycardId):
        """
        @rtype: L{twisted.internet.defer.Deferred}
        """
        return self.callRemote('removeKeycardId', bouncerName, keycardId)

    def remote_getStreamData(self):
        return self.comp.getStreamData()

    def remote_getLoadData(self):
        return self.comp.getLoadData()

    def remote_updatePorterDetails(self, path, username, password):
        return self.comp.updatePorterDetails(path, username, password)

class HTTPFileStreamer(component.BaseComponent, httpbase.HTTPAuthentication, 
    log.Loggable):

    componentMediumClass = HTTPFileMedium

    def __init__(self):
       component.BaseComponent.__init__(self)
       httpbase.HTTPAuthentication.__init__(self, self)

    def init(self):
        self.mountPoint = None
        self.type = None
        self.port = None
        self.hostname = None
        self.loggers = []

        self._singleFile = False
        self._connected_clients = 0
        self._total_bytes_written = 0
        self._transfersInProgress = {} # {request->(offset, FileTransfer)}

    def do_setup(self):
        props = self.config['properties']
        mountPoint = props.get('mount_point', '')
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
            self._porterPath = props['porter_socket_path']
            self._porterUsername = props['porter_username']
            self._porterPassword = props['porter_password']
        self.loggers = \
            self.plugs['flumotion.component.plugs.loggers.Logger']

        if 'bouncer' in props:
            self.setBouncerName(props['bouncer'])
        if 'issuer' in props:
            self.setIssuerClass(props['issuer'])
        
    def do_stop(self):
        if self.type == 'slave':
            return self._pbclient.deregisterPath(self.mountPoint)
        return component.BaseComponent.do_stop(self)

    def updatePorterDetails(self, path, username, password):
        """
        Provide a new set of porter login information, for when we're in slave
        mode and the porter changes.
        If we're currently connected, this won't disconnect - it'll just change
        the information so that next time we try and connect we'll use the
        new ones
        """
        if self.type == 'slave':
            self._porterUsername = username
            self._porterPassword = password

            creds = credentials.UsernamePassword(self._porterUsername, 
                self._porterPassword)
            self._pbclient.startLogin(creds, self.medium)

            # If we've changed paths, we must do some extra work.
            if path != self._porterPath:
                self._porterPath = path
                self._pbclient.stopTrying() # Stop trying to connect with the
                                            # old connector.
                self._pbclient.resetDelay()
                reactor.connectWith(
                    fdserver.FDConnector, self._porterPath, 
                    self._pbclient, 10, checkPID=False)
        else:
            raise errors.WrongStateError(
                "Can't specify porter details in master mode")

    def do_start(self, *args, **kwargs):
        #root = HTTPRoot()
        root = resource.Resource()
        # TwistedWeb wants the child path to not include the leading /
        mount = self.mountPoint[1:]
        # split path on / and add iteratively twisted.web resources
        children = string.split(mount, '/')
        current_resource = root
        for child in children[:-1]:
            res = resource.Resource()
            current_resource.putChild(child, res)
            current_resource = res
        fileResource = File(self.filePath, self._requestStarted, 
            self._requestFinished, self)
        self.debug("Putting File resource at %r", children[-1:][0])
        current_resource.putChild(children[-1:][0], fileResource)
        #root.putChild(mount, HTTPStaticFile(self.filePath))
        d = defer.Deferred()
        if self.type == 'slave':
            # Streamer is slaved to a porter.
            if self._singleFile:
                self._pbclient = porterclient.HTTPPorterClientFactory(
                    server.Site(resource=root), [self.mountPoint], d)
            else:
                self._pbclient = porterclient.HTTPPorterClientFactory(
                    server.Site(resource=root), [], d, 
                    prefixes=[self.mountPoint])
            creds = credentials.UsernamePassword(self._porterUsername, 
                self._porterPassword)
            self._pbclient.startLogin(creds, self.medium)
            self.debug("Starting porter login!")
            # This will eventually cause d to fire
            reactor.connectWith(fdserver.FDConnector, self._porterPath, 
                self._pbclient, 10, checkPID=False)
        else:
            # File Streamer is standalone.
            try:
                self.debug('Listening on %s' % self.port)
                iface = ""
                reactor.listenTCP(self.port, server.Site(resource=root), 
                    interface=iface)
            except error.CannotListenError:
                t = 'Port %d is not available.' % self.port
                self.warning(t)
                m = messages.Error(T_(N_(
                    "Network error: TCP port %d is not available."), self.port))
                self.addMessage(m)
                self.setMood(moods.sad)
                return defer.fail(errors.ComponentStartHandledError(t))
            # fire callback so component gets happy
            d.callback(None)
        # we are responsible for setting component happy
        def setComponentHappy(result):
            self.setMood(moods.happy)
            return result
        d.addCallback(setComponentHappy)
        return d

    def do_check(self):
        props = self.config['properties']
        if props.get('type', 'master') == 'slave':
            for k in 'socket_path', 'username', 'password':
                if not 'porter_' + k in props:
                    msg = ' slave mod, missing required property %s' % k
                    return defer.fail(errors.ConfigError(msg))
        else:
            if not 'port' in props:
                msg = "master mode, missing required property 'port'"
                return defer.fail(errors.ConfigError(msg))

        if props.get('mount_point', None) is not None: 
            path = props.get('path', None) 
            if path is None: 
                msg = "missing required property 'path'"
                return defer.fail(errors.ConfigError(msg)) 
            if os.path.isfile(path):
                self._singleFile = True
            elif os.path.isdir(path):
                self._singleFile = False
            else:
                msg = "the file or directory specified in 'path': %s does " \
                    "not exist or is neither a file nor directory" % path
                return defer.fail(errors.ConfigError(msg)) 

    def addFileTransfer(self, request, offset, transfer):
        self._transfersInProgress[request] = (offset, transfer)

    def _requestStarted(self, request):
        self._connected_clients += 1

    def _requestFinished(self, request, bytesWritten, timeConnected):
        headers = request.getAllHeaders()

        args = {'ip': request.getClientIP(),
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

        for logger in self.loggers:
            logger.event('http_session_completed', args)

        self._connected_clients -= 1
        self._total_bytes_written += bytesWritten
        if request in self._transfersInProgress:
            del self._transfersInProgress[request]

    def getUrl(self):
        return "http://%s:%d%s" % (self.hostname, self.port, self.mountPoint)

    def getStreamData(self):
        socket = 'flumotion.component.plugs.streamdata.StreamDataProvider'
        if self.plugs[socket]: 
            plug = self.plugs[socket][-1] 
            return plug.getStreamData()
        else:
            return {
                'protocol': 'HTTP',
                'description': 'On-Demand Flumotion Stream',
                'url' : self.getUrl()
                }

    def getLoadData(self):
        """
        Return a tuple (deltaadded, deltaremoved, bytes_transferred, 
        current_clients, current_load) of our current bandwidth and user values.
        The deltas and current_load are NOT currently implemented here, we set 
        them as zero.
        """
        bytesTransferred = self._total_bytes_written
        for (offset, transfer) in self._transfersInProgress.values():
            bytesTransferred += transfer.written - offset

        return (0, 0, bytesTransferred, self._connected_clients, 0)


    # Override HTTPAuthentication methods
    def authenticateKeycard(self, bouncerName, keycard):
        return self.medium.authenticate(bouncerName, keycard)

    def cleanupKeycard(self, bouncerName, keycard):
        return self.medium.removeKeycardId(bouncerName, keycard.id)

    def clientDone(self, fd):
        # TODO: implement this properly.
        self.warning ("Expiring clients is not implemented for static "
            "fileserving")

