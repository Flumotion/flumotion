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
# register gdpsink
import flumotion.component.common.fgdp.fgdp

__version__ = "$Rev$"


class GDPConsumer(feedcomponent.ParseLaunchComponent):
    logCategory = 'gdp-consumer'

    def get_pipeline_string(self, properties):
        return "fgdpsink name=sink"

    def configure_pipeline(self, pipeline, properties):
        sink = self.get_element('sink')
        sink.set_property('mode', properties.get('mode', 'push'))
        sink.set_property('host', properties.get('host', 'localhost'))
        sink.set_property('port', properties.get('port', 15000))
        sink.set_property('username', properties.get('username', 'user'))
        sink.set_property('password', properties.get('password', 'test'))
        sink.set_property('version', properties.get('version', '0.1'))
        sink.set_property('max-reconnection-delay',
                properties.get('max-reconnection-delay', 5))
