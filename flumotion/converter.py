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

import optik
import socket
import sys

# Workaround for non existent popt integration
_sys_argv = sys.argv
sys.argv = sys.argv[:1]

# XXX: Why does this have to be done before the reactor import?
#      Find out a better way
if __name__ == '__main__':
    import gstreactor
    gstreactor.install()
    
import gst

from twisted.internet import reactor
from twisted.python import log

from component import Component
import gstutils

class Converter(Component):
    name = 'converter'
    def __init__(self, name, source, host, port, pipeline):
        Component.__init__(self, name, source, host, port)
        self.pipeline_string = 'tcpclientsrc name=source ! ' + \
                               '%s ! tcpserversink name=sink' % pipeline
        self.source = source
        
    def start(self, source_host, source_port, sink_host, sink_port):
        log.msg('(source) Going to listen on port %s:%d' % (source_host, source_port))
        log.msg('(sink)   Going to connect to %s:%d' % (sink_host, sink_port))
        
        source = self.pipeline.get_by_name('source')
        source.set_property('host', source_host)
        source.set_property('port', source_port)

        sink = self.pipeline.get_by_name('sink')
        sink.set_property('host', sink_host)
        sink.set_property('port', sink_port)
        
        self.pipeline_play()

    def remote_start(self, source_host, source_port, sink_host, sink_port):
        self.start(source_host, source_port, sink_host, sink_port)
        
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
    parser.add_option('-p', '--pipeline',
                      action="store", type="string", dest="pipeline",
                      default=None,
                      help="Pipeline to run")
    parser.add_option('-s', '--source',
                      action="store", type="string", dest="source",
                      default=None,
                      help="Host source to get data from")
    parser.add_option('-v', '--verbose',
                      action="store_true", dest="verbose",
                      help="Be verbose")

    options, args = parser.parse_args(args)

    if options.pipeline is None:
        print 'Need a pipeline'
        return 2

    if options.name is None:
        print 'Need a name'
        return 2

    if options.source is None:
        print 'Need a source'
        return 2
    
    if options.verbose:
        log.startLogging(sys.stdout)

    if ':' in options.host:
        host, port = options.split(options.host)
    else:
        host = options.host
        port = 8890

    log.msg('Connect to %s on port %d' % (host, port))
    client = Converter(options.name, options.source, host, port,
                       options.pipeline)
    reactor.run()
    
if __name__ == '__main__':
    sys.exit(main(_sys_argv))
