# -*- Mode: Python -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# Flumotion - a streaming media server
# Copyright (C) 2004,2005 Fluendo, S.L. (www.fluendo.com). All rights reserved.

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

class Theora(feedcomponent.ParseLaunchComponent):
    def __init__(self, name, eaters, pipeline):
        feedcomponent.ParseLaunchComponent.__init__(self, name,
                                                    eaters,
                                                    ['default'],
                                                    pipeline)

def createComponent(config):
    component = Theora(config['name'], config['source'],
                       "ffmpegcolorspace ! theoraenc name=encoder")
    
    element = component.pipeline.get_by_name('encoder')
    if config.has_key('bitrate'):
        element.set_property('bitrate', config['bitrate'])
    if config.has_key('quality'):
        element.set_property('quality', config['quality'])
    if config.has_key('keyframe-threshold'):
        element.set_property('keyframe-threshold', 
            config['keyframe-threshold'])
    if config.has_key('keyframe-mindistance'):
        element.set_property('keyframe-mindistance',
            config['keyframe-mindistance'])
    if config.has_key('keyframe-maxdistance'):
        element.set_property('keyframe-freq',
            config['keyframe-maxdistance'])
        element.set_property('keyframe-force',
            config['keyframe-maxdistance'])
    if config.has_key('quick-compress'):
        element.set_property('quick',
            config['quick-compress'])
    if config.has_key('noise-sensitivity'):
        element.set_property('noise-sensitivity',
            config['noise-sensitivity'])
        
    return component
