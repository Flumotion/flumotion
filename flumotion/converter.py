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

import sys

# Workaround for non existent popt integration
_sys_argv = sys.argv
sys.argv = sys.argv[:1] # + ['--gst-debug=*:5']

if __name__ == '__main__':
    import gstreactor
    gstreactor.install()
    
import gst

from twisted.internet import reactor
from twisted.python import log

import component
import gstutils

class Converter(component.BaseComponent):
    name = 'converter'
    def __init__(self, name, sources, host, port, pipeline):
        component.BaseComponent.__init__(self, name, sources, host, port, pipeline)

    def get_pipeline(self, pipeline):
        if len(self.sources) == 1:
            return 'tcpclientsrc name=%s ! %s ! tcpserversink name=sink' % (self.sources[0], pipeline)

        for source in self.sources:
            if ' ' in source:
                raise TypeError, "spaces not allowed in sources"
            
            source_name = '@%s' % source
            if pipeline.find(source_name) == -1:
                raise TypeError, "%s needs to be specified in the pipeline" % source_name
            
            pipeline = pipeline.replace(source_name, 'tcpclientsrc name=%s' % source)

        return pipeline + ' ! tcpserversink name=sink'

    def start(self, sources, sink_host, sink_port):
        log.msg('(source) Going to listen on port %s:%d' % (sink_host, sink_port))

        # Setup all sources
        for source_name, source_host, source_port in sources:
            log.msg('(sink)   Going to connect to %s (%s:%d)' % (source_name,
                                                                 source_host, source_port))
            source = self.pipeline.get_by_name(source_name)
            source.set_property('host', source_host)
            source.set_property('port', source_port)

        # Setup the sink
        sink = self.pipeline.get_by_name('sink')
        sink.set_property('host', sink_host)
        sink.set_property('port', sink_port)

        # Play
        self.pipeline_play()
        
    def remote_start(self, sources, sink_host, sink_port):
        self.start(sources, sink_host, sink_port)
        
def main(args):
    try:
        options = component.get_options_for('converter', args)
    except component.OptionError, e:
        print 'ERROR:', e
        raise SystemExit
    
    client = Converter(options.name, options.sources, options.host,
                       options.port, options.pipeline)
    reactor.run()
    
if __name__ == '__main__':
    sys.exit(main(_sys_argv))
