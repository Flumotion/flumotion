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

from flumotion.common.i18n import gettexter
from flumotion.component import feedcomponent as fc

__version__ = "$Rev$"
T_ = gettexter()


class DecoderComponent(fc.ReconfigurableComponent):

    disconnectedPads = True
    keepStreamheaderForLater = True

    def configure_pipeline(self, pipeline, properties):
        # Handle decoder dynamic pads
        eater = self.eaters.values()[0]
        depay = self.get_element(eater.depayName)
        depay.get_pad("src").add_event_probe(self._depay_reset_event, eater)

        decoder = self.pipeline.get_by_name("decoder")
        decoder.connect('new-decoded-pad', self._new_decoded_pad_cb)

    def get_output_elements(self):
        return [self.get_element(i.name + '-output')
                for i in self._feeders_info.values()]

    def _depay_reset_event(self, pad, event, eater):
        if event.type != gst.EVENT_CUSTOM_DOWNSTREAM:
            return True
        if event.get_structure().get_name() != 'flumotion-reset':
            return True
        self.info("Received flumotion-reset, not droping buffers anymore")

        self.dropStreamHeaders = False
        if self.disconnectedPads:
            return False
        return True

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
            return

        self.info("No feeder found for decoded pad %s with caps %s",
                   pad, new_caps.to_string())
