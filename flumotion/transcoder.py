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

import socket
import sys

import gobject
import gst

if __name__ == '__main__':
    import gstreactor
    gstreactor.install()

from twisted.spread import pb
from twisted.internet import reactor

class TranscoderFactory(pb.Root):
    def pipeline_iterate(self):
        self.pipeline.iterate()
        return True

    def pipeline_play(self):
        print 'Setting state to playing'
        self.pipeline.set_state(gst.STATE_PLAYING)

    def pipeline_state_change_cb(self, *args):
        pass
    
#        print 'state-changed', args
        
    def error_cb(self, object, element, error, arg):
        print element.get_name(), str(error)

    def remote_start(self, port):
        print 'Transcoder.start'
        self.pipeline = gst.Pipeline('acquisition-thread')
        self.pipeline.connect('state-change', self.pipeline_state_change_cb)
        self.pipeline.connect('error', self.error_cb)
        
        self.src = gst.element_factory_make('tcpserversrc')
        self.src.set_property('port', port)
        self.sink = gst.element_factory_make('xvimagesink')
        self.reframer = gst.element_factory_make('videoreframer')

    def remote_getInfo(self):
        return self.src.get_property('port')
    
    def remote_setController(self, controller):
        self.controller = controller

    def remote_setCaps(self, caps):
        print "Transcoder got caps", caps
        self.pipeline.add_many(self.src, self.reframer, self.sink)
        self.src.link(self.reframer)
        self.reframer.link_filtered(self.sink, gst.caps_from_string(caps))

        gobject.idle_add(self.pipeline_iterate)
        reactor.callLater(0, self.pipeline_play)
        
if __name__ == '__main__':
    factory = pb.PBServerFactory(TranscoderFactory())
    reactor.listenTCP(8803, factory)
    print 'Listening on *:8803'
    reactor.run()
