# -*- Mode: Python; test-case-name: flumotion.test.test_http -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# flumotion/component/consumers/httpstreamer/resources.py:
# web server part of http streamer component
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

import os
import time
import errno
import resource

import gst

from twisted.protocols import http
from twisted.web import server, resource as web_resource
from twisted.internet import reactor, defer
import twisted.internet.error

from flumotion.common import common, log, keycards

__all__ = ['HTTPStreamingAdminResource',
           'HTTPStreamingResource', 'MultifdSinkStreamer']

HTTP_NAME = 'FlumotionHTTPServer'
HTTP_VERSION = '0.1.0'

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

STATS_TEMPLATE = """<!doctype html public "-//IETF//DTD HTML 2.0//EN">
<html>
<head>
  <title>Statistics for %(name)s</title>
</head>
<body>
<table>
%(stats)s
</table>
</body>
</html>
"""

HTTP_VERSION = '%s/%s' % (HTTP_NAME, HTTP_VERSION)

# implements a Resource for the HTTP admin interface
class HTTPAdminResource(web_resource.Resource):
    
    isLeaf = True
    
    def __init__(self, parent):
        'call with a HTTPStreamingResource to admin for'
        self.parent = parent
        self.debug = self.parent.debug
        web_resource.Resource.__init__(self)

    ### resource.Resource methods

    def render(self, request):
        self.debug('Request for admin page')
        if not self.isAuthenticated(request):
            self.debug('Unauthorized request for /admin from %s' % request.getClientIP())
            error_code = http.UNAUTHORIZED
            request.setResponseCode(error_code)
            request.setHeader('server', HTTP_VERSION)
            request.setHeader('content-type', 'text/html')
            request.setHeader('WWW-Authenticate', 'Basic realm="Restricted Access"')

            return ERROR_TEMPLATE % {'code': error_code,
                                     'error': http.RESPONSES[error_code]}

        return self._render_stats(request)

    ### our methods

    # FIXME: file has this too - move upperclass ?
    def isAuthenticated(self, request):
        if request.getClientIP() == '127.0.0.1':
            return True
        
        if (request.getUser() == 'admin' and
            request.getPassword() == self.parent.admin_password):
            return True
        return False
     
    def _render_stats(self, request):
        streamer = self.parent.streamer
        s = streamer.getState()
        
        def row(label, value):
            return '<tr><td>%s</td><td>%s</td></tr>' % (label, value)
        block = []

        block.append('<tr><td colspan=2><b>Stream</b></td></tr>')
        block.append('<tr>')
        block.append(row('Mime type',   s['stream-mime']))
        block.append(row('Uptime',      s['stream-uptime']))
        block.append(row('Bit rate',    s['stream-bitrate']))
        block.append(row('Total bytes', s['stream-totalbytes']))
        block.append('</tr>')

        block.append('<tr><td colspan=2><b>Clients</b></td></tr>')
        block.append('<tr>')
        current = s['clients-current']
        max = s['clients-max']
        block.append(row('Current', "%s (of %s) " % (current, max)))
        block.append(row('Average', s['clients-average']))
        peak = s['clients-peak']
        time = s['clients-peak-time']
        block.append(row('Peak',    "%s (at %s) " % (peak, time)))
        block.append('</tr>')

        block.append('<tr><td colspan=2><b>Client consumption</b></td></tr>')
        block.append('<tr>')
        block.append(row('Bit rate',    s['consumption-bitrate']))
        block.append(row('Total bytes', s['consumption-totalbytes']))
        block.append('</tr>')
         
        return STATS_TEMPLATE % {
            'name': streamer.get_name(),
            'stats': "\n".join(block)
        }


