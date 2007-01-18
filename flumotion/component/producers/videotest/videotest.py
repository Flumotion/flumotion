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

from flumotion.component import feedcomponent

class VideoTest(feedcomponent.ParseLaunchComponent):

    def init(self):
        self.uiState.addKey('pattern', 0)

    def get_pipeline_string(self, properties):
        format = properties.get('format', 'video/x-raw-yuv')

        if format == 'video/x-raw-yuv':
            format = '%s,format=(fourcc)I420' % format

        # Filtered caps
        struct = gst.structure_from_string(format)
        for k in 'width', 'height':
            if k in properties:
                struct[k] = properties[k]

        if 'framerate' in properties:
            framerate = properties['framerate']
            struct['framerate'] = gst.Fraction(framerate[0], framerate[1])

        # If RGB, set something ffmpegcolorspace can convert.
        if format == 'video/x-raw-rgb':
            struct['red_mask'] = 0xff00
        caps = gst.Caps(struct)
        
        is_live = 'is-live=true'

        return 'videotestsrc %s name=source ! %s' % (is_live, caps)
        
    # Set properties
    def configure_pipeline(self, pipeline, properties):
        def notify_pattern(obj, pspec):
            self.uiState.set('pattern', int(obj.get_property('pattern')))

        source = self.get_element('source')
        source.connect('notify::pattern', notify_pattern)
        if 'pattern' in properties:
            source.set_property('pattern', properties['pattern'])

