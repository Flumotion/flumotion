# -*- Mode: Python -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# flumotion/component/producers/bttv/bttv.py: BTTV producer
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
import gst.interfaces

from flumotion.common import log

from flumotion.component.base import producer
from flumotion.component import feedcomponent
from flumotion.component.effects.colorbalance import colorbalance

# FIXME: rename to TVCard
# FIXME: what does __all__ *do* ?
__all__ = ['BTTV']

class BTTV(feedcomponent.ParseLaunchComponent):

    def __init__(self, name, pipeline):
        feedcomponent.ParseLaunchComponent.__init__(self,name,
                                                    [],
                                                    ['default'],
                                                    pipeline)

    # called to set initial channel and norm from NULL->READY
    def state_changed_cb(self, element, old, new, channel, norm):
        if not (old == gst.STATE_NULL and new == gst.STATE_READY):
            return

        self.debug("bttv NULL->READY, setting channel %s and norm %s" % (
            channel, norm))
        if channel:
            c = element.find_channel_by_name(channel)
            if c:
                self.debug("set channel to %s" % channel)
                element.set_channel(c)
        if norm:
            c = element.find_norm_by_name(norm)
            if c:
                self.debug("set norm to %s" % norm)
                element.set_norm(c)

                                       
def createComponent(config):
    device = config['device']
    width = config.get('width', 320)
    height = config.get('height', 240)
    channel = config['channel']
    norm = config['signal']

    # This needs to be done properly
    device_width = width
    device_height = height
    #device_width = config['device-width']
    #device_height = config['device-height']

    framerate = config.get('framerate', 25.0)
    
    pipeline = ('v4lsrc name=source device=%s copy-mode=true ! '
                'video/x-raw-yuv,width=%d,height=%d ! videoscale ! '
                'video/x-raw-yuv,width=%d,height=%d ! videorate ! '
                'video/x-raw-yuv,framerate=%f') % (device,
                                                   device_width,
                                                   device_height,
                                                   width, height,
                                                   framerate)
    config['pipeline'] = pipeline

    component = BTTV(config['name'], pipeline)

    # create and add colorbalance effect
    source = component.get_pipeline().get_by_name('source')
    hue = config.get('hue', None)
    saturation = config.get('saturation', None)
    brightness = config.get('brightness', None)
    contrast = config.get('contrast', None)
    cb = colorbalance.Colorbalance('outputColorbalance', source,
        hue, saturation, brightness, contrast)
    component.addEffect(cb)

    # register state change notify to set channel and norm
    element = component.get_pipeline().get_by_name('source')
    element.connect('state-change', component.state_changed_cb, channel, norm)

    return component
