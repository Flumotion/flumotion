# -*- Mode: Python -*-
# vi:si:et:sw=4:sts=4:ts=4

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

import sys

if __name__ == '__main__':
    import gstreactor
    gstreactor.install()
    
import gst

from twisted.internet import reactor

from flumotion.server import component
from flumotion.utils import log
from flumotion import errors

def msg(*args):
    log.msg('converter', *args)
    
class Converter(component.BaseComponent):
    kind = 'converter'
    def start(self, sources, sink_host, sink_port):
        self.setup_sources(sources)
        
        msg('Going to listen on %s:%d' % (sink_host, sink_port))
        self.set_sink_properties(host=sink_host, port=sink_port)

        self.pipeline_play()

    remote_start = start
        
def main(args):
    try:
        options = component.get_options_for('converter', args)
    except component.OptionError, e:
        print 'ERROR:', e
        raise SystemExit
    
    try:
        client = Converter(options.name, options.sources,
                           options.pipeline)
    except errors.PipelineParseError, e:
        print 'Bad pipeline: %s' % e
        raise SystemExit
    
    reactor.connectTCP(options.host, options.port, client.factory)
    reactor.run()
    
if __name__ == '__main__':
    sys.exit(main(sys.argv))
