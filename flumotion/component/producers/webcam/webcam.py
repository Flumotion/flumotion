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

import gst

from flumotion.common import gstreamer

from flumotion.component import feedcomponent
from flumotion.component.effects.colorbalance import colorbalance

# FIXME: rename to Webcam
class WebCamera(feedcomponent.ParseLaunchComponent):

    def __init__(self, name, pipeline):
        feedcomponent.ParseLaunchComponent.__init__(self, name,
                                                    [],
                                                    ['default'],
                                                    pipeline)

def setProp(struct, dict, name):
    if dict.has_key(name):
        struct[name] = dict[name]
                                                                                
def createComponent(config):
    device = config['device']

    # Filtered caps
    format = config.get('format', 'video/x-raw-yuv')
    struct = gst.structure_from_string('%s,format=(fourcc)I420' % format)
    setProp(struct, config, 'width')
    setProp(struct, config, 'height')
    setProp(struct, config, 'framerate')
    caps = gst.Caps(struct)
   
    # create component
    autoprobe = "autoprobe=false"
    # added in gst-plugins 0.8.6
    if gstreamer.element_factory_has_property('v4lsrc', 'autoprobe-fps'):
        autoprobe += " autoprobe-fps=false"
    
    pipeline = 'v4lsrc name=source %s copy-mode=1 device=%s ! ' \
               'ffmpegcolorspace ! "%s" ! videorate ! "%s"' \
               % (autoprobe, device, caps, caps)
    component = WebCamera(config['name'], pipeline)

    # create and add colorbalance effect
    source = component.get_pipeline().get_by_name('source')
    hue = config.get('hue', None)
    saturation = config.get('saturation', None)
    brightness = config.get('brightness', None)
    contrast = config.get('contrast', None)
    cb = colorbalance.Colorbalance('outputColorbalance', source,
        hue, saturation, brightness, contrast)
    component.addEffect(cb)

    return component
