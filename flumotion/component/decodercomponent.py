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

"""
Decoder component, participating in the stream
"""

import gst
import gst.interfaces

from flumotion.common.i18n import N_, gettexter
from flumotion.common import errors, messages, gstreamer
from flumotion.component.effects.audiorate import audiorate
from flumotion.component.effects.videorate import videorate
from flumotion.component.effects.videoscale import videoscale
from flumotion.component import feedcomponent as fc

__version__ = "$Rev$"
T_ = gettexter()


class DecoderComponent(fc.ReconfigurableComponent):

    disconnectedPads = True
    keepStreamheaderForLater = True
    swallowNewSegment = False

    _feeders_info = []

    def configure_pipeline(self, pipeline, properties):
        # Handle decoder dynamic pads
        eater = self.eaters.values()[0]
        depay = self.get_element(eater.depayName)
        depay.get_pad("src").add_event_probe(self._depay_reset_event, eater)

        decoder = self.pipeline.get_by_name("decoder")
        decoder.connect('new-decoded-pad', self._new_decoded_pad_cb)

        self._add_video_effects()
        self._add_audio_effects()

    def get_output_elements(self):
        return [self.get_element(i.name + '-output')
                for i in self._feeders_info.values()]

    def _depay_reset_event(self, pad, event, eater):
        if event.type != gst.EVENT_CUSTOM_DOWNSTREAM:
            return True
        if gstreamer.event_is_flumotion_reset(event):
            return True
        self.info("Received flumotion-reset, not droping buffers anymore")

        self.dropStreamHeaders = False
        if self.disconnectedPads:
            return False
        return True

    def _add_video_effects(self):
        # Add the effects to the component but don't plug them until we have a
        # valid video pad
        props = self.config['properties']
        is_square = props.get('is-square', False)
        add_borders = props.get('add-borders', False)
        width = props.get('width', None)
        height = props.get('height', None)
        fr = props.get('framerate', (25, 2))
        framerate = gst.Fraction(fr[0], fr[1])

        self.vr = videorate.Videorate('videorate', None,
                                      self.pipeline, framerate)
        self.addEffect(self.vr)
        #self.vr.effectBin.set_state(gst.STATE_PLAYING)
        self.debug("Videorate added")

        self.videoscaler = videoscale.Videoscale('videoscale', self,
            None, self.pipeline,
            width, height, is_square, add_borders)
        self.addEffect(self.videoscaler)
        #self.videoscaler.effectBin.set_state(gst.STATE_PLAYING)
        self.debug("Videoscaler  added")

    def _add_audio_effects(self):
        # Add the effects to the component but don't plug them until we have a
        # valid video pad
        props = self.config['properties']
        samplerate = props.get('samplerate', 44100)

        self.ar = audiorate.Audiorate('audiorate', None,
                                      self.pipeline, samplerate)
        self.addEffect(self.ar)

    def _new_decoded_pad_cb(self, decoder, pad, last):
        self.log("Decoder %s got new decoded pad %s", decoder, pad)

        self.dropStreamHeaders = True
        new_caps = pad.get_caps()

        # Select a compatible output element
        for outelem in self.get_output_elements():
            output_pad = outelem.get_pad('sink')
            if output_pad.is_linked():
                continue

            pad_caps = output_pad.get_caps()
            if not new_caps.is_subset(pad_caps):
                continue

            self.log("Linking decoded pad %s with caps %s to feeder %s",
                       pad, new_caps.to_string(), outelem.get_name())
            pad.link(output_pad)
            self.disconnectedPads = False

            # Plug effects
            if 'video' in pad_caps.to_string():
                self._plug_video_effects(pad)
            if 'audio' in pad_caps.to_string():
                self._plug_audio_effects(pad)
            return

        self.info("No feeder found for decoded pad %s with caps %s",
                   pad, new_caps.to_string())

    def _plug_video_effects(self, pad):
        self.vr.sourcePad = pad
        self.vr.plug()
        self.videoscaler.sourcePad = self.vr.effectBin.get_pad("src")
        self.videoscaler.plug()

    def _plug_audio_effects(self, pad):
        self.ar.sourcePad = pad
        self.ar.plug()
