# -*- Mode: Python -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# Flumotion - a video streaming server
# Copyright (C) 2004 Fluendo
#
# http.py: a consumer that streams over HTTP
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Street #330, Boston, MA 02111-1307, USA.

import os
import random
import time

import gobject
import gst
from twisted.protocols import http
from twisted.web import server, resource
from twisted.internet import reactor

from flumotion.component import component
from flumotion.common import interfaces
from flumotion.common import auth
from flumotion.utils import gstutils, log
from flumotion.utils.gstutils import gsignal

import twisted.internet.error

__all__ = ['HTTPClientKeycard', 'HTTPStreamingAdminResource',
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

class HTTPClientKeycard:
    
    __implements__ = interfaces.IClientKeycard,
    
    def __init__(self, request):
        self.request = request
        
    def getUsername(self):
        return self.request.getUser()

    def getPassword(self):
        return self.request.getPassword()

    def getIP(self):
        return self.request.getClientIP()

def format_bytes(bytes):
    'nicely format number of bytes'
    idx = ['P', 'T', 'G', 'M', 'K', '']
    value = float(bytes)
    l = idx.pop()
    while idx and value >= 1024:
        l = idx.pop()
        value /= 1024
    return "%.2f %sB" % (value, l)

def format_time(time):
    'nicely format time'
    display = []
    days = time / 86400
    if days >= 7:
        display.append('%d weeks' % days / 7)
        days %= 7
    if days >= 1:
        display.append('%d days' % days)
    time %= 86400
    h = time / 3600
    time %= 3600
    m = time / 60
    time %= 60
    s = time
    display.append('%02d:%02d:%02d' % (h, m, s))
    return " ".join(display)
    
class HTTPStreamingAdminResource(resource.Resource):
    def __init__(self, parent):
        'call with a HTTPStreamingResource to admin for'
        self.parent = parent
        self.debug = self.parent.debug
        #self.info = lambda msg: log.info('HTTP admin', msg)

        resource.Resource.__init__(self)

    def getChild(self, path, request):
        return self
        
    def isAuthenticated(self, request):
        if request.getClientIP() == '127.0.0.1':
            return True
        if request.getUser() == 'fluendo' and request.getPassword() == 's3kr3t':
            return True
        return False
    
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

        return self.render_stats(request)
    
    def render_stats(self, request):
        stats = self.parent.streamer
        
        bytes_sent      = stats.getBytesSent()
        bytes_received  = stats.getBytesReceived()
        uptime          = stats.getUptime()
        
        s = {}
        s['Clients connected'] = stats.getClients()
        s['Mime type'] = self.parent.streamer.get_mime()
        s['Total bytes sent'] = format_bytes(bytes_sent)
        s['Bytes processed'] = format_bytes(bytes_received)
        s['Stream uptime'] = format_time(uptime)
        s['Stream bitrate'] = format_bytes(bytes_received / uptime) + '/sec'
        s['Total client bitrate'] = format_bytes(bytes_sent / uptime) + '/sec'
        s['Peak Client Number'] = stats.getPeakClients()
        
        stats.updateAverage()
        s['Average Simultaneous Clients'] = int(stats.getAverageClients())
        s['Maximum allowed clients'] = int(self.parent.maxAllowedClients())

        block = []
        for key, value in s.items():
            block.append('<tr><td>%s</td><td>%s</td></tr>' % (key, value))
            
        return STATS_TEMPLATE % {
            'name': self.parent.streamer.get_name(),
            'stats': "\n".join(block)}

class Stats:
    def __init__(self, sink):
        self.sink = sink
        
        self.no_clients = 0        
        self.start_time = time.time()
        # keep track of the highest number
        self.peak_client_number = 0 
        # keep track of average clients by tracking last average and its time
        self.average_client_number = 0
        self.average_time = self.start_time
        
    def updateAverage(self):
        # update running average of clients connected
        now = time.time()
        # calculate deltas
        dt1 = self.average_time - self.start_time
        dc1 = self.average_client_number
        dt2 = now - self.average_time
        dc2 = self.no_clients
        self.average_time = now # we can update now that we used self.av
        if dt1 == 0:
            # first measurement
            self.average_client_number = 0
        else:
            self.average_client_number = (dc1 * dt1 / (dt1 + dt2) +
                                          dc2 * dt2 / (dt1 + dt2))
    def clientAdded(self):
        self.updateAverage()

        self.no_clients += 1

        if self.no_clients > self.peak_client_number:
            self.peak_client_number = self.no_clients
    
    def clientRemoved(self):
        self.updateAverage()
        self.no_clients -= 1

    def getBytesSent(self):
        return self.sink.get_property('bytes-served')
    
    def getBytesReceived(self):
        return self.sink.get_property('bytes-to-serve')
    
    def getUptime(self):
        return time.time() - self.start_time
    
    def getClients(self):
        return self.no_clients
    
    def getPeakClients(self):
        return self.peak_client_number
    
    def getAverageClients(self):
        return self.average_client_number
        
class HTTPStreamingResource(resource.Resource, log.Loggable):
    __reserve_fds__ = 50 # number of fd's to reserve for non-streaming

    logCategory = 'httpstreamer'
    
    def __init__(self, streamer):
        self.logfile = None
            
        streamer.connect('client-removed', self.streamer_client_removed_cb)
        self.streamer = streamer
        self.admin = HTTPStreamingAdminResource(self)

        self.request_hash = {}
        self.auth = None
        
        self.start_time = time.time()
        self.peak_client_number = 0 # keep track of the highest number
        # keep track of average clients by tracking last average and its time
        self.average_client_number = 0
        self.average_time = self.start_time
        self.maxclients = -1
        
        resource.Resource.__init__(self)

    def setLogfile(self, logfile):
        self.logfile = open(logfile, 'a')
        
    def log(self, fd, ip, request):
        if not self.logfile:
            return

        headers = request.getAllHeaders()

        stats = self.streamer.get_stats(fd)
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

    def streamer_client_removed_cb(self, streamer, sink, fd, reason):
        request = self.request_hash[fd]
        self.removeClient(request, fd)

    def isReady(self):
        if self.streamer.caps is None:
            self.debug('We have no caps yet')
            return False
        
        return True

    def setAuth(self, auth):
        self.auth = auth

    def setMaxClients(self, maxclients):
        self.info('setting maxclients to %d' % maxclients)
        self.maxclients = maxclients
        
    def getChild(self, path, request):
        if path == 'stats':
            return self.admin
        return self

    def setHeaders(self, request):
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
        os.write(fd, 'HTTP/1.0 200 OK\r\n%s\r\n' % ''.join(headers))

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
            from resource import getrlimit, RLIMIT_NOFILE
            limit = getrlimit(RLIMIT_NOFILE)
            return limit[0] - self.__reserve_fds__

    def reachedMaxClients(self):
        return len(self.request_hash) >= self.maxAllowedClients()
    
    def isAuthenticated(self, request):
        if self.auth is None:
            return True

        keycard = HTTPClientKeycard(request)
        return self.auth.authenticate(keycard)

    def addClient(self, request):
        """Add a request, so it can be used for statistics
        @param request: the request
        @type request: twisted.protocol.http.Request
        """

        fd = request.transport.fileno()
        self.request_hash[fd] = request

    def removeClient(self, request, fd):
        """Removes a request and add logging. Note that it does not disconnect the client
        @param request: the request
        @type request: twisted.protocol.http.Request
        @param fd: the file descriptor for the client being removed
        @type fd: L{int}
        """

        ip = request.getClientIP()
        self.log(fd, ip, request)
        self.info('client from %s on fd %d disconnected' % (ip, fd))
        del self.request_hash[fd]

    def handleNotReady(self, request):
        self.debug('Not sending data, it\'s not ready')
        return server.NOT_DONE_YET
        
    def handleMaxClients(self, request):
        self.debug('Refusing clients, client limit %d reached' % self.maxAllowedClients())

        request.setHeader('content-type', 'text/html')
        request.setHeader('server', HTTP_VERSION)
        
        error_code = http.SERVICE_UNAVAILABLE
        request.setResponseCode(error_code)
        
        return ERROR_TEMPLATE % {'code': error_code,
                                 'error': http.RESPONSES[error_code]}
        
    def handleUnauthorized(self, request):
        self.debug('client from %s is unauthorized' % (request.getClientIP()))
        request.setHeader('content-type', 'text/html')
        request.setHeader('server', HTTP_VERSION)
        if self.auth:
            request.setHeader('WWW-Authenticate',
                              'Basic realm="%s"' % self.auth.getDomain())
            
        error_code = http.UNAUTHORIZED
        request.setResponseCode(error_code)
        
        return ERROR_TEMPLATE % {'code': error_code,
                                 'error': http.RESPONSES[error_code]}

    def handleNewClient(self, request):
        # everything fulfilled, serve to client
        self.setHeaders(request)
        self.addClient(request)
        fd = request.transport.fileno()
        self.streamer.add_client(fd)
        self.info('client from %s on fd %d accepted' % (request.getClientIP(), fd))
        return server.NOT_DONE_YET
        
    def render(self, request):
        self.debug('client from %s connected' % (request.getClientIP()))
    
        if not self.isReady():
            return self.handleNotReady(request)
        elif self.reachedMaxClients():
            return self.handleMaxClients(request)
        elif not self.isAuthenticated(request):
            return self.handleUnauthorized(request)
        else:
            return self.handleNewClient(request)

class HTTPView(component.ComponentView):
    def __init__(self, comp):
        component.ComponentView.__init__(self, comp)

        self.comp.connect('ui-state-changed', self.comp_ui_state_changed_cb)

    def getState(self):
        stats = self.comp

        s = {}

        bytes_sent      = stats.getBytesSent()
        bytes_received  = stats.getBytesReceived()
        uptime          = stats.getUptime()

        s['clients-connected'] = self.comp.getClients()
        s['mime'] = self.comp.get_mime()
        s['bytes-sent'] = format_bytes(bytes_sent)
        s['bytes-received'] = format_bytes(bytes_received)
        s['uptime'] = format_time(uptime)
        s['bitrate'] = format_bytes(bytes_received / uptime) + '/sec'
        s['clients-bitrate'] = format_bytes(bytes_sent / uptime) + '/sec'
        s['peak-clients'] = stats.getPeakClients()
        #s['average-clients'] = int(stats.getAverageClients())
        #s['max-clients'] = int(self.parent.maxAllowedClients())
        
        return s
    
    def comp_ui_state_changed_cb(self, comp):
        self.callRemote('uiStateChanged', self.comp.get_name(), self.getState())

class MultifdSinkStreamer(component.ParseLaunchComponent, Stats):
    logCategory = 'cons-http'
    # use select for test
    pipe_template = 'multifdsink name=sink ' + \
                                'buffers-max=500 ' + \
                                'buffers-soft-max=250 ' + \
                                'recover-policy=1'

    gsignal('client-removed', object, int, int)
    gsignal('ui-state-changed')
    
    component_view = HTTPView

    def __init__(self, name, source, port):
        self.port = port
        self.gst_properties = []
        component.ParseLaunchComponent.__init__(self, name, [source], [],
                                                self.pipe_template)
        Stats.__init__(self, sink=self.get_sink())
        self.caps = None
        
    def __repr__(self):
        return '<MultifdSinkStreamer (%s)>' % self.component_name

    def remote_notifyState(self):
        self.update_ui_state()

    def notify_caps_cb(self, element, pad, param):
        caps = pad.get_negotiated_caps()
        if caps is None:
            return
        
        caps_str = gstutils.caps_repr(caps)
        self.debug('Got caps: %s' % caps_str)
        
        if not self.caps is None:
            self.warn('Already had caps: %s, replacing' % caps_str)

        self.debug('Storing caps: %s' % caps_str)
        self.caps = caps
        
        self.emit('ui-state-changed')

    def get_mime(self):
        if self.caps:
            return self.caps.get_structure(0).get_name()

    def get_content_type(self):
        mime = self.get_mime()
        if mime == 'multipart/x-mixed-replace':
            mime += ";boundary=ThisRandomString"
        return mime
    
    def add_client(self, fd):
        sink = self.get_sink()
        stats = sink.emit('add', fd)

    def get_stats(self, fd):
        sink = self.get_sink()
        return sink.emit('get-stats', fd)
    
    def get_sink(self):
        assert self.pipeline, 'Pipeline not created'
        sink = self.pipeline.get_by_name('sink')
        assert sink, 'No sink element in pipeline'
        assert isinstance(sink, gst.Element)
        return sink

    def update_ui_state(self):
        self.emit('ui-state-changed')
        
    def client_added_cb(self, sink, fd):
        Stats.clientAdded(self)
        self.update_ui_state()
        
    def client_removed_cb(self, sink, fd, reason):
        self.emit('client-removed', sink, fd, reason)
        Stats.clientRemoved(self)
        self.update_ui_state()

    def feeder_state_change_cb(self, element, old, state):
        component.BaseComponent.feeder_state_change_cb(self, element,
                                                     old, state, '')
        if state == gst.STATE_PLAYING:
            self.debug('Ready to serve clients on %d' % self.port)

    def link_setup(self, eaters, feeders):
        sink = self.get_sink()
        sink.connect('deep-notify::caps', self.notify_caps_cb)
        sink.connect('state-change', self.feeder_state_change_cb)
        sink.connect('client-removed', self.client_removed_cb)
        sink.connect('client-added', self.client_added_cb)

        self.setGstProperties()

    def setGstProperties(self):
        for prop in self.gst_properties:
            type = prop.type
            if type == 'int':
                value = int(prop.data)
            elif type == 'str':
                value = str(prop.data)
            else:
                value = prop.data

            element = self.pipeline.get_by_name(prop.element)
            element.set_property(prop.name, value)

    def setProperties(self, properties):
        self.gst_properties = properties
        
gobject.type_register(MultifdSinkStreamer)

def createComponent(config):
    reactor.debug = True

    name = config['name']
    port = int(config['port'])
    source = config['source']

    component = MultifdSinkStreamer(name, source, port)
    resource = HTTPStreamingResource(component)
    
    factory = server.Site(resource=resource)
    
    if config.has_key('gst-property'):
        component.setProperties(config['gst-property'])

    if config.has_key('logfile'):
        component.debug('Logging to %s' % config['logfile'])
        resource.setLogfile(config['logfile'])

    if config.has_key('auth'):
        auth_component = auth.getAuth(config['config'],
                                      config['auth'])
        resource.setAuth(auth_component)

    if config.has_key('maxclients'):
        resource.setMaxClients(int(config['maxclients']))
        
    component.debug('Listening on %d' % port)
    try:
        reactor.listenTCP(port, factory)
    except twisted.internet.error.CannotListenError:
        component.error('Port %d is not available.' % port)

    return component
