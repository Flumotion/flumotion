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
    def __init__(self):
        self.thread = None

    def sink_pad_notify_caps_cb(self, pad, unused):
        caps = pad.get_negotiated_caps()
        if not caps:
            return

        self.controller.callRemote('acqNotifyCaps', self, str(caps))

        #self.sink.get_pad('sink').disconnect(self.sig_id)
        reactor.callLater(0, self.assignRealSink)

    def assignRealSink(self):
        self.thread.set_state(gst.STATE_PAUSED)
        # Pause, unlink and remove
        self.thread.remove(self.sink)
        self.src.unlink(self.sink)

        # Create new, add and link and play
        self.sink = gst.element_factory_make('filesink')
        self.sink.set_property('location', self.filename)
        self.thread.add(self.sink)
        self.src.link(self.sink)
        
        self.thread.set_state(gst.STATE_PLAYING)
        
    def remote_setController(self, controller):
        print "Acquisition.remote_setController", controller
        self.controller = controller

    def remote_startFileSink(self, filename):
        print "Acquisition.remote_startFileSink", filename
        self.filename = filename
        
        self.thread = gst.Thread('acquisition-thread')

        self.src = gst.element_factory_make('videotestsrc')
        self.sink = gst.element_factory_make('fakesink')
        
        pad = self.sink.get_pad('sink')
        self.sig_id = pad.connect('notify::caps', self.sink_pad_notify_caps_cb)
        
        self.thread.add_many(self.src, self.sink)
        self.src.link(self.sink)
        
        self.thread.set_state(gst.STATE_PLAYING)
