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
import errors

class Streamer(gobject.GObject, component.BaseComponent):
    __gsignals__ = {
        'data-recieved': (gobject.SIGNAL_RUN_FIRST, gobject.TYPE_NONE,
                          (gst.Buffer,)),
    }

    kind = 'streamer'
    def __init__(self, name, sources):
        self.__gobject_init__()
        component.BaseComponent.__init__(self, name, sources)

    def sink_handoff_cb(self, element, buffer, pad):
        self.emit('data-recieved', buffer)

    # connect() is already taken by gobject.GObject
    def connect_to(self, sources):
        self.setup_sources(sources)
        sink = self.get_sink()
        sink.connect('handoff', self.sink_handoff_cb)
        
        self.pipeline_play()

    remote_connect = connect_to
        
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
    sys.exit(main(_sys_argv))

