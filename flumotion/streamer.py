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
import sys
import string

if __name__ == '__main__':
    import gstreactor
    gstreactor.install()

import gobject
import gst
from twisted.web import server, resource
from twisted.internet import reactor

import component
import errors
import log

def msg(*args):
    log.msg('streamer', *args)
    
def warn(*args):
    log.warning('streamer', *args)

class Streamer(gobject.GObject, component.BaseComponent):
    __gsignals__ = {
        'data-received' : (gobject.SIGNAL_RUN_FIRST, gobject.TYPE_NONE,
                          (gst.Buffer,)),
    }

    kind = 'streamer'
    pipe_template = 'fakesink signal-handoffs=1 silent=0 name=sink'
    
    def __init__(self, name, sources):
        self.__gobject_init__()
        component.BaseComponent.__init__(self, name, sources, self.pipe_template)
        self.caps = None
        
    def sink_handoff_cb(self, element, buffer, pad):
        self.emit('data-received', buffer)
        
    def notify_caps_cb(self, element, pad, param):
        msg('Got caps: %s' % pad.get_negotiated_caps())
        
        if not self.caps is None:
            warn('Already had caps: %s, replacing' % self.caps)

        msg('Storing caps: %s' % pad.get_negotiated_caps())
        self.caps = pad.get_negotiated_caps()

    # connect() is already taken by gobject.GObject
    def connect_to(self, sources):
        self.setup_sources(sources)
        sink = self.get_sink()
        sink.connect('handoff', self.sink_handoff_cb)
        sink.connect('deep-notify::caps', self.notify_caps_cb)
        
        self.pipeline_play()

    remote_connect = connect_to
        
gobject.type_register(Streamer)

class StreamingResource(resource.Resource):
    def __init__(self, streamer):
        resource.Resource.__init__(self)
        self.streamer = streamer
        self.streamer.connect('data-received', self.data_received_cb)
        
        self.current_requests = []
        self.buffer_queue = []

        self.first_buffer = None
        self.caps_buffers = []
        
        reactor.callLater(0, self.bufferWrite)

    def data_received_cb(self, transcoder, gbuffer):
        s = str(buffer(gbuffer))
        if gbuffer.flag_is_set(gst.BUFFER_IN_CAPS):
            msg('Received a GST_BUFFER_IN_CAPS buffer')
            self.caps_buffers.append(s)
        else:
            if not self.first_buffer:
                msg('Received the first buffer')
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
        msg('client from %s disconnected' % request.getClientIP()) 
        self.current_requests.remove(request)

    def isReady(self):
        if self.streamer.caps is None:
            msg('We have no caps yet')
            return False
        
        if self.first_buffer is None:
            msg('We still haven\'t received any buffers')
            return False

        return True
        
    def render(self, request):
        msg('client from %s connected' % request.getClientIP())   
        if not self.isReady():
            msg('Not sending data, it\'s not ready')
            return server.NOT_DONE_YET

        mime = self.streamer.caps.get_structure(0).get_name()
        if mime == 'multipart/x-mixed-replace':
            msg('setting Content-type to %s but with camserv hack' % mime)
            # Stolen from camserv
            request.setHeader('Cache-Control', 'no-cache')
            request.setHeader('Cache-Control', 'private')
            request.setHeader("Content-type", "%s;boundary=ThisRandomString" % mime)
        else:
            msg('setting Content-type to %s' % mime)
            request.setHeader('Content-type', mime)
        
        for buffer in self.caps_buffers:
            request.write(buffer)
            
        self.current_requests.append(request)
        request.notifyFinish().addBoth(self.lost, request)
        
        return server.NOT_DONE_YET

def main(args):
    options = component.get_options_for('streamer', args)
    try:
        client = Streamer(options.name, options.sources)
    except errors.PipelineParseError, e:
        print 'Bad pipeline: %s' % e
        raise SystemExit
    
    if options.protocol == 'http':
        web_factory = server.Site(resource=StreamingResource(client))
    else:
        print 'Only http protcol supported right now'

    reactor.connectTCP(options.host, options.port, client.factory)
    reactor.listenTCP(options.listen_port, web_factory)
    reactor.run()

if __name__ == '__main__':
    sys.exit(main(sys.argv))

