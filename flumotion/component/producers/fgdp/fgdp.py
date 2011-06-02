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

from flumotion.component import feedcomponent
from flumotion.common import gstreamer
# register gdpsrc
import flumotion.component.common.fgdp.fgdp

__version__ = "$Rev$"


class FGDPProducer(feedcomponent.ParseLaunchComponent):
    logCategory = 'fgdp-producer'

    def get_pipeline_string(self, properties):
        return "fgdpsrc name=src"

    def configure_pipeline(self, pipeline, properties):
        src = self.get_element('src')
        src.set_property('mode', properties.get('mode', 'pull'))
        src.set_property('host', properties.get('host', 'localhost'))
        src.set_property('port', properties.get('port', 15000))
        src.set_property('username', properties.get('username', 'user'))
        src.set_property('password', properties.get('password', 'test'))
        src.set_property('version', properties.get('version', '0.1'))
        src.set_property('max-reconnection-delay',
                properties.get('max-reconnection-delay', 0.5))
        src.connect('connected', self._on_connected)
        src.connect('disconnected', self._on_disconnected)

    def _on_connected(self, element):
        self.info("FGDP producer connected")
        pad = self.get_element('src').get_pad('src')
        pad.push_event(gstreamer.flumotion_reset_event())

    def _on_disconnected(self, element, reason):
        self.info("FGDP producer disconnected: %s", reason)
