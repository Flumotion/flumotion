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
sys.argv = sys.argv[:1]

if __name__ == '__main__':
    import gstreactor
    gstreactor.install()
    
import gst
from twisted.internet import reactor
from twisted.python import log

import component

class Producer(component.BaseComponent):
    name = 'producer'
    def __init__(self, name, host, port, pipeline):
        component.BaseComponent.__init__(self, name, None, host, port, pipeline)

    def get_pipeline(self, pipeline):
        return '%s ! tcpserversink name=sink' % pipeline
        
    def listen(self, host, port):
        log.msg('Going to listen on port %d' % port)

        sink = self.pipeline.get_by_name('sink')
        sink.set_property('host', host)
        sink.set_property('port', port)
        
        self.pipeline_play()
        
    def remote_listen(self, host, port):
        self.listen(host, port)
        
def main(args):
    try:
        options = component.get_options_for('producer', args)
    except component.OptionError, e:
        print 'ERROR:', e
        raise SystemExit
    
    client = Producer(options.name, options.host, options.port, options.pipeline)
    reactor.run()

if __name__ == '__main__':
    sys.exit(main(_sys_argv))
