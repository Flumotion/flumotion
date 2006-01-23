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

class VideoTestMedium(feedcomponent.FeedComponentMedium):
    def __init__(self, comp):
        feedcomponent.FeedComponentMedium.__init__(self, comp)

    def setup(self, config):
        # called after component's setup
        # connect to pattern notify
        source = self.comp.get_element('source')
        source.connect('notify::pattern', self.cb_pattern_notify)

    def cb_pattern_notify(self, object, pspec):
        pattern = object.get_property('pattern')
        self.callRemote('adminCallRemote', 'propertyChanged', 'pattern',
            int(pattern))

class VideoTest(feedcomponent.ParseLaunchComponent):

    component_medium_class = VideoTestMedium
    
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
            if gst.gst_version < (0,9):
                struct['framerate'] = float(framerate[0]) / framerate[1]
            else:
                struct['framerate'] = gst.Fraction(framerate[0], framerate[1])

        # If RGB, set something ffmpegcolorspace can convert.
        if format == 'video/x-raw-rgb':
            struct['red_mask'] = 0xff00
        caps = gst.Caps(struct)
        
        if gst.gst_version < (0,9):
            is_live = 'sync=true'
        else:
            is_live = 'is-live=true'

        return 'videotestsrc %s name=source ! %s' % (is_live, caps)
        
    # Set properties
    def configure_pipeline(self, pipeline, properties):
        source = self.get_element('source')
        if 'pattern' in properties:
            source.set_property('pattern', properties['pattern'])

