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
import string
import sys

import gobject
import gst
from twisted.web import server, resource
from twisted.internet import reactor

from flumotion.server import component
from flumotion.utils import gstutils

class StreamingResource(resource.Resource):
    def __init__(self, streamer):
        resource.Resource.__init__(self)
        self.streamer = streamer
        self.streamer.connect('data-received', self.data_received_cb)
        self.msg = streamer.msg
        
        self.current_requests = []
        self.buffer_queue = []

        self.first_buffer = None
        self.caps_buffers = []
        
        reactor.callLater(0, self.bufferWrite)

    def data_received_cb(self, transcoder, gbuffer):
        s = str(buffer(gbuffer))
        if gbuffer.flag_is_set(gst.BUFFER_IN_CAPS):
            self.msg('Received a GST_BUFFER_IN_CAPS buffer')
            self.caps_buffers.append(s)
        else:
            if not self.first_buffer:
                self.msg('Received the first buffer')
                self.first_buffer = gbuffer
            self.buffer_queue.append(s)
                                             
    def bufferWrite(self, *args):
        for buffer in self.buffer_queue:
            for request in self.current_requests:
                request.write(buffer)
        self.buffer_queue = []
            
        reactor.callLater(0.01, self.bufferWrite)
        
    def getChild(self, path, request):
        return self

    def lost(self, obj, request):
        self.msg('client from %s disconnected' % request.getClientIP()) 
        self.current_requests.remove(request)

    def isReady(self):
        if self.streamer.caps is None:
            self.msg('We have no caps yet')
            return False
        
        if self.first_buffer is None:
            self.msg('We still haven\'t received any buffers')
            return False

        return True
        
    def render(self, request):
        self.msg('client from %s connected' % request.getClientIP())   
        if not self.isReady():
            self.msg('Not sending data, it\'s not ready')
            return server.NOT_DONE_YET

        mime = self.streamer.caps.get_structure(0).get_name()
        if mime == 'multipart/x-mixed-replace':
            self.msg('setting Content-type to %s but with camserv hack' % mime)
            # Stolen from camserv
            request.setHeader('Cache-Control', 'no-cache')
            request.setHeader('Cache-Control', 'private')
            request.setHeader("Content-type", "%s;boundary=ThisRandomString" % mime)
        else:
            self.msg('setting Content-type to %s' % mime)
            request.setHeader('Content-type', mime)
        
        for buffer in self.caps_buffers:
            request.write(buffer)
            
        self.current_requests.append(request)
        request.notifyFinish().addBoth(self.lost, request)
        
        return server.NOT_DONE_YET

class NewStreamingResource(resource.Resource):
    def __init__(self, streamer):
        self.streamer = streamer
        self.msg = streamer.msg
        resource.Resource.__init__(self)
        
    def lost(self, obj, fd, ip):
        self.streamer.add_client(fd)
        self.msg('client from %s disconnected' % ip)

    def isReady(self):
        if self.streamer.caps is None:
            self.msg('We have no caps yet')
            return False
        
        return True
        
    def getChild(self, path, request):
        print 'getChild'
        return self

    def render(self, request):
        ip = request.getClientIP()
        self.msg('client from %s connected' % ip)
    
        if not self.isReady():
            self.msg('Not sending data, it\'s not ready')
            return server.NOT_DONE_YET

        mime = self.streamer.caps.get_structure(0).get_name()
        if mime == 'multipart/x-mixed-replace':
            self.msg('setting Content-type to %s but with camserv hack' % mime)
            # Stolen from camserv
            request.setHeader('Cache-Control', 'no-cache')
            request.setHeader('Cache-Control', 'private')
            request.setHeader("Content-type", "%s;boundary=ThisRandomString" % mime)
        else:
            self.msg('setting Content-type to %s' % mime)
            request.setHeader('Content-type', mime)

        fd = request.transport.fileno()
        self.streamer.add_client(fd)
        
        request.notifyFinish().addBoth(self.lost, fd, ip)
        
        return server.NOT_DONE_YET

class FileSinkStreamer(component.ParseLaunchComponent):
    kind = 'streamer'
    pipe_template = 'filesink name=sink location="%s"'

    def __init__(self, name, sources, location):
        self.location = location
        pipeline = self.pipe_template % location
        component.ParseLaunchComponent.__init__(self, name, sources,
                                                [], pipeline)

    # connect() is already taken by gobject.GObject
    def connect_to(self, sources):
        self.setup_sources(sources)
        sink = self.pipeline.get_by_name('sink')
        sink.connect('state-change', self.feed_state_change_cb, '')

        self.pipeline_play()

    remote_connect = connect_to


class MultifdSinkStreamer(component.ParseLaunchComponent):
    kind = 'streamer'
    pipe_template = 'multifdsink name=sink'
    
    def __init__(self, name, sources):
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

    def add_client(self, fd):
        print 'client added', fd
        sink = self.get_sink()
        sink.emit('remove', fd)

    def remove_client(self, fd):
         print 'client removed', fd
         sink = self.get_sink()
         sink.emit('add', fd)
        
    def get_sink(self):
        assert self.pipeline, 'Pipeline not created'
        sink = self.pipeline.get_by_name('sink')
        assert sink, 'No sink element in pipeline'
        assert isinstance(sink, gst.Element)
        return sink

    # connect() is already taken by gobject.GObject
    def connect_to(self, sources):
        self.setup_sources(sources)
        sink = self.get_sink()
        sink.connect('deep-notify::caps', self.notify_caps_cb)
        sink.connect('state-change', self.feed_state_change_cb, '')
        
        self.pipeline_play()

    remote_connect = connect_to

class FakeSinkStreamer(gobject.GObject, component.ParseLaunchComponent):
    __gsignals__ = {
        'data-received' : (gobject.SIGNAL_RUN_FIRST, gobject.TYPE_NONE,
                          (gst.Buffer,)),
    }

    kind = 'streamer'
    pipe_template = 'fakesink signal-handoffs=1 silent=1 name=sink'
    
    def __init__(self, name, sources):
        self.__gobject_init__()
        component.ParseLaunchComponent.__init__(self, name, sources, [], self.pipe_template)
        self.caps = None
        
    def sink_handoff_cb(self, element, buffer, pad):
        self.emit('data-received', buffer)
        
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

    def get_sink(self):
        assert self.pipeline, 'Pipeline not created'
        sink = self.pipeline.get_by_name('sink')
        assert sink, 'No sink element in pipeline'
        assert isinstance(sink, gst.Element)
        return sink

    def add_client(self, fd):
        pass

    def remove_client(self, fd):
        pass
    
    # connect() is already taken by gobject.GObject
    def connect_to(self, sources):
        self.setup_sources(sources)
        sink = self.get_sink()
        sink.connect('handoff', self.sink_handoff_cb)
        sink.connect('deep-notify::caps', self.notify_caps_cb)
        sink.connect('state-change', self.feed_state_change_cb, '')
        
        self.pipeline_play()

    remote_connect = connect_to

gobject.type_register(FakeSinkStreamer)
