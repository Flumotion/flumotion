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

class StreamingResource(resource.Resource):
    def __init__(self, streamer, location):
        resource.Resource.__init__(self)
        if location:
            self.logfile = file(location, 'a')
        else:
            self.logfile = None
            
        self.streamer = streamer
        self.streamer.connect('data-received', self.data_received_cb)
        self.msg = streamer.msg
        
        self.current_requests = []
        self.buffer_queue = []

        self.first_buffer = None
        self.caps_buffers = []
        self.bytes_sent = {}
        
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
                try:
                    fd = request.transport.fileno()
                    self.bytes_sent[fd] += len(buffer)
                except NotImplementedError:
                    pass
                request.write(buffer)
                
        self.buffer_queue = []
            
        reactor.callLater(0.01, self.bufferWrite)
        
    def getChild(self, path, request):
        return self

    def log(self, msg):
        self.msg(msg)
        if self.logfile:
            timestamp = time.strftime('%Y-%m-%d-%H:%M:%S', time.localtime())
            self.logfile.write('%s %s\n' % (timestamp, msg))
            self.logfile.flush()
        
    def lost(self, obj, request, fd, ip):
        self.log('client from %s disconnected (%d bytes sent)' % (ip, self.bytes_sent[fd]))
        self.current_requests.remove(request)
        del self.bytes_sent[fd]

    def isReady(self):
        if self.streamer.caps is None:
            self.msg('We have no caps yet')
            return False
        
        if self.first_buffer is None:
            self.msg('We still haven\'t received any buffers')
            return False

        return True
        
    def render(self, request):
        ip = request.getClientIP()
        self.log('client from %s connected' % ip)
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
            
        fd = request.transport.fileno()
        self.bytes_sent[fd] = 0
        self.current_requests.append(request)
        request.notifyFinish().addBoth(self.lost, request, fd, ip)
        
        return server.NOT_DONE_YET

class NewStreamingResource(resource.Resource):
    def __init__(self, streamer, location):
        self.streamer = streamer
        if location:
            self.logfile = file(location, 'a')
        else:
            self.logfile = None
        self.msg = streamer.msg
        
        resource.Resource.__init__(self)
        
    def log(self, msg):
        self.msg(msg)
        if not self.logfile:
            return
        
        timestamp = time.strftime('%Y-%m-%d-%H:%M:%S', time.localtime())
        self.logfile.write('%s %s\n' % (timestamp, msg))
        self.logfile.flush()

    def lost(self, obj, fd, ip):
        self.streamer.remove_client(fd)
        self.log('client from %s disconnected' % ip)

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
        self.log('client from %s connected' % ip)
    
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
    
    def set_instance(self, shell):
        print 'setting pipeline', self.pipeline == None, self.pipeline is None
        
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
