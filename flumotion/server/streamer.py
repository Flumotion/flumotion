# -*- Mode: Python -*-
# vi:si:et:sw=4:sts=4:ts=4

# Flumotion - a video streamer server
# Copyright (C) 2004 Fluendo
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
# Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.

import os
import signal
import string
import sys
import time

import gobject
import gst
from twisted.web import server, resource
from twisted.internet import reactor

from flumotion.server import component
from flumotion.utils import gstutils

class HTTPStreamingResource(resource.Resource):
    def __init__(self, streamer, location):
        
        if location:
            self.logfile = file(location, 'a')
        else:
            self.logfile = None
            
        streamer.connect('streamer-client-removed', self.client_removed_cb)
        self.msg = streamer.msg
        self.streamer = streamer

        self.request_hash = {}
        
        resource.Resource.__init__(self)
        
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

        print headers
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
        date = time.strftime('[%d/%b/%Y:%H:%M:%S %z]', time.localtime())
        request = 'GET / HTTP/1.0'
        response = 200
        referer = headers.get('referer', '-')
        user_agent = headers.get('user-agent', '-')
        msg = "%s %s %s %s \"%s\" %d %d %s \"%s\" %d\n" % (ip, ident, username,
                                                           date, request,
                                                           response, bytes_sent,
                                                           referer, user_agent,
                                                           time_connected)
        self.logfile.write(msg)
        self.logfile.flush()

    def streamer_client_removed_cb(self, streamer, sink, fd):
        request = self.request_hash[fd]
        ip = request.getClientIP()
        fd = request.transport.fileno()
        self.log(fd, ip, request)
        self.msg('(%d) client from %s disconnected' % (fd, ip))
        del self.request_hash[fd]
        
    def isReady(self):
        if self.streamer.caps is None:
            self.msg('We have no caps yet')
            return False
        
        return True
        
    def getChild(self, path, request):
        return self

    def render(self, request):
        ip = request.getClientIP()
        fd = request.transport.fileno()
        self.request_hash[fd] = request
        self.msg('(%d) client from %s connected' % (fd, ip))
    
        if not self.isReady():
            self.msg('Not sending data, it\'s not ready')
            return server.NOT_DONE_YET

        mime = self.streamer.get_mime()
        if mime == 'multipart/x-mixed-replace':
            self.msg('setting Content-type to %s but with camserv hack' % mime)
            # Stolen from camserv
            request.setHeader('Cache-Control', 'no-cache')
            request.setHeader('Cache-Control', 'private')
            request.setHeader("Content-type", "%s;boundary=ThisRandomString" % mime)
        else:
            self.msg('setting Content-type to %s' % mime)
            request.setHeader('Content-type', mime)

        self.streamer.add_client(fd)
        # Noop to write headers, bad twisted
        request.write('')
        
        #request.notifyFinish().addBoth(self.lost, fd, ip)
        
        return server.NOT_DONE_YET

class FileSinkStreamer(component.ParseLaunchComponent):
    kind = 'streamer'
    pipe_template = 'filesink name=sink location="%s"'
    def __init__(self, name, sources, location):
        self.location = location

        pipeline = self.pipe_template % self.get_location()
        component.ParseLaunchComponent.__init__(self, name, sources,
                                                [], pipeline)

    def create_admin(self):
        from twisted.manhole.telnet import ShellFactory
        from flumotion.twisted.shell import Shell
        
        ts = ShellFactory()
        ts.username = 'fluendo'
        ts.protocol = Shell
        ts.namespace['self'] = self
        ts.namespace['restart'] = self.local_restart

        return ts
    
    def get_location(self):
        if self.location.find('%') != -1:
            timestamp = time.strftime('%Y-%m-%d-%H:%M:%S', time.localtime())
            return self.location % timestamp

        return self.location

    def local_restart(self):
        if self.pipeline is None:
            self.msg('Not started yet, skipping')
            return

        self.pipeline.set_state(gst.STATE_PAUSED)

        # Save and close file
        sink = self.pipeline.get_by_name('sink')
        sink.set_state(gst.STATE_READY)

        location = self.get_location()
        self.msg('setting location to', location)
        sink.set_property('location', location)
        
        self.pipeline.set_state(gst.STATE_PLAYING)

    # connect() is already taken by gobject.GObject
    def connect_to(self, sources):
        self.setup_sources(sources)
        sink = self.pipeline.get_by_name('sink')
        sink.connect('state-change', self.feed_state_change_cb, '')

        self.pipeline_play()

    remote_connect = connect_to

class MultifdSinkStreamer(component.ParseLaunchComponent, gobject.GObject):
    kind = 'streamer'
    pipe_template = 'multifdsink buffers-max=500 buffers-soft-max=250 recover-policy=1 name=sink'
    __gsignals__ = {
        'client-removed': (gobject.SIGNAL_RUN_FIRST, None, (object, int))
                   }
                                       
    
    def __init__(self, name, sources):
        self.__gobject_init__()
        component.ParseLaunchComponent.__init__(self, name, sources, [], self.pipe_template)
        self.caps = None
        
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
        sink.emit('add', fd)
         
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
        
    # connect() is already taken by gobject.GObject
    def connect_to(self, sources):
        self.setup_sources(sources)
        sink = self.get_sink()
        sink.connect('deep-notify::caps', self.notify_caps_cb)
        sink.connect('state-change', self.feed_state_change_cb, '')
        sink.connect('client-removed', self.client_removed_cb)
        
        self.pipeline_play()

    remote_connect = connect_to
gobject.type_register(MultifdSinkStreamer)
