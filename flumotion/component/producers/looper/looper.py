# -*- Mode: Python -*-
# vi:si:et:sw=4:sts=4:ts=4

# Flumotion - a streaming media server
# Copyright (C) 2004,2005,2006,2007,2008,2009 Fluendo, S.L.
# Copyright (C) 2010,2011 Flumotion Services, S.A.
# All rights reserved.
#
# This file may be distributed and/or modified under the terms of
# the GNU Lesser General Public License version 2.1 as published by
# the Free Software Foundation.
# This file is distributed without any warranty; without even the implied
# warranty of merchantability or fitness for a particular purpose.
# See "LICENSE.LGPL" in the source distribution for more information.
#
# Headers in this file shall remain intact.

import gst
import gobject

from flumotion.common import errors, messages
from flumotion.common.i18n import N_, gettexter
from flumotion.component import feedcomponent
from flumotion.component.common.avproducer import avproducer

__version__ = "$Rev$"
T_ = gettexter()


class LooperMedium(feedcomponent.FeedComponentMedium):

    def __init__(self, comp):
        feedcomponent.FeedComponentMedium.__init__(self, comp)

    def remote_restartLoop(self):
        return self.comp.do_seek(False)

    def remote_getNbIterations(self):
        return self.comp.nbiterations

    def remote_getFileInformation(self):
        return self.comp.fileinformation


# How to start the first segment:
# 1) Make your pipeline, but don't link the sinks
# 2) Block the source pads of what would be the sinks' peers
# 3) When both block functions fire, link the pads, then do a segment seek
# 4) Then you can unblock pads and the sinks will receive exactly one
# new segment with all gst versions
#
# To loop a segment, when you get the segment_done message
# asynchronously, just do a new segment seek.


