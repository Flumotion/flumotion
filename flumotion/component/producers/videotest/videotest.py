# -*- Mode: Python -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# flumotion/component/producers/videotest/videotest.py: videotest producer
#
# Flumotion - a streaming media server
# Copyright (C) 2004 Fluendo, S.L. (www.fluendo.com). All rights reserved.

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

        # connect to pattern notify
        source = self.comp.get_element('source')
        source.connect('notify::pattern', self.cb_pattern_notify)

    def cb_pattern_notify(self, object, pspec):
        pattern = object.get_property('pattern')
        self.callRemote('propertyChanged', self.comp.get_name(), 'pattern',
            int(pattern))

class VideoTest(feedcomponent.ParseLaunchComponent):

    component_medium_class = VideoTestMedium
    
    def __init__(self, name, pipeline):
        feedcomponent.ParseLaunchComponent.__init__(self, name,
                                                    [],
                                                    ['default'],
                                                    pipeline)


def setProp(struct, dict, name):
    if dict.has_key(name):
        struct[name] = dict[name]
        
def createComponent(config):
    format = config.get('format', 'video/x-raw-yuv')

    if format == 'video/x-raw-yuv':
        format = '%s,format=(fourcc)I420' % format
    # Filtered caps
    struct = gst.structure_from_string(format)
    setProp(struct, config, 'width')
    setProp(struct, config, 'height')
    setProp(struct, config, 'framerate')
    # If RGB, set something ffmpegcolorspace can convert.
    if format == 'video/x-raw-rgb':
        struct['red_mask'] = 0xff00
    caps = gst.Caps(struct)
    
    component = VideoTest(config['name'],
                          'videotestsrc name=source ! %s' % caps)

    # Set properties
    source = component.get_element('source')
    if config.has_key('pattern'):
        source.set_property('pattern', config['pattern'])
                            
    return component

