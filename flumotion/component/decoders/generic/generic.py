# -*- Mode: Python -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# Flumotion - a streaming media server
# Copyright (C) 2004,2005,2006,2007 Fluendo, S.L. (www.fluendo.com).
# All rights reserved.

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

from flumotion.component import decodercomponent as dc
from flumotion.common import messages
from flumotion.common.i18n import N_, gettexter

T_ = gettexter()

__version__ = "$Rev: 7162 $"

BASIC_AUDIO_CAPS = "audio/x-raw-int;audio/x-raw-float"
BASIC_VIDEO_CAPS = "video/x-raw-yuv;video/x-raw-rgb"

# FIXME: The GstAutoplugSelectResult enum has no bindings in gst-python.
# Replace this when the enum is exposed in the bindings.

GST_AUTOPLUG_SELECT_TRY = 0
GST_AUTOPLUG_SELECT_SKIP = 2


class FeederInfo(object):

    def __init__(self, name, caps, linked=False):
        self.name = name
        self.caps = caps


class SyncKeeper(gst.Element):
    __gstdetails__ = ('SyncKeeper', 'Generic',
                      'Retimestamp the output to be contiguous and maintain '
                      'the sync', 'Xavier Queralt')
    _audiosink = gst.PadTemplate("audio-in",
                                 gst.PAD_SINK,
                                 gst.PAD_ALWAYS,
                                 gst.caps_from_string(BASIC_AUDIO_CAPS))
    _videosink = gst.PadTemplate("video-in",
                                 gst.PAD_SINK,
                                 gst.PAD_ALWAYS,
                                 gst.caps_from_string(BASIC_VIDEO_CAPS))
    _audiosrc = gst.PadTemplate("audio-out",
                                gst.PAD_SRC,
                                gst.PAD_ALWAYS,
                                gst.caps_from_string(BASIC_AUDIO_CAPS))
    _videosrc = gst.PadTemplate("video-out",
                                gst.PAD_SRC,
                                gst.PAD_ALWAYS,
                                gst.caps_from_string(BASIC_VIDEO_CAPS))

    nextVideoTs = 0
    nextAudioTs = 0
    videoReceived = False
    audioReceived = False
    audioDiscontBuffer = None
    videoDiscontBuffer = None

    sendVideoNewSegment = True
    sendAudioNewSegment = True
    videoPadding = 0
    audioPadding = 0
    resetReceived = False

    def __init__(self):
        gst.Element.__init__(self)

        self.audiosink = gst.Pad(self._audiosink, "audio-in")
        self.audiosink.set_chain_function(self.chainfunc)
        self.audiosink.set_event_function(self.eventfunc)
        self.add_pad(self.audiosink)
        self.videosink = gst.Pad(self._videosink, "video-in")
        self.videosink.set_chain_function(self.chainfunc)
        self.videosink.set_event_function(self.eventfunc)
        self.add_pad(self.videosink)

        self.audiosrc = gst.Pad(self._audiosrc, "audio-out")
        self.add_pad(self.audiosrc)
        self.videosrc = gst.Pad(self._videosrc, "video-out")
        self.add_pad(self.videosrc)

    def push_video_buffer(self, buffer):
        buffer.timestamp += self.videoPadding
        self.nextVideoTs = buffer.timestamp + buffer.duration
        if self.sendVideoNewSegment:
            self.videosrc.push_event(
                gst.event_new_new_segment(True, 1.0, gst.FORMAT_TIME,
                                          buffer.timestamp, -1, 0))
            self.sendVideoNewSegment = False

        self.log(
          "Output video timestamp: %s, %s" % (gst.TIME_ARGS(buffer.timestamp),
                                              gst.TIME_ARGS(buffer.duration)))
        self.videosrc.push(buffer)

    def push_audio_buffer(self, buffer):
        buffer.timestamp += self.audioPadding
        self.nextAudioTs = buffer.timestamp + buffer.duration
        if self.sendAudioNewSegment:
            self.audiosrc.push_event(
                gst.event_new_new_segment(True, 1.0, gst.FORMAT_TIME,
                                          buffer.timestamp, -1, 0))
            self.sendAudioNewSegment = False

        self.log(
          "Output audio timestamp: %s, %s" % (gst.TIME_ARGS(buffer.timestamp)
                                              gst.TIME_ARGS(buffer.duration)))
        self.audiosrc.push(buffer)

    def fixAVPadding(self, videoBuffer=None, audioBuffer=None):
        if not self.resetReceived:
            return False
        if not videoBuffer or not audioBuffer:
            return False
        diff = audioBuffer.timestamp - videoBuffer.timestamp
        newStart = max(self.nextVideoTs, self.nextAudioTs)

        if diff > 0:
            self.videoPadding = newStart - videoBuffer.timestamp
            self.audioPadding = newStart + diff - audioBuffer.timestamp
        else:
            self.videoPadding = newStart + diff - videoBuffer.timestamp
            self.audioPadding = newStart - audioBuffer.timestamp

        self.resetReceived = False

        return True

    def chainfunc(self, pad, buffer):
        if pad.get_name() == 'audio-in':
            self.log(
           "Input audio timestamp: %s, %s" % (gst.TIME_ARGS(buffer.timestamp),
                                              gst.TIME_ARGS(buffer.duration)))
            if self.fixAVPadding(self.videoDiscontBuffer, buffer):
                self.push_video_buffer(self.videoDiscontBuffer)
                self.videoDiscontBuffer = None

            # Check contiguous buffer
            self.audioReceived = True
            if self.videoReceived:
                self.push_audio_buffer(buffer)
            elif self.resetReceived:
                self.audioDiscontBuffer = buffer

            return gst.FLOW_OK
        elif pad.get_name() == 'video-in':
            self.log(
           "Input video timestamp: %s, %s" % (gst.TIME_ARGS(buffer.timestamp),
                                              gst.TIME_ARGS(buffer.duration)))

            if self.fixAVPadding(buffer, self.audioDiscontBuffer):
                self.push_audio_buffer(self.audioDiscontBuffer)
                self.audioDiscontBuffer = None

            self.videoReceived = True
            if self.audioReceived:
                self.push_video_buffer(buffer)
            elif self.resetReceived:
                self.videoDiscontBuffer = buffer

            return gst.FLOW_OK
        else:
            return gst.FLOW_ERROR

    def eventfunc(self, pad, event):
        self.debug("Received event %r from %s" % (event, event.src))
        if event.type == gst.EVENT_NEWSEGMENT:
            return False
        if event.type != gst.EVENT_CUSTOM_DOWNSTREAM:
            return True
        if event.get_structure().get_name() != 'flumotion-reset':
            return True
        self.resetReceived = True
        self.videoReceived = False
        self.audioReceived = False
        self.sendVideoNewSegment = True
        self.sendAudioNewSegment = True

        self.audiosrc.push_event(event)
        self.videosrc.push_event(event)
        return True

