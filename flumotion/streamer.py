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

import pygtk
pygtk.require('2.0')

import sys
    
# Workaround for non existent popt integration
_sys_argv = sys.argv
sys.argv = sys.argv[:1]

# XXX: Why does this have to be done before the reactor import?
#      Find out a better way
if __name__ == '__main__':
    import gstreactor
    gstreactor.install()

import optik
import time

import gobject
import gst
from twisted.web import server, resource
from twisted.internet import reactor
from twisted.python import log

from component import Component

class Streamer(gobject.GObject, Component):
    __gsignals__ = {
        'data-recieved': (gobject.SIGNAL_RUN_FIRST, gobject.TYPE_NONE,
                          (gst.Buffer,)),
    }
    name = 'streamer'
    def __init__(self, name, sources, host, port):
        self.__gobject_init__()
        Component.__init__(self, name, sources, host, port)
        self.pipeline_string = 'fakesink signal-handoffs=1 silent=1 name=sink'
        for source in sources:
            self.pipeline_string.replace(source, 'identify name=%s_placeholder' % source)
        
    def sink_handoff_cb(self, element, buffer, pad):
        self.emit('data-recieved', buffer)
        
    def connect_to(self, name, host, port):
        log.msg('Going to connect to %s:%d' % (host, port))

        old = self.pipeline.get_by_name('%s_placeholder' % name)

        source = gst.element_factory_make('tcpclientsrc', source)
        source.set_property('host', host)
        source.set_property('port', port)

        sink = self.pipeline.get_by_name('sink')
        sink.connect('handoff', self.sink_handoff_cb)
        
        self.pipeline_play()
     
    def remote_connect(self, host, port):
        self.connect_to(host, port)
        
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
    parser = optik.OptionParser()
    parser.add_option('-c', '--controller',
                      action="store", type="string", dest="host",
                      default="localhost:8890",
                      help="Controller to connect to default localhost:8890]")
    parser.add_option('-n', '--name',
                      action="store", type="string", dest="name",
                      default=None,
                      help="Name of component")
    parser.add_option('-p', '--protocol',
                      action="store", type="string", dest="protocol",
                      default=None,
                      help="Protocol to use")
    parser.add_option('-o', '--port',
                      action="store", type="int", dest="port",
                      default=None,
                      help="Port to bind to")
    parser.add_option('-s', '--source',
                      action="store", type="string", dest="source",
                      default=None,
                      help="Host source to get data from")
    parser.add_option('-v', '--verbose',
                      action="store_true", dest="verbose",
                      help="Be verbose")

    options, args = parser.parse_args(args)

    if options.name is None:
        print 'Need a name'
        return 2

    if options.source is None:
        print 'Need a source'
        return 2

    if options.protocol is None:
        print 'Need a protocol'
        return 2

    if options.port is None:
        print 'Need a port'
        return 2
    
    if options.verbose:
        log.startLogging(sys.stdout)

    port = 8890
    if options.host is None:
        host = 'localhost'
    elif ':' in options.host:
        host, port = options.split(options.host)
    else:
        host = options.host

    component = Streamer(options.name, options.source, host, port)
    
    if options.protocol == 'http':
        factory = server.Site(resource=StreamingResource(component))
    else:
        print 'Only http protcol supported right now'

    log.msg('Connect to controller %s on port %d' % (host, port))

    reactor.listenTCP(options.port, factory)
    reactor.run()

if __name__ == '__main__':
    sys.exit(main(_sys_argv))

