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

import sys
    
_sys_argv = sys.argv
sys.argv = sys.argv[:1]

if __name__ == '__main__':
    import gstreactor
    gstreactor.install()

import gobject
import gst

from twisted.web import server, resource
from twisted.internet import reactor
from twisted.python import log

import component

class Streamer(gobject.GObject, component.BaseComponent):
    __gsignals__ = {
        'data-recieved': (gobject.SIGNAL_RUN_FIRST, gobject.TYPE_NONE,
                          (gst.Buffer,)),
    }
    name = 'streamer'
    def __init__(self, name, sources, host, port):
        self.__gobject_init__()
        component.BaseComponent.__init__(self, name, sources, host, port)

    def get_pipeline(self, pipeline):
        if len(self.sources) == 1:
            return 'tcpclientsrc name=%s ! fakesink signal-handoffs=1 silent=1 name=sink' % self.sources[0]

        pipeline = ''
        for source in sources:
            if ' ' in source:
                raise TypeError, "spaces not allowed in sources"

            source_name = '@%s' % source
            if pipeline.find(source_name) == -1:
                raise TypeError, "%s needs to be specified in the pipeline" % source_name
            
            pipeline = pipeline.replace(source_name, 'tcpclientsrc name=%s' % source)

        return pipeline
        
    def sink_handoff_cb(self, element, buffer, pad):
        self.emit('data-recieved', buffer)
        
    def connect_to(self, sources):
        for name, host, port in sources:
            log.msg('Going to connect to %s:%d' % (host, port))
            source = self.pipeline.get_by_name(name)
            source.set_property('host', host)
            source.set_property('port', port)

        sink = self.pipeline.get_by_name('sink')
        sink.connect('handoff', self.sink_handoff_cb)
        
        self.pipeline_play()
     
    def remote_connect(self, sources):
        self.connect_to(sources)
        
gobject.type_register(Streamer)

class StreamingResource(resource.Resource):
    def __init__(self, streamer):
        resource.Resource.__init__(self)

        self.streamer = streamer
        streamer.connect('data-recieved', self.data_recieved_cb)
        
        self.current_requests = []
        
    def data_recieved_cb(self, transcoder, gbuffer):
        for request in self.current_requests:
            self.write(request, str(buffer(gbuffer)))
        
    def getChild(self, path, request):
        return self

    def write(self, request, data):
        # Stolen from camserv
        request.write('--ThisRandomString\n')
        request.write("Content-type: image/jpeg\n\n")
        request.write(data + '\n')

    def lost(self, obj, request):
        print 'client from', request.getClientIP(), 'disconnected'
        self.current_requests.remove(request)
        
    def render(self, request):
        print 'client from', request.getClientIP(), 'connected'
        
        # Stolen from camserv
        request.setHeader('Cache-Control', 'no-cache')
        request.setHeader('Cache-Control', 'private')
        request.setHeader("Content-type", "multipart/x-mixed-replace;;boundary=ThisRandomString")
        request.setHeader('Pragma', 'no-cache')
        
        self.current_requests.append(request)
        request.notifyFinish().addBoth(self.lost, request)
        
        return server.NOT_DONE_YET
    
def main(args):
    options = component.get_options_for('streamer', args)
    comp = Streamer(options.name, options.sources,
                    options.host, options.port)
    
    if options.protocol == 'http':
        factory = server.Site(resource=StreamingResource(comp))
    else:
        print 'Only http protcol supported right now'

    reactor.listenTCP(options.listen_port, factory)
    reactor.run()

if __name__ == '__main__':
    sys.exit(main(_sys_argv))

