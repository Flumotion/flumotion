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
import time

import gobject
import gst
from twisted.protocols import http
from twisted.web import server, resource
from twisted.internet import reactor

from flumotion.server import component
from flumotion.utils import gstutils, log

__all__ = ['HTTPStreamingResource', 'MultifdSinkStreamer']

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
HTTP_VERSION = '%s/%s' % (HTTP_NAME, HTTP_VERSION)

class HTTPStreamingResource(resource.Resource):
    def __init__(self, streamer):
        self.logfile = None
            
        streamer.connect('client-removed', self.streamer_client_removed_cb)
        self.msg = streamer.msg
        self.streamer = streamer

        self.request_hash = {}
        
        resource.Resource.__init__(self)

    def setLogfile(self, logfile):
        self.logfile = open(logfile, 'w')
        
    def log(self, fd, ip, request):
        if not self.logfile:
            return

        headers = request.getAllHeaders()

        sink = self.streamer.get_sink()
        stats = sink.emit('get-stats', fd)
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

    def streamer_client_removed_cb(self, streamer, sink, fd):
        request = self.request_hash[fd]
        ip = request.getClientIP()
        self.log(fd, ip, request)
        self.msg('(%d) client from %s disconnected' % (fd, ip))
        del self.request_hash[fd]
        
    def isReady(self):
        if self.streamer.caps is None:
            self.msg('We have no caps yet')
            return False
        
        return True

    def isAuthenticated(self, request):
        # return True always until implemented nicely
        return True
        if request.getClientIP() == '127.0.0.1':
            return True
        if request.getUser() == 'fluendo' and request.getPassword() == 's3cr3t':
            return True
        return False
    
    def getChild(self, path, request):
        return self

    def setHeaders(self, request):
        # XXX: Use request.setHeader/request.write
        fd = request.transport.fileno()
        headers = []
        def setHeader(field, name):
            headers.append('%s: %s\r\n' % (field, name))

        # Mimic Twisted as close as possible
        setHeader('Server', HTTP_VERSION)
        setHeader('Date', http.datetimeToString())
        
        mime = self.streamer.get_mime()
        if mime == 'multipart/x-mixed-replace':
            self.msg('setting Content-type to %s but with camserv hack' % mime)
            # Stolen from camserv
            setHeader('Cache-Control', 'no-cache')
            setHeader('Cache-Control', 'private')
            setHeader("Content-type", "%s;boundary=ThisRandomString" % mime)
        else:
            self.msg('setting Content-type to %s' % mime)
            setHeader('Content-type', mime)

        os.write(fd, 'HTTP/1.0 200 OK\r\n%s\r\n' % ''.join(headers))
        
    def addClient(self, request):
        fd = request.transport.fileno()
        self.request_hash[fd] = request
        self.streamer.add_client(fd)
        
    def render(self, request):
        self.msg('client from %s connected' % (request.getClientIP()))
    
        sink = self.streamer.get_sink()
        if not self.isReady():
            self.msg('Not sending data, it\'s not ready')
            return server.NOT_DONE_YET

        if self.isAuthenticated(request):
            self.setHeaders(request)
            self.addClient(request)
            return server.NOT_DONE_YET
        else:
            self.msg('client from %s is unauthorized' % (request.getClientIP()))
            error_code = http.UNAUTHORIZED
            request.setResponseCode(error_code)
            request.setHeader('server', HTTP_VERSION)
            request.setHeader('content-type', 'text/html')
            #request.setHeader('WWW-Authenticate', 'Basic realm="Restricted Access"')

            return ERROR_TEMPLATE % {'code': error_code,
                                     'error': http.RESPONSES[error_code]}

class MultifdSinkStreamer(component.ParseLaunchComponent, gobject.GObject):
    pipe_template = 'multifdsink name=sink ' + \
                                'buffers-max=500 ' + \
                                'buffers-soft-max=250 ' + \
                                'recover-policy=1'
    __gsignals__ = {
        'client-removed': (gobject.SIGNAL_RUN_FIRST, None, (object, int))
                   }
                                       
    
    def __init__(self, name, source):
        self.__gobject_init__()
        component.ParseLaunchComponent.__init__(self, name, [source], [],
                                                self.pipe_template)
        self.caps = None

    def __repr__(self):
        return '<MultifdSinkStreamer (%s)>' % self.component_name
    
    def notify_caps_cb(self, element, pad, param):
        caps = pad.get_negotiated_caps()
        if caps is None:
            return
        
        caps_str = gstutils.caps_repr(caps)
        self.msg('Got caps: %s' % caps_str)
        
        if not self.caps is None:
            self.warn('Already had caps: %s, replacing' % caps_str)

        self.msg('Storing caps: %s' % caps_str)
        self.caps = caps

    def get_mime(self):
        return self.caps.get_structure(0).get_name()
    
    def add_client(self, fd):
        sink = self.get_sink()
        stats = sink.emit('add', fd)
         
    def remove_client(self, fd):
        sink = self.get_sink()
        sink.emit('remove', fd)
        
    def get_sink(self):
        assert self.pipeline, 'Pipeline not created'
        sink = self.pipeline.get_by_name('sink')
        assert sink, 'No sink element in pipeline'
        assert isinstance(sink, gst.Element)
        return sink

    def client_removed_cb(self, sink, fd):
        self.emit('client-removed', sink, fd)
        
    def client_added_cb(self, sink, fd):
        pass

    def link_setup(self, sources, feeds):
        sink = self.get_sink()
        sink.connect('deep-notify::caps', self.notify_caps_cb)
        sink.connect('state-change', self.feed_state_change_cb, '')
        sink.connect('client-removed', self.client_removed_cb)
        sink.connect('client-added', self.client_added_cb)
        
gobject.type_register(MultifdSinkStreamer)

def createComponent(config):
    name = config['name']
    port = int(config['port'])
    source = config['source']

    component = MultifdSinkStreamer(name, source)
    resource = HTTPStreamingResource(component)
    if config.has_key('logfile'):
        component.msg('Logging to %s' % config['logfile'])
        resource.setLogfile(config['logfile'])
        
    factory = server.Site(resource=resource)
    component.msg( 'Listening on %d' % port)
    reactor.listenTCP(port, factory)

    return component
