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

from twisted.internet import reactor

from flumotion.component import feedcomponent
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


class GenericDecoder(feedcomponent.DecoderComponent):
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

        pipeline_parts = [self._get_base_pipeline_string()]

        feeder_tmpl = ("identity name=%s single-segment=True "
                       "silent=True ! %s ! @feeder:%s@")

        for i in self._feeders_info.values():
            ename = self._get_output_element_name(i.name)
            pipeline_parts.append(feeder_tmpl % (ename, i.caps, i.name))

        pipeline_str = " ".join(pipeline_parts)
        self.log("Decoder pipeline: %s", pipeline_str)

        self._blacklist = properties.get('blacklist', [])

        return pipeline_str

    def configure_pipeline(self, pipeline, properties):
        feedcomponent.DecoderComponent.configure_pipeline(self, pipeline,
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
