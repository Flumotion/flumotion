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

class TranscoderFactory(pb.Root):
    def remote_setController(self, controller):
        print "Transcoder.remote_setController", controller
        self.controller = controller

    def remote_startFileSrc(self, filename):
        print 'Transcoder.remote_startFilesrc', filename
        self.thread = gst.Thread('acquisition-thread')
        
        self.src = gst.element_factory_make('filesrc')
        self.src.set_property('location', filename)
        
        self.sink = gst.element_factory_make('xvimagesink')
        self.reframer = gst.element_factory_make('videoreframer')
        
    def remote_setCaps(self, caps):
        print "Transcoder.remote_setCaps", caps
        self.thread.add_many(self.src, self.reframer, self.sink)
        self.src.link(self.reframer)
        self.reframer.link_filtered(self.sink, gst.caps_from_string(caps))
        self.controller.callRemote('transStarted', self)
        
        reactor.callLater(0, self.thread.set_state, gst.STATE_PLAYING)
