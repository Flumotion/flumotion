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

import gst
from twisted.spread import pb
from twisted.internet import reactor

class AcquisitionFactory(pb.Root):
    def __init__(self, pipeline):
        self.pipeline = pipeline
        
        self.thread = gst.parse_launch('{ %s }' % pipeline)
        self.src = self.thread.get_list()[-1]

        self.sink = gst.element_factory_make('fakesink')
        
        # XXX: Disconnect?
        pad = self.sink.get_pad('sink')
        pad.connect('notify::caps', self.sink_pad_notify_caps_cb)

        self.thread.add(self.sink)
        self.src.link(self.sink)
        
    def sink_pad_notify_caps_cb(self, pad, unused):
        print 'got caps, notifying'

        caps = pad.get_negotiated_caps()
        if not caps:
            return

        self.control.callRemote('acqNotifyCaps', hash(self), str(caps))

        # 
        #reactor.callLater(0, self.assignRealSink)
        
    def remote_assignRealSink(self):
        print 'swapping sinks'
        
        self.thread.set_state(gst.STATE_PAUSED)
        
        # Pause, unlink and remove
        self.thread.remove(self.sink)
        self.src.unlink(self.sink)

        # Create new, add and link and play
        #self.sink = gst.element_factory_make('filesink')
        #self.sink.set_property('location', self.filename)
        self.sink = gst.element_factory_make('tcpclientsink')
        self.thread.add(self.sink)
        self.src.link(self.sink)

        self.thread.set_state(gst.STATE_PLAYING)

    def remote_setController(self, object):
        print 'Acquisition.setController', object
        self.control = object
        return hash(self)
    
    def remote_setTranscoder(self, object):
        print 'Acquisition.setTranscoder', object
        self.transcoder = object
        
    def remote_startFileSink(self, filename):
        print "Acquisition.remote_startFileSink", filename
        self.filename = filename
        self.thread.set_state(gst.STATE_PLAYING)
        
if __name__ == '__main__':
    import sys
    
    factory = pb.PBServerFactory(AcquisitionFactory(sys.argv[1]))
    reactor.listenTCP(8802, factory)
    reactor.run()
