# -*- Mode: Python -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# Flumotion - a streaming media server
# Copyright (C) 2004,2005 Fluendo, S.L. (www.fluendo.com). All rights reserved.

# This file may be distributed and/or modified under the terms of
# the GNU General Public License version 2 as published by
# the Free Software Foundation.
# This file is distributed without any warranty; without even the implied
# warranty of merchantability or fitness for a particular purpose.
# See "LICENSE.GPL" in the source distribution for more information.

# Licensees having purchased or holding a valid Flumotion Advanced
# Streaming Server license may use this file in accordance with the
# Flumotion Advanced Streaming Server Commercial License Agreement.
# See "LICENSE.Flumotion" in the source distribution for more information.

# Headers in this file shall remain intact.

import gst

from flumotion.component import feedcomponent

class LooperMedium(feedcomponent.FeedComponentMedium):
    def __init__(self, comp):
        feedcomponent.FeedComponentMedium.__init__(self, comp)


class Looper(feedcomponent.ParseLaunchComponent):

    component_medium_class = LooperMedium

    def __init__(self, config):
        # setup the properties
        width = config.get('width', 240)
        height = config.get('height', int(576 * width/720.))
        framerate = config.get('framerate', (25, 2))
        location = config.get('location')
        
        # create the component
        template = (
            'filesrc location=%(location)s'
            '       ! oggdemux name=demux'
            '    demux. ! theoradec name=theoradec'
            '       ! videorate'
            '       ! videoscale'
            '       ! video/x-raw-yuv,width=%(width)d,height=%(height)d,framerate=%(framerate)s'
            '       ! queue ! identity name=vident sync=true silent=true check-perfect=true ! @feeder::video@'
            '    demux. ! vorbisdec name=vorbisdec ! audioconvert'
            '       ! audio/x-raw-int,width=16,depth=16,signed=(boolean)true'
            '       ! queue ! identity name=aident sync=true silent=true check-perfect=true ! @feeder::audio@'
            % dict(location=location, width=width,
                   height=height, framerate=('%d/%d' % (framerate[0], framerate[1]))))
        
        feedcomponent.ParseLaunchComponent.__init__(self, config['name'],
                                                    [],
                                                    ['video', 'audio'],
                                                    template)
        self.initial_seek = False

    def _message_cb(self, bus, message):
        if message.src == self.pipeline and message.type == gst.MESSAGE_SEGMENT_DONE:
            # let's looooop again :)
            gst.debug("sending segment seek again")
            self.oggdemux.seek(1.0, gst.FORMAT_TIME, gst.SEEK_FLAG_SEGMENT,
                               gst.SEEK_TYPE_SET, 0, gst.SEEK_TYPE_END, 0)
        elif message.src == self.oggdemux and message.type == gst.MESSAGE_STATE_CHANGED:
            gst.debug("got state changed on oggdemux")
            old, new, pending = message.parse_state_changed()
            if old == gst.STATE_NULL and new == gst.STATE_READY and not self.initial_seek:
                # initial segment seek
                gst.debug("send initial seek")
                self.oggdemux.seek(1.0, gst.FORMAT_TIME, gst.SEEK_FLAG_SEGMENT | gst.SEEK_FLAG_FLUSH,
                                   gst.SEEK_TYPE_SET, 0, gst.SEEK_TYPE_END, 0)
                self.initial_seek = True

    def start(self, eatersData, feedersData):
        self.oggdemux = self.pipeline.get_by_name("demux")

        gst.warning("CAN I EVEN OUTPUT DEBUG MESSAGES ?????????")

        self.bus = self.pipeline.get_bus()
        self.bus.add_signal_watch()
        self.bus.connect('message', self._message_cb)

        # send initial segment-seek
        #self.pipeline.seek(1.0, gst.FORMAT_TIME, gst.SEEK_FLAG_SEGMENT,
        #                   gst.SEEK_TYPE_NONE, 0, gst.SEEK_TYPE_NONE, 0)

        feedcomponent.ParseLaunchComponent.start(self, eatersData, feedersData)
