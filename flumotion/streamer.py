# -*- Mode: Python -*-
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
#

import time
import sys
    
import gobject
import gst

if __name__ == '__main__':
    import gstreactor
    gstreactor.install()

from twisted.web import server, resource
from twisted.internet import reactor

class Streamer(gobject.GObject):
    __gsignals__ = {
        'data-recieved': (gobject.SIGNAL_RUN_FIRST, gobject.TYPE_NONE,
                          (gst.Buffer,)),
    }
    def __init__(self, hostname, port):
        self.hostname = hostname
        self.port = port
        
        self.create_pipeline()

    def pipeline_pause(self):
        retval = self.pipeline.set_state(gst.STATE_PAUSED)
        if not retval:
            log.msg('WARNING: Changing state to PLAYING failed')
        gobject.idle_add(self.pipeline.iterate)
        
    def pipeline_play(self):
        retval = self.pipeline.set_state(gst.STATE_PLAYING)
        if not retval:
            log.msg('WARNING: Changing state to PLAYING failed')
        gobject.idle_add(self.pipeline.iterate)

    def create_pipeline(self):
        pipeline = gst.parse_launch('tcpclientsrc name=source ! '
                                    'fakesink name=sink signals-handoff=1 silent=1')
        sink = pipeline.get_by_name('sink')
        sink.connect('handoff', self.sink_handoff_cb)

    def sink_handoff_cb(self, element, buffer, pad):
        print 'GOT DATA'
    
class StreamerResource(resource.Resource):
    def __init__(self, client):
        resource.Resource.__init__(self)

        client = StreamerComponent()
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

if __name__ == '__main__':
    reactor.listenTCP(8804, server.Site(resource=SimpleResource()))
    print 'Listening on *:8804'
    reactor.run()