gobject.type_register(SyncKeeper)
gst.element_register(SyncKeeper, "synckeeper", gst.RANK_MARGINAL)


class GenericDecoder(dc.DecoderComponent):
    """
    Generic decoder component using decodebin2.

    It listen to the custom gstreamer event flumotion-reset,
    and reset the decoding pipeline by removing the old one
    and creating a new one.

    Sub-classes must override _get_feeders_info() and return
    a list of FeederInfo instances that describe the decoder
    output.

    When reset, if the new decoded pads do not match the
    previously negotiated caps, feeder will not be connected,
    and the decoder will go sad.
    """

    logCategory = "gen-decoder"


    ### Public Methods ###

    def init(self):
        self._feeders_info = None # {FEEDER_NAME: FeederInfo}

    def get_pipeline_string(self, properties):
        # Retrieve feeder info and build a dict out of it
        finfo = self._get_feeders_info()
        assert finfo, "No feeder info specified"
        self._feeders_info = dict([(i.name, i) for i in finfo])

        base_pipeline = self._get_base_pipeline_string()

        pipeline_parts = ["%s synckeeper name=sync" % base_pipeline]

        feeder_tmpl = ("identity name=%(ename)s silent=true ! %(caps)s ! "
                       "sync.%(pad)s-in sync.%(pad)s-out ! @feeder:%(pad)s@")

        for i in self._feeders_info.values():
            ename = self._get_output_element_name(i.name)
            pipeline_parts.append(
                feeder_tmpl % dict(ename=ename, caps=i.caps, pad=i.name))

        pipeline_str = " ".join(pipeline_parts)
        self.log("Decoder pipeline: %s", pipeline_str)

        self._blacklist = properties.get('blacklist', [])

        return pipeline_str

    def configure_pipeline(self, pipeline, properties):
        dc.DecoderComponent.configure_pipeline(self, pipeline,
                                               properties)

        decoder = self.pipeline.get_by_name("decoder")
        decoder.connect('autoplug-select', self._autoplug_select_cb)

    ### Protected Methods ##

    def _get_base_pipeline_string(self):
        return 'decodebin2 name=decoder'

    def _get_feeders_info(self):
        """
        Must be overridden to returns a tuple of FeederInfo.
        """
        return None

    ### Private Methods ###

    def _get_output_element_name(self, feed_name):
        return "%s-output" % feed_name

    ### Callbacks ###

    def _autoplug_select_cb(self, decoder, pad, caps, factory):
        if factory.get_name() in self._blacklist:
            self.log("Skipping element %s because it's in the blacklist",
                     factory.get_name())
            return GST_AUTOPLUG_SELECT_SKIP
        return GST_AUTOPLUG_SELECT_TRY


class SingleGenericDecoder(GenericDecoder):

    logCategory = "sgen-decoder"

    _caps_lookup = {'audio': BASIC_AUDIO_CAPS,
                    'video': BASIC_VIDEO_CAPS}

    def init(self):
        self._media_type = None

    def check_properties(self, properties, addMessage):
        media_type = properties.get("media-type")
        if media_type not in ["audio", "video"]:
            msg = 'Property media-type can only be "audio" or "video"'
            m = messages.Error(T_(N_(msg)), mid="error-decoder-media-type")
            addMessage(m)
        else:
            self._media_type = media_type

    def _get_feeders_info(self):
        caps = self._caps_lookup[self._media_type]
        return FeederInfo('default', caps),


class AVGenericDecoder(GenericDecoder):

    logCategory = "avgen-decoder"

    def _get_feeders_info(self):
        return (FeederInfo('audio', BASIC_AUDIO_CAPS),
                FeederInfo('video', BASIC_VIDEO_CAPS))
