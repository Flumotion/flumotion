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
    
import gobject
import gst

if __name__ == '__main__':
    import gstreactor
    gstreactor.install()

from twisted.spread import pb
from twisted.internet import reactor

class AcquisitionFactory(pb.Root):
    def __init__(self, pipeline):
        self.pipeline_string = pipeline
        
    def sink_pad_notify_caps_cb(self, element, pad, caps):
        # XXX: Only do this for fakesinks sink pad
        if not (element.get_name() == 'fakesink' and pad.get_name() == 'sink'):
            return

        caps = pad.get_negotiated_caps()
        if not caps:
            print 'BAD CAPS', str(caps)
            return

        print 'got caps, notifying'
        self.controller.callRemote('acqNotifyCaps', hash(self), str(caps))

    def error_cb(self, object, element, error, arg):
        print element.get_name(), str(error)
        
    def remote_assignRealSink(self, hostname, port):
        print 'swapping sinks', hostname, port

        # Pause
        self.pipeline.set_state(gst.STATE_PAUSED)
        
        # Stream back to the beginning
        event = gst.event_new_seek(gst.FORMAT_TIME |
                                   gst.SEEK_METHOD_SET |
                                   gst.SEEK_FLAG_FLUSH, 0)
        self.sink.send_event(event)

        # Unlink and remove
        self.pipeline.remove(self.sink)
        assert not self.src.unlink(self.sink)

        self.sink = gst.element_factory_make('tcpclientsink')
        self.sink.set_property('host', hostname)
        self.sink.set_property('port', port)
        
        self.sink.connect('error', self.error_cb)
        self.pipeline.add(self.sink)
        self.src.link(self.sink)
 
        reactor.callLater(0, self.pipeline_play)

    def remote_setController(self, object):
        self.controller = object
        return hash(self)
    
    def pipeline_iterate(self):
        self.pipeline.iterate()
        return True

    def pipeline_play(self):
        print 'playing'
        self.pipeline.set_state(gst.STATE_PLAYING)
        
    def remote_start(self):
        print "Acquisition.start()"
        
        self.pipeline = gst.parse_launch('%s ! fakesink name=fakesink' % self.pipeline_string)
        self.pipeline.connect('error', self.error_cb)
        self.src = self.pipeline.get_list()[-2]
        
        self.sink = self.pipeline.get_by_name('fakesink')
        
        # XXX: Disconnect signal?
        self.sink.connect('deep-notify::caps', self.sink_pad_notify_caps_cb)

        reactor.callLater(0, self.pipeline_play)
        gobject.idle_add(self.pipeline_iterate)
        
if __name__ == '__main__':
    factory = pb.PBServerFactory(AcquisitionFactory(sys.argv[1]))
    reactor.listenTCP(8802, factory)
    reactor.run()
