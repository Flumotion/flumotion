# -*- Mode: Python -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# flumotion/component/producers/videotest/videotest.py: videotest producer
#
# Flumotion - a streaming media server
# Copyright (C) 2004 Fluendo (www.fluendo.com)

# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
# See "LICENSE.GPL" in the source distribution for more information.

# This program is also licensed under the Flumotion license.
# See "LICENSE.Flumotion" in the source distribution for more information.

import gst

from flumotion.component import feedcomponent

class VideoTest(feedcomponent.ParseLaunchComponent):
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
    
    # Filtered caps
    struct = gst.structure_from_string('%s,format=(fourcc)I420' % format)
    setProp(struct, config, 'width')
    setProp(struct, config, 'height')
    setProp(struct, config, 'framerate')
    caps = gst.Caps(struct)
    
    component = VideoTest(config['name'], 'videotestsrc name=source ! %s' % caps)

    # Set properties
    source = component.get_element('source')
    if config.has_key('pattern'):
        source.set_property('pattern', config['pattern'])
                            
    return component