class Looper(avproducer.AVProducerBase):

    componentMediumClass = LooperMedium

    def init(self):
        self.initial_seek = False
        self.nbiterations = 0
        self.fileinformation = None
        self.timeoutid = 0
        self.pads_awaiting_block = []
        self.pads_to_link = []
        self.bus = None
        self.uiState.addKey('info-location', '')
        self.uiState.addKey('info-duration', 0)
        self.uiState.addKey('info-audio', None)
        self.uiState.addKey('info-video', None)
        self.uiState.addKey('num-iterations', 0)
        self.uiState.addKey('position', 0)

    def _do_extra_checks(self):
        from flumotion.component.producers import checks
        version = checks.get_pygst_version(gst)
        if version >= (0, 10, 11, 0) and version < (0, 10, 14, 0):
            # if it's going to segfault it won't have time to deliver
            # messages to manager, otherwise we don't need to show it!
            # but we can add a log message
            self.warning('the version of gst-python you are using is known to '
                         'cause segfault in the looper component, please '
                         'update to the latest release')
            self.warning('... just so you know, in case it crashes')

        return [checks.checkTicket349()]

    def get_raw_video_element(self):
        return self.pipeline.get_by_name('theoradec')

    def get_pipeline_template(self):
        template = (
            'filesrc location=%(location)s'
            '       ! oggdemux name=demux'
            '    demux. ! queue ! theoradec name=theoradec'
            '       ! identity name=vident single-segment=true sync=true '
            '                  silent=true'
            '       ! @feeder:video@'
            '    demux. ! queue ! vorbisdec name=vorbisdec'
            '       ! volume name=setvolume'
            '       ! level name=volumelevel message=true '
            '       ! identity name=aident single-segment=true sync=true '
            '                  silent=true'
            '       ! @feeder:audio@'
            % dict(location=self.filelocation))

        return template

    def make_message_for_gstreamer_error(self, gerror, debug):
        if gerror.domain == 'gst-resource-error-quark':
            return messages.Error(T_(N_(
                "Could not open file '%s' for reading."), self.filelocation),
                debug='%s\n%s' % (gerror.message, debug),
                mid=gerror.domain, priority=40)
        base = feedcomponent.ParseLaunchComponent
        return base.make_message_for_gstreamer_error(self, gerror, debug)

    def run_discoverer(self):

        def discovered(d, ismedia):
            self.uiState.set('info-location', self.filelocation)
            self.uiState.set('info-duration',
                             max(d.audiolength, d.videolength))
            if d.is_audio:
                self.uiState.set('info-audio',
                                 "%d channel(s) %dHz" % (d.audiochannels,
                                                         d.audiorate))
            if d.is_video:
                self.uiState.set('info-video',
                                 "%d x %d at %d/%d fps" % (d.videowidth,
                                                           d.videoheight,
                                                           d.videorate.num,
                                                           d.videorate.denom))

        from gst.extend import discoverer
        d = discoverer.Discoverer(self.filelocation)
        d.connect('discovered', discovered)
        d.discover()

    def on_segment_done(self):
        self.do_seek(False)
        self.nbiterations += 1
        self.uiState.set('num-iterations', self.nbiterations)

    def on_pads_blocked(self):
        for src, sink in self.pads_to_link:
            src.link(sink)
        self.do_seek(True)
        for src, sink in self.pads_to_link:
            src.set_blocked_async(False, lambda *x: None)
        self.pads_to_link = []
        self.nbiterations = 0
        self.uiState.set('num-iterations', self.nbiterations)

    def configure_pipeline(self, pipeline, properties):
        avproducer.AVProducerBase.configure_pipeline(self, pipeline,
                                                     properties)

        def on_message(bus, message):
            handlers = {(pipeline, gst.MESSAGE_SEGMENT_DONE):
                        self.on_segment_done,
                        (pipeline, gst.MESSAGE_APPLICATION):
                        self.on_pads_blocked}

            if (message.src, message.type) in handlers:
                handlers[(message.src, message.type)]()

        self.oggdemux = pipeline.get_by_name("demux")

        for name in 'aident', 'vident':

            def blocked(x, is_blocked):
                if not x in self.pads_awaiting_block:
                    return
                self.pads_awaiting_block.remove(x)
                if not self.pads_awaiting_block:
                    s = gst.Structure('pads-blocked')
                    m = gst.message_new_application(pipeline, s)
                    # marshal to the main thread
                    pipeline.post_message(m)

            e = pipeline.get_by_name(name)
            src = e.get_pad('src')
            sink = src.get_peer()
            src.unlink(sink)
            src.set_blocked_async(True, blocked)
            self.pads_awaiting_block.append(src)
            self.pads_to_link.append((src, sink))

        self.bus = pipeline.get_bus()
        self.bus.add_signal_watch()

        self.bus.connect('message', on_message)

    def do_seek(self, flushing):
        """
        Restarts the looping.

        Returns True if the seeking was accepted,
        Returns False otherwiser
        """
        self.debug("restarting looping")
        flags = gst.SEEK_FLAG_SEGMENT | (flushing and gst.SEEK_FLAG_FLUSH or 0)
        return self.oggdemux.seek(1.0, gst.FORMAT_TIME, flags,
                                  gst.SEEK_TYPE_SET, 0, gst.SEEK_TYPE_END, 0)

    def do_setup(self):

        def check_time():
            self.log("checking position")
            try:
                pos, _ = self.pipeline.query_position(gst.FORMAT_TIME)
            except:
                self.debug("position query didn't succeed")
            else:
                self.uiState.set('position', pos)
            return True

        if not self.timeoutid:
            self.timeoutid = gobject.timeout_add(500, check_time)

    def do_stop(self):
        if self.bus:
            self.bus.remove_signal_watch()
            self.bus = None

        if self.timeoutid:
            gobject.source_remove(self.timeoutid)
            self.timeoutid = 0

        self.nbiterations = 0

    def _parse_aditional_properties(self, properties):
        # setup the properties
        self.bus = None
        self.filelocation = properties.get('location')
        self.run_discoverer()
