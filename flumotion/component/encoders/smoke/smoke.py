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

class Smoke(feedcomponent.ParseLaunchComponent):
    def __init__(self, name, eaters, pipeline):
        feedcomponent.ParseLaunchComponent.__init__(self, name,
                                                    eaters,
                                                    ['default'],
                                                    pipeline)

def createComponent(config):
    component = Smoke(config['name'], [config['source']],
                      "ffmpegcolorspace ! smokeenc name=encoder")
    
    element = component.pipeline.get_by_name('encoder')
    if config.has_key('qmin'):
        element.set_property('qmin', config['qmin'])
    if config.has_key('qmax'):
        element.set_property('qmax', config['qmax'])
    if config.has_key('threshold'):
        element.set_property('threshold', config['threshold'])
    if config.has_key('keyframe'):
        element.set_property('keyframe', config['keyframe'])

    return component