### the Twisted resource that handles the base URL
class HTTPStreamingResource(web_resource.Resource, log.Loggable):

    __reserve_fds__ = 50 # number of fd's to reserve for non-streaming
    logCategory = 'httpstreamer'
    isLeaf = True
    
    def __init__(self, streamer):
        """
        @param streamer: L{MultifdSinkStreamer}
        """
        self.logfile = None
        self.admin_password = None
            
        streamer.connect('client-removed', self._streamer_client_removed_cb)
        self.streamer = streamer
        
        self._requests = {}         # request fd -> Request
        self._fdToKeycard = {}      # request fd -> Keycard
        self._idToKeycard = {}      # keycard id -> Keycard
        self._fdToDurationCall = {} # request fd -> IDelayedCall for duration
        self.bouncerName = None
        self.auth = None
        
        self.maxclients = -1
        
        web_resource.Resource.__init__(self)

    def _streamer_client_removed_cb(self, streamer, sink, fd, reason, stats):
        try:
            request = self._requests[fd]
            self._removeClient(request, fd, stats)
        except KeyError:
            self.warning('[fd %5d] not found in _requests' % fd)

    def setRoot(self, path):
        self.putChild(path, self)
        
    def setLogfile(self, logfile):
        self.logfile = open(logfile, 'a')
        
    def logWrite(self, fd, ip, request, stats):
        if not self.logfile:
            return

        headers = request.getAllHeaders()

        if stats:
            bytes_sent = stats[0]
            time_connected = int(stats[3] / gst.SECOND)
        else:
            bytes_sent = -1
            time_connected = -1

        # ip address
        # ident
        # authenticated name (from http header)
        # date
        # request
        # request response
        # bytes sent
        # referer
        # user agent
        # time connected
        ident = '-'
        username = '-'
        date = time.strftime('%d/%b/%Y:%H:%M:%S %z', time.localtime())
        request_str = '%s %s %s' % (request.method,
                                    request.uri,
                                    request.clientproto)
        response = request.code
        referer = headers.get('referer', '-')
        user_agent = headers.get('user-agent', '-')
        format = "%s %s %s [%s] \"%s\" %d %d %s \"%s\" %d\n"
        msg = format % (ip, ident, username, date, request_str,
                        response, bytes_sent, referer, user_agent,
                        time_connected)
        self.logfile.write(msg)
        self.logfile.flush()

    def setAuth(self, auth):
        self.auth = auth

    def setMaxClients(self, maxclients):
        self.info('setting maxclients to %d' % maxclients)
        self.maxclients = maxclients

    def setAdminPassword(self, password):
        self.admin_password = password

    def setBouncerName(self, bouncerName):
        self.bouncerName = bouncerName

    # FIXME: rename to writeHeaders
    """
    @rtype: boolean
    @returns: whether or not the file descriptor can be used further.
    """
    def _writeHeaders(self, request):
        fd = request.transport.fileno()
        headers = []
        def setHeader(field, name):
            headers.append('%s: %s\r\n' % (field, name))

        # Mimic Twisted as close as possible
        setHeader('Server', HTTP_VERSION)
        setHeader('Date', http.datetimeToString())
        setHeader('Cache-Control', 'no-cache')
        setHeader('Cache-Control', 'private')
        setHeader('Content-type', self.streamer.get_content_type())
            
        #self.debug('setting Content-type to %s' % mime)
        ### FIXME: there's a window where Twisted could have removed the
        # fd because the client disconnected.  Catch EBADF correctly here.
        try:
            os.write(fd, 'HTTP/1.0 200 OK\r\n%s\r\n' % ''.join(headers))
            return True
        except OSError, (no, s):
            if no == errno.EBADF:
                self.warning('[fd %5d] client gone before writing header' % fd)
            elif no == errno.ECONNRESET:
                self.warning('[fd %5d] client reset connection writing header' % fd)
            else:
                self.warning('[fd %5d] unhandled write error when writing header: %s' % (fd, s))
            return False

    def isReady(self):
        if self.streamer.caps is None:
            self.debug('We have no caps yet')
            return False
        
        return True

    def maxAllowedClients(self):
        """
        maximum number of allowed clients based on soft limit for number of
        open file descriptors and fd reservation
        """
        if self.maxclients != -1:
            return self.maxclients
        else:
            limit = resource.getrlimit(resource.RLIMIT_NOFILE)
            return limit[0] - self.__reserve_fds__

    def reachedMaxClients(self):
        return len(self._requests) >= self.maxAllowedClients()
    
    def authenticate(self, request):
        """
        Returns: a deferred returning a keycard or None
        """
        # for now, we're happy with a UACPP keycard; the password arrives
        # plaintext anyway
        keycard = keycards.KeycardUACPP(
            request.getUser(),
            request.getPassword(), request.getClientIP())
        keycard.requesterName = self.streamer.get_name(),
        keycard._fd = request.transport.fileno()
        
        if self.bouncerName is None:
            return defer.succeed(keycard)

        return self.streamer.medium.authenticate(self.bouncerName, keycard)

    def _addClient(self, request):
        """
        Add a request, so it can be used for statistics.

        @param request: the request
        @type request: twisted.protocol.http.Request
        """

        fd = request.transport.fileno()
        self._requests[fd] = request

    def _removeClient(self, request, fd, stats):
        """
        Removes a request and add logging.
        Note that it does not disconnect the client; it is called in reaction
        to a client disconnecting.
        
        @param request: the request
        @type request: twisted.protocol.http.Request
        @param fd: the file descriptor for the client being removed
        @type fd: L{int}
        @param stats: the statistics for the removed client
        @type stats: GValueArray
        """

        ip = request.getClientIP()
        self.logWrite(fd, ip, request, stats)
        self.info('[fd %5d] client from %s disconnected' % (fd, ip))
        request.finish()
        del self._requests[fd]
        if self.bouncerName and self._fdToKeycard.has_key(fd):
            id = self._fdToKeycard[fd].id
            del self._fdToKeycard[fd]
            del self._idToKeycard[id]
            self.streamer.medium.removeKeycard(self.bouncerName, id)
        if self._fdToDurationCall.has_key(fd):
            self.debug("canceling later expiration on fd %d" % fd)
            self._fdToDurationCall[fd].cancel()
            del self._fdToDurationCall[fd]

    def _durationCallLater(self, fd):
        """
        Expire a client due to a duration expiration.
        """
        self.debug("duration exceeded, expiring client on fd %d" % fd)

        # we're called from a callLater, so we've already run; just delete
        if self._fdToDurationCall.has_key(fd):
            del self._fdToDurationCall[fd]
            
        self.streamer.remove_client(fd)

    def expireKeycard(self, keycardId):
        """
        Expire a client's connection associated with the keycard Id.
        """
        self.debug("expiring client with keycard Id" % keycardId)

        keycard = self._idToKeycard[keycardId]
        fd = keycard._fd

        if self._fdToDurationCall.has_key(fd):
            self.debug("canceling later expiration on fd %d" % fd)
            self._fdToDurationCall[fd].cancel()
            del self._fdToDurationCall[fd]

        self.streamer.remove_client(fd)

    def _handleNotReady(self, request):
        self.debug('Not sending data, it\'s not ready')
        return server.NOT_DONE_YET
        
    def _handleMaxClients(self, request):
        self.debug('Refusing clients, client limit %d reached' % self.maxAllowedClients())

        request.setHeader('content-type', 'text/html')
        request.setHeader('server', HTTP_VERSION)
        
        error_code = http.SERVICE_UNAVAILABLE
        request.setResponseCode(error_code)
        
        return ERROR_TEMPLATE % {'code': error_code,
                                 'error': http.RESPONSES[error_code]}
        
    def _handleUnauthorized(self, request):
        self.debug('client from %s is unauthorized' % (request.getClientIP()))
        request.setHeader('content-type', 'text/html')
        request.setHeader('server', HTTP_VERSION)
        if self.auth:
            request.setHeader('WWW-Authenticate',
                              'Basic realm="%s"' % self.auth.getDomain())
            
        error_code = http.UNAUTHORIZED
        request.setResponseCode(error_code)
        
        # we have to write data ourselves, since we already returned NOT_DONE_YET
        html = ERROR_TEMPLATE % {'code': error_code,
                                 'error': http.RESPONSES[error_code]}
        request.write(html)
        request.finish()

    def _handleNewClient(self, request):
        # everything fulfilled, serve to client
        self._writeHeaders(request)
        self._addClient(request)
        fd = request.transport.fileno()
        
        # take over the file descriptor from Twisted by removing them from
        # the reactor
        # spiv told us to remove* on request.transport, and that works
        reactor.removeReader(request.transport)
        reactor.removeWriter(request.transport)
    
        # hand it to multifdsink
        self.streamer.add_client(fd)
        ip = request.getClientIP()
        self.info('[fd %5d] start streaming to %s' % (fd, ip))

    ### resource.Resource methods

    def _render(self, request):
        fd = request.transport.fileno()
        self.debug('[fd %5d] _render(): client from %s connected, request %s' %
            (fd, request.getClientIP(), request))

        if not self.isReady():
            return self._handleNotReady(request)
        elif self.reachedMaxClients():
            return self._handleMaxClients(request)

        d = self.authenticate(request)
        d.addCallback(self._authenticatedCallback, request)
        self.debug('_render(): asked for authentication')
        # FIXME
        #d.addErrback()

        # we MUST return this from our _render.
        # FIXME: check if this is true
        # FIXME: check how we later handle not authorized
        return server.NOT_DONE_YET

    def _authenticatedCallback(self, keycard, request):
        self.debug('_authenticatedCallback: keycard %r' % keycard)
        if not keycard:
            self._handleUnauthorized(request)
            return

        # properly authenticated
        if request.method == 'GET':
            fd = request.transport.fileno()

            if self.bouncerName:
                self._fdToKeycard[fd] = keycard
                self._idToKeycard[keycard.id] = keycard

            if keycard.duration:
                self.debug('new connection on %d will be expired in %f seconds' % (fd, keycard.duration))
                self._fdToDurationCall[fd] = reactor.callLater(keycard.duration, self._durationCallLater, fd)

            self._handleNewClient(request)

        elif request.method == 'HEAD':
            self.debug('handling HEAD request')
            self._writeHeaders(request)
            # tell Twisted we already wrote headers ourselves
            request.startedWriting = True
            request.finish()
        else:
            raise AssertionError

    render_GET = _render
    render_HEAD = _render

class HTTPRoot(web_resource.Resource):
    pass

def setup(component, port, mountPoint):
    """I setup the HTTP interface and attaches a streamer to mount_point
    
    @param component  : MultifdSinkStreamer
    @param port :       port to listen on
    @type  port :       integer
    @param mountPoint : mount point of stream
    @type  mountPoint : string

    @returns : the streaming resource
    @rtype   : HTTPStreamingResource
    """
    
    if mountPoint.startswith('/'):
        mountPoint = mountPoint[1:]

    streamingResource = HTTPStreamingResource(component)
    adminResource = HTTPAdminResource(streamingResource)
    
    root = HTTPRoot()
    root.putChild(mountPoint, streamingResource)
    root.putChild('stats', adminResource)

    component.debug('Listening on %d' % port)
    try:
        reactor.listenTCP(port, server.Site(resource=root))
    except twisted.internet.error.CannotListenError:
        component.error('Port %d is not available.' % port)

    return streamingResource
    
