# -*- Mode: Python -*-
# Flumotion - a video streaming server
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
#

import pygtk
pygtk.require('2.0')

import re
import socket
import sys
    
import gobject
import gst

if __name__ == '__main__':
    import gstreactor
    gstreactor.install()

from twisted.internet import reactor
from twisted.python import log
from twisted.spread import pb

import pbutil

def verbose_deep_notify_cb(object, orig, pspec):
    value = orig.get_property(pspec.name)
    if pspec.value_type == gobject.TYPE_BOOLEAN:
        if value:
            value = 'TRUE'
        else:
            value = 'FALSE'
                
    log.msg('deep-notify %s: %s = %s' % (orig.get_path_string(),
                                         pspec.name,
                                         value))

class Transcoder(gobject.GObject, pb.Referenceable):
    __gsignals__ = {
        'data-recieved': (gobject.SIGNAL_RUN_FIRST, gobject.TYPE_NONE,
                          (gst.Buffer,)),
    }
    def __init__(self, username, host, port, pipeline):
        self.__gobject_init__()
        self.host = host
        factory = pb.PBClientFactory()
        reactor.connectTCP(host, port, factory)
        defered = factory.login(pbutil.Username('trans_%s' % username),
                                client=self)
        defered.addCallback(self.got_perspective_cb)
        self.pipeline_string = pipeline
        
    def got_perspective_cb(self, persp):
        self.persp = persp
        
    def pipeline_error_cb(self, object, element, error, arg):
        log.msg('element %s error %s %s' % (element.get_path_string(), str(error), repr(arg)))
        self.persp.callRemote('error', element.get_path_string(), error.message)

    def pipeline_state_change_cb(self, element, old, state):
        log.msg('pipeline state-changed %s %s -> %s' % (element.get_path_string(),
                                                        gst.element_state_get_name(old),
                                                        gst.element_state_get_name(state)))
        self.persp.callRemote('stateChanged', old, state)
        
    def pipeline_pause(self):
        retval = self.pipeline.set_state(gst.STATE_PAUSED)
        if not retval:
            log.msg('Changing state to PAUSED failed')
        gobject.idle_add(self.pipeline.iterate)
        
    def pipeline_play(self):
        retval = self.pipeline.set_state(gst.STATE_PLAYING)
        if not retval:
            log.msg('Changing state to PLAYING failed')
        gobject.idle_add(self.pipeline.iterate)
        
    def prepare(self, element_name):
        
        log.msg('prepare called')

        #pipe = '%s name=source ! %s ! tcpclientsink name=sink'
        pipe = '%s name=source ! %s ! fakesink name=sink silent=1 signal-handoffs=1'
        self.pipeline = gst.parse_launch(pipe % (element_name, self.pipeline_string))
        self.pipeline.connect('deep-notify', verbose_deep_notify_cb)
        self.pipeline.connect('error', self.pipeline_error_cb)
        self.pipeline.connect('state-change', self.pipeline_state_change_cb)

        source = self.pipeline.get_by_name('source')
            
        sink = self.pipeline.get_list()[-1]

        if 'handoff' in gobject.signal_list_names(sink):
            log.msg('connecting handoff on %r' % sink)
            sink.connect('handoff', self.sink_handoff_cb)
        else:
            log.msg('%r does not support the handoff signal' % sink)

        return source
    
    def sink_handoff_cb(self, object, buffer, pad):
        self.emit('data-recieved', buffer)

    def connect_to(self, host, port):
        log.msg('Going to connect to %s:%d' % (host, port))
        
        source = self.prepare('tcpclientsrc')
        source.set_property('host', host)
        source.set_property('port', port)

        reactor.callLater(0, self.pipeline_play)

    def listen(self, port):
        log.msg('Going to listen on port %d' % port)
        
        source = self.prepare('tcpserversrc')
        source.set_property('port', port)

        reactor.callLater(0, self.pipeline_play)
        log.msg('returning from listen')

    def remote_connect(self, host, port):
        self.connect_to(host, port)
        
    def remote_listen(self, port):
        self.listen(port)

    def remote_prepare(self):
        return socket.gethostbyname(self.host)
    
"tcpclientsrc host=foobar ! tcpclientsink"

gobject.type_register(Transcoder)

from twisted.web import server, resource
from twisted.internet import reactor

class StreamingResource(resource.Resource):
    def __init__(self, client):
        resource.Resource.__init__(self)
        
        client.connect('data-recieved', self.data_recieved_cb)
        self.current_requests = []
        
    def data_recieved_cb(self, transcoder, gstbuffer):
        data = str(buffer(gstbuffer))
        #log.msg('Data of len %d coming in' % len(data))
        
        for request in self.current_requests:
            self.write(request, data)
        
    def getChild(self, path, request):
        return self

    def write(self, request, data):
        request.write('--ThisRandomString\n')
        request.write("Content-type: image/jpeg\n\n")
        request.write(data + '\n')

    def lost(self, obj, request):
        print 'client from', request.getClientIP(), 'disconnected'
        self.current_requests.remove(request)
        
    def render(self, request):
        print 'client from', request.getClientIP(), 'connected'
        request.setHeader('Cache-Control', 'no-cache')
        request.setHeader('Cache-Control', 'private')
        request.setHeader("Content-type", "multipart/x-mixed-replace;;boundary=ThisRandomString")
        request.setHeader('Pragma', 'no-cache')
        self.current_requests.append(request)
        request.notifyFinish().addBoth(self.lost, request)
        
        return server.NOT_DONE_YET
    
#         NO = 200
#         DELAY = 0.500
#         for i in range(NO):
#             reactor.callLater(DELAY*i,     self.write, request, self.data)
#             reactor.callLater(DELAY*(i+1), self.write, request, self.data2)
#         reactor.callLater(DELAY*(NO+1), request.finish)
        
#         return server.NOT_DONE_YET
        
def parseHostString(string, port=8890):
    if not string:
        return 'localhost', port
    
    try:
        host, port = re.search(r'(.+):(\d+)', string).groups()
    except:
        host = string
        
    return host, port
    
if __name__ == '__main__':
    log.startLogging(sys.stdout)

    if len(sys.argv) == 2:
        pipeline = sys.argv[1]
        controller = ''
    elif len(sys.argv) == 3:
        pipeline = sys.argv[1] 
        controller = sys.argv[2]
    else:
        print 'Usage: transcoder.py pipeline [controller-host[:port]]'
        sys.exit(2)
        
    name = 'johan'
    host, port = parseHostString(controller)
    log.msg('Connect to %s on port %d' % (host, port))
    client = Transcoder(name, host, port, pipeline)
    reactor.listenTCP(8804, server.Site(resource=StreamingResource(client)))
    reactor.run()
