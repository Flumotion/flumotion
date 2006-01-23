# -*- Mode: Python -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# Flumotion - a streaming media server
# Copyright (C) 2004,2005,2006 Fluendo, S.L. (www.fluendo.com).
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
from flumotion.component import feedcomponent

class AudioTest(feedcomponent.ParseLaunchComponent):
    def get_pipeline_string(self, properties):
        rate = properties.get('rate', 8000)
        volume = properties.get('volume', 1.0)

        if gst.gst_version < (0,9):
            is_live = 'sync=true'
            source = 'sinesrc'
        else:
            is_live = 'is-live=true'
            source = 'audiotestsrc'

        return ('%s name=source %s ! audio/x-raw-int,rate=%d ! volume volume=%f'
                % (source, is_live, rate, volume))

    def configure_pipeline(self, pipeline, properties):
        element = self.get_element('source')
        if properties.has_key('freq'):
            element.set_property('freq', properties['freq'])
