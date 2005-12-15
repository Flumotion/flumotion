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
import gobject

from flumotion.common import errors
from flumotion.component import feedcomponent

class LooperMedium(feedcomponent.FeedComponentMedium):
    def __init__(self, comp):
        feedcomponent.FeedComponentMedium.__init__(self, comp)

    def remote_gimme5(self, text):
        return self.comp.restart_looping()

    def remote_getNbIterations(self):
        return self.comp.nbiterations

    def remote_getFileInformation(self):
        return self.comp.fileinformation


class Looper(feedcomponent.ParseLaunchComponent):

    component_medium_class = LooperMedium

    def get_pipeline_string(self, properties):
        # setup the properties
        self.bus = None
        self.videowidth = properties.get('width', 240)
        self.videoheight = properties.get('height', int(576 * self.videowidth/720.))
        self.videoframerate = properties.get('framerate', (25, 2))
        self.filelocation = properties.get('location')

        vstruct = gst.structure_from_string("video/x-raw-yuv,width=%(width)d,height=%(height)d" %
                                            dict (width=self.videowidth, height=self.videoheight))
        vstruct['framerate'] = gst.Fraction(self.videoframerate[0],
                                            self.videoframerate[1])

        vcaps = gst.Caps(vstruct)
        
        self.initial_seek = False
        self.nbiterations = 0

        self.discovered = False
        try:
            from gst.extend import discoverer
        except ImportError:
            raise errors.ComponentError(
                'Could not import gst.extend.discoverer.  '
                'You need at least GStreamer Python Bindings 0.10.1')

        self.discoverer = discoverer.Discoverer(self.filelocation)
        self.discoverer.connect('discovered', self._filediscovered)
        self.discoverer.discover()
        self.fileinformation = None

        self.timeoutid = 0

        # create the component
        template = (
            'filesrc location=%(location)s'
            '       ! oggdemux name=demux'
            '    demux. ! theoradec name=theoradec'
            '       ! identity name=videolive single-segment=true silent=true'
            '       ! videorate name=videorate'
            '       ! videoscale'
            '       ! %(vcaps)s'
            '       ! queue ! identity name=vident sync=true silent=true ! @feeder::video@'
            '    demux. ! vorbisdec name=vorbisdec ! identity name=audiolive single-segment=true silent=true'
            '       ! audioconvert'
            '       ! audio/x-raw-int,width=16,depth=16,signed=(boolean)true'
            '       ! queue ! identity name=aident sync=true silent=true ! @feeder::audio@'
            % dict(location=self.filelocation, vcaps=vcaps))

        return template

    def _filediscovered(self, discoverer, ismedia):
        self.discovered = True
        info = {}
        info["location"] = self.filelocation
        info["duration"] = max(discoverer.audiolength, discoverer.videolength)
        if discoverer.is_audio:
            info["audio"] = "%d channel(s) %dHz" % (discoverer.audiochannels,
                                                    discoverer.audiorate)
        if discoverer.is_video:
            info["video"] = "%d x %d at %d/%d fps" % (discoverer.videowidth,
                                                      discoverer.videoheight,
                                                      discoverer.videorate.num,
                                                      discoverer.videorate.denom)
        self.fileinformation = info
        self.adminCallRemote("haveFileInformation", info)

    def _message_cb(self, bus, message):
        if message.src == self.pipeline and message.type == gst.MESSAGE_SEGMENT_DONE:
            # let's looooop again :)
            self.debug("sending segment seek again")
            self.nbiterations += 1
            self.oggdemux.seek(1.0, gst.FORMAT_TIME, gst.SEEK_FLAG_SEGMENT,
                               gst.SEEK_TYPE_SET, 0, gst.SEEK_TYPE_END, 0)
            self.adminCallRemote("numberIterationsChanged", self.nbiterations)
        elif message.src == self.oggdemux and message.type == gst.MESSAGE_STATE_CHANGED:
            gst.debug("got state changed on oggdemux")
            old, new, pending = message.parse_state_changed()
            if old == gst.STATE_NULL and new == gst.STATE_READY and not self.initial_seek:
                # initial segment seek
                gst.debug("send initial seek")
                self.oggdemux.seek(1.0, gst.FORMAT_TIME, gst.SEEK_FLAG_SEGMENT | gst.SEEK_FLAG_FLUSH,
                                   gst.SEEK_TYPE_SET, 0, gst.SEEK_TYPE_END, 0)
                self.initial_seek = True
        elif message.src == self.pipeline and message.type == gst.MESSAGE_STATE_CHANGED:
            old, new, pending = message.parse_state_changed()
            if new == gst.STATE_PLAYING:
                self.debug("Starting time update timeout")
                if not self.timeoutid:
                    self.timeoutid = gobject.timeout_add(500, self._check_time)

    def _check_time(self):
        self.log("checking position")
        try:
            pos, format = self.pipeline.query_position(gst.FORMAT_TIME)
        except:
            self.debug("position query didn't succeed")
        else:
            self.adminCallRemote("haveUpdatedPosition", pos)
        return True

    def restart_looping(self):
        """
        Restarts the looping.
        
        Returns True if the seeking was accepted,
        Returns False otherwiser
        """
        self.debug("restarting looping")
        return self.oggdemux.seek(1.0, gst.FORMAT_TIME, gst.SEEK_FLAG_SEGMENT,
                                  gst.SEEK_TYPE_SET, 0, gst.SEEK_TYPE_END, 0)

    def _probe(self, element, buffer, detail):
        if isinstance(buffer, gst.Buffer):
            self.debug("%s: [%s -- %s]" % (detail,
                                           gst.TIME_ARGS(buffer.timestamp),
                                           gst.TIME_ARGS(buffer.timestamp + buffer.duration)))
        else:
            self.debug("%s: EVENT %s" % (detail, buffer))
        return True

    def start(self, eatersData, feedersData, clocking):
        self.oggdemux = self.pipeline.get_by_name("demux")

        self.bus = self.pipeline.get_bus()
        self.bus.add_signal_watch()
        self.bus.connect('message', self._message_cb)
        self.nbiterations = 0
        self.adminCallRemote("numberIterationsChanged", 5)

        feedcomponent.ParseLaunchComponent.start(self, eatersData, feedersData, clocking)

    def stop(self):
        if self.bus:
            self.bus.remove_signal_watch()
        if self.timeoutid:
            gobject.source_remove(self.timeoutid)
            self.timeoutid = 0
        self.nbiterations = 0
        self.adminCallRemote("numberIterationsChanged", self.nbiterations)
