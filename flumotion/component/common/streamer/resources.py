# -*- Mode: Python; test-case-name: flumotion.test.test_http -*-
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
import socket
import time
import errno
import string
import resource
import fcntl

import gst

try:
    from twisted.web import http
except ImportError:
    from twisted.protocols import http

from twisted.web import server, resource as web_resource
from twisted.internet import reactor, defer

from flumotion.configure import configure
from flumotion.common import log

# register serializable
from flumotion.common import keycards


__all__ = ['HTTPStreamingResource', 'HTTPStreamer']
__version__ = "$Rev$"


ERROR_TEMPLATE = """<!doctype html public "-//IETF//DTD HTML 2.0//EN">
<html>
<head>
  <title>%(code)d %(error)s</title>
</head>
<body>
<h2>%(code)d %(error)s</h2>
</body>
</html>
"""


### the Twisted resource that handles the base URL

HTTP_VERSION = configure.version

class HTTPStreamingResource(web_resource.Resource, log.Loggable):
    HTTP_NAME = 'FlumotionHTTPServer'
    HTTP_SERVER = '%s/%s' % (HTTP_NAME, HTTP_VERSION)

    __reserve_fds__ = 50 # number of fd's to reserve for non-streaming

    logCategory = 'httpstreamer'

    # IResource interface variable; True means it will not chain requests
    # further down the path to other resource providers through
    # getChildWithDefault
    isLeaf = True

    def __init__(self, streamer, httpauth):
        """
        @param streamer: L{Streamer}
        """
        self.streamer = streamer
        self.httpauth = httpauth

        self._requests = {}            # request fd -> Request

        self.maxclients = self.getMaxAllowedClients(-1)
        self.maxbandwidth = -1 # not limited by default

        # If set, a URL to redirect a user to when the limits above are reached
        self._redirectOnFull = None

        self._removing = {} # Optional deferred notification of client removals

        socket = 'flumotion.component.plugs.request.RequestLoggerPlug'
        self.loggers = streamer.plugs.get(socket, [])

        socket = \
            'flumotion.component.plugs.requestmodifier.RequestModifierPlug'
        self.modifiers = streamer.plugs.get(socket, [])

        self.logfilter = None

        web_resource.Resource.__init__(self)

    def clientRemoved(self, sink, fd, reason, stats):
        # this is the callback attached to our flumotion component,
        # not the GStreamer element
        if fd in self._requests:
            request = self._requests[fd]
            self._removeClient(request, fd, stats)
        else:
            self.warning('[fd %5d] not found in _requests' % fd)

    def removeAllClients(self):
        l = []
        for fd in self._requests:
            self._removing[fd] = defer.Deferred()
            l.append(self._removing[fd])
            self.streamer.remove_client(fd)

        return defer.DeferredList(l)

    def setRoot(self, path):
        self.putChild(path, self)

    def setLogFilter(self, logfilter):
        self.logfilter = logfilter

    def rotateLogs(self):
        """
        Close the logfile, then reopen using the previous logfilename
        """
        for logger in self.loggers:
            self.debug('rotating logger %r' % logger)
            logger.rotate()

    def logWrite(self, fd, ip, request, stats):

        headers = request.getAllHeaders()

        if stats:
            bytes_sent = stats[0]
            time_connected = int(stats[3] / gst.SECOND)
        else:
            bytes_sent = -1
            time_connected = -1

        args = {'ip': ip,
                'time': time.gmtime(),
                'method': request.method,
                'uri': request.uri,
                'username': '-', # FIXME: put the httpauth name
                'get-parameters': request.args,
                'clientproto': request.clientproto,
                'response': request.code,
                'bytes-sent': bytes_sent,
                'referer': headers.get('referer', None),
                'user-agent': headers.get('user-agent', None),
                'time-connected': time_connected}

        l = []
        for logger in self.loggers:
            l.append(defer.maybeDeferred(
                logger.event, 'http_session_completed', args))

        return defer.DeferredList(l)

    def setUserLimit(self, limit):
        self.info('setting maxclients to %d' % limit)
        self.maxclients = self.getMaxAllowedClients(limit)
        # Log what we actually managed to set it to.
        self.info('set maxclients to %d' % self.maxclients)

    def setBandwidthLimit(self, limit):
        self.maxbandwidth = limit
        self.info("set maxbandwidth to %d", self.maxbandwidth)

    def setRedirectionOnLimits(self, url):
        self._redirectOnFull = url

    def _setRequestHeaders(self, request):
        content = self.streamer.get_content_type()
        request.setHeader('Server', self.HTTP_SERVER)
        request.setHeader('Date', http.datetimeToString())
        request.setHeader('Connection', 'close')
        request.setHeader('Cache-Control', 'no-cache')
        request.setHeader('Cache-Control', 'private')
        request.setHeader('Content-type', content)

    def _formatHeaders(self, request):
        # Mimic Twisted as close as possible
        headers = []
        for name, value in request.headers.items():
            headers.append('%s: %s\r\n' % (name, value))
        for cookie in request.cookies:
            headers.append('%s: %s\r\n' % ("Set-Cookie", cookie))
        return headers

    # FIXME: rename to writeHeaders

    def _writeHeaders(self, request):
        """
        Write out the HTTP headers for the incoming HTTP request.

        @rtype:   boolean
        @returns: whether or not the file descriptor can be used further.
        """
        fd = request.transport.fileno()
        fdi = request.fdIncoming

        # the fd could have been closed, in which case it will be -1
        if fd == -1:
            self.info('[fd %5d] Client gone before writing header' % fdi)
            # FIXME: do this ? del request
            return False
        if fd != request.fdIncoming:
            self.warning('[fd %5d] does not match current fd %d' % (fdi, fd))
            # FIXME: do this ? del request
            return False

        self._setRequestHeaders(request)

        # Call request modifiers
        for modifier in self.modifiers:
            modifier.modify(request)

        headers = self._formatHeaders(request)

        ### FIXME: there's a window where Twisted could have removed the
        # fd because the client disconnected.  Catch EBADF correctly here.
        try:
            # TODO: This is a non-blocking socket, we really should check
            # return values here, or just let twisted handle all of this
            # normally, and not hand off the fd until after twisted has
            # finished writing the headers.
            os.write(fd, 'HTTP/1.0 200 OK\r\n%s\r\n' % ''.join(headers))
            # tell TwistedWeb we already wrote headers ourselves
            request.startedWriting = True
            return True
        except OSError, (no, s):
            if no == errno.EBADF:
                self.info('[fd %5d] client gone before writing header' % fd)
            elif no == errno.ECONNRESET:
                self.info(
                    '[fd %5d] client reset connection writing header' % fd)
            else:
                self.info(
                    '[fd %5d] unhandled write error when writing header: %s'
                    % (fd, s))
        # trigger cleanup of request
        del request
        return False

    def isReady(self):
        if not self.streamer.hasCaps():
            self.debug('We have no caps yet')
            return False
        return True

    def getMaxAllowedClients(self, maxclients):
        """
        maximum number of allowed clients based on soft limit for number of
        open file descriptors and fd reservation. Increases soft limit to
        hard limit if possible.
        """
        (softmax, hardmax) = resource.getrlimit(resource.RLIMIT_NOFILE)
        import sys
        version = sys.version_info

        if maxclients != -1:
            neededfds = maxclients + self.__reserve_fds__

            # Bug in python 2.4.3, see
            # http://sourceforge.net/tracker/index.php?func=detail&
            #   aid=1494314&group_id=5470&atid=105470
            if version[:3] == (2, 4, 3) and \
                not hasattr(socket, "has_2_4_3_patch"):
                self.warning(
                    'Setting hardmax to 1024 due to python 2.4.3 bug')
                hardmax = 1024

            if neededfds > softmax:
                lim = min(neededfds, hardmax)
                resource.setrlimit(resource.RLIMIT_NOFILE, (lim, hardmax))
                return lim - self.__reserve_fds__
            else:
                return maxclients
        else:
            return softmax - self.__reserve_fds__

    def reachedServerLimits(self):
        if self.maxclients >= 0 and len(self._requests) >= self.maxclients:
            return True
        elif self.maxbandwidth >= 0:
            # Reject if adding one more client would take us over the limit.
            if ((len(self._requests) + 1) *
                    self.streamer.getCurrentBitrate() >= self.maxbandwidth):
                return True
        return False

    def _addClient(self, request):
        """
        Add a request, so it can be used for statistics.

        @param request: the request
        @type request: twisted.protocol.http.Request
        """

        fd = request.transport.fileno()
        self._requests[fd] = request

    def _logRequestFromIP(self, ip):
        """
        Returns whether we want to log a request from this IP; allows us to
        filter requests from automated monitoring systems.
        """
        if self.logfilter:
            return not self.logfilter.isInRange(ip)
        else:
            return True

    def _removeClient(self, request, fd, stats):
        """
        Removes a request and add logging.
        Note that it does not disconnect the client; it is called in reaction
        to a client disconnecting.
        It also removes the keycard if one was created.

        @param request: the request
        @type request: L{twisted.protocols.http.Request}
        @param fd: the file descriptor for the client being removed
        @type fd: L{int}
        @param stats: the statistics for the removed client
        @type stats: GValueArray
        """

        # PROBE: finishing request; see httpserver.httpserver
        self.debug('[fd %5d] (ts %f) finishing request %r',
                   request.transport.fileno(), time.time(), request)

        ip = request.getClientIP()
        if self._logRequestFromIP(ip):
            d = self.logWrite(fd, ip, request, stats)
        else:
            d = defer.succeed(True)
        self.info('[fd %5d] Client from %s disconnected' % (fd, ip))

        # We can't call request.finish(), since we already "stole" the fd, we
        # just loseConnection on the transport directly, and delete the
        # Request object, after cleaning up the bouncer bits.
        self.httpauth.cleanupAuth(fd)

        self.debug('[fd %5d] (ts %f) closing transport %r', fd, time.time(),
            request.transport)
        # This will close the underlying socket. We first remove the request
        # from our fd->request map, since the moment we call this the fd might
        # get re-added.
        del self._requests[fd]
        request.transport.loseConnection()

        self.debug('[fd %5d] closed transport %r' % (fd, request.transport))

        def _done(_):
            if fd in self._removing:
                self.debug("client is removed; firing deferred")
                removeD = self._removing.pop(fd)
                removeD.callback(None)

            # PROBE: finished request; see httpserver.httpserver
            self.debug('[fd %5d] (ts %f) finished request %r',
                       fd, time.time(), request)

        d.addCallback(_done)
        return d

    def handleAuthenticatedRequest(self, res, request):
        # PROBE: authenticated request; see httpserver.httpfile
        self.debug('[fd %5d] (ts %f) authenticated request %r',
                   request.transport.fileno(), time.time(), request)

        if request.method == 'GET':
            self._handleNewClient(request)
        elif request.method == 'HEAD':
            self.debug('handling HEAD request')
            self._writeHeaders(request)
            request.finish()
        else:
            raise AssertionError

        return res

    ### resource.Resource methods

    # this is the callback receiving the request initially

    def _render(self, request):
        fd = request.transport.fileno()
        # we store the fd again in the request using it as an id for later
        # on, so we can check when an fd went away (being -1) inbetween
        request.fdIncoming = fd

        # PROBE: incoming request; see httpserver.httpfile
        self.debug('[fd %5d] (ts %f) incoming request %r',
                   fd, time.time(), request)

        self.info('[fd %5d] Incoming client connection from %s' % (
            fd, request.getClientIP()))
        self.debug('[fd %5d] _render(): request %s' % (
            fd, request))

        if not self.isReady():
            return self._handleNotReady(request)
        elif self.reachedServerLimits():
            return self._handleServerFull(request)

        self.debug('_render(): asked for (possible) authentication')
        d = self.httpauth.startAuthentication(request)
        d.addCallback(self.handleAuthenticatedRequest, request)
        # Authentication has failed and we've written a response; nothing
        # more to do
        d.addErrback(lambda x: None)

        # we MUST return this from our _render.
        return server.NOT_DONE_YET

    def _handleNotReady(self, request):
        self.debug('Not sending data, it\'s not ready')
        return server.NOT_DONE_YET

    def _handleServerFull(self, request):
        if self._redirectOnFull:
            self.debug("Redirecting client, client limit %d reached",
                self.maxclients)
            error_code = http.FOUND
            request.setHeader('location', self._redirectOnFull)
        else:
            self.debug('Refusing clients, client limit %d reached' %
                self.maxclients)
            error_code = http.SERVICE_UNAVAILABLE

        request.setHeader('content-type', 'text/html')

        request.setHeader('server', HTTP_VERSION)
        request.setResponseCode(error_code)

        return ERROR_TEMPLATE % {'code': error_code,
                                 'error': http.RESPONSES[error_code]}

    def _handleNewClient(self, request):
        # everything fulfilled, serve to client
        fdi = request.fdIncoming
        if not self._writeHeaders(request):
            self.debug("[fd %5d] not adding as a client" % fdi)
            return

        # take over the file descriptor from Twisted by removing them from
        # the reactor
        # spiv told us to remove* on request.transport, and that works
        # then we figured out that a new request is only a Reader, so we
        # remove the removedWriter - this is because we never write to the
        # socket through twisted, only with direct os.write() calls from
        # _writeHeaders.

        # see http://twistedmatrix.com/trac/ticket/1796 for a guarantee
        # that this is a supported way of stealing the socket
        fd = fdi
        self.debug("[fd %5d] taking away from Twisted" % fd)
        reactor.removeReader(request.transport)
        #reactor.removeWriter(request.transport)

        # check if it's really an open fd (i.e. that twisted didn't close it
        # before the removeReader() call)
        try:
            fcntl.fcntl(fd, fcntl.F_GETFL)
        except IOError, e:
            if e.errno == errno.EBADF:
                self.warning("[fd %5d] is not actually open, ignoring" % fd)
            else:
                self.warning("[fd %5d] error during check: %s (%d)" % (
                    fd, e.strerror, e.errno))
            return

        self._addClient(request)

        # hand it to multifdsink
        self.streamer.add_client(fd, request)
        ip = request.getClientIP()

        # PROBE: started request; see httpfile.httpfile
        self.debug('[fd %5d] (ts %f) started request %r',
                   fd, time.time(), request)

        self.info('[fd %5d] Started streaming to %s' % (fd, ip))

    render_GET = _render
    render_HEAD = _render


class HTTPRoot(web_resource.Resource, log.Loggable):
    logCategory = "httproot"

    def getChildWithDefault(self, path, request):
        # we override this method so that we can look up tree resources
        # directly without having their parents.
        # There's probably a more Twisted way of doing this, but ...
        fullPath = path
        if request.postpath:
            fullPath += '/' + string.join(request.postpath, '/')
        self.debug("[fd %5d] Incoming request %r for path %s",
            request.transport.fileno(), request, fullPath)
        r = web_resource.Resource.getChildWithDefault(self, fullPath, request)
        self.debug("Returning resource %r" % r)
        return r
