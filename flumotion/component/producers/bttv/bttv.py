# -*- Mode: Python -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# flumotion/component/producers/bttv/bttv.py: BTTV producer
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
import gst.interfaces

from flumotion.component.base import producer
from flumotion.component import feedcomponent
from flumotion.common import log

# FIXME: rename to TVCard
# FIXME: what does __all__ *do* ?
__all__ = ['BTTV']

class BTTVMedium(feedcomponent.FeedComponentMedium):
    def __init__(self, comp):
        feedcomponent.FeedComponentMedium.__init__(self, comp)

        # connect to value_changed for colorbalance channels
        # FIXME: doesn't get called when we change it
        pipeline = comp.get_pipeline()
        element = pipeline.get_by_name('source')
        element.connect('value-changed', self.cb_colorbalance_changed)

    def remote_setColorBalanceProperty(self, which, value):
        channel = self.comp.setColorBalanceProperty(which, value)

        # FIXME: call callback coz it doesnt get called when we change it
        if channel:
            pipeline = self.comp.get_pipeline()
            element = pipeline.get_by_name('source')
            self.cb_colorbalance_changed(element, channel, value)

    def remote_getColorBalanceProperties(self):
        return self.comp.getColorBalanceProperties()

    def cb_colorbalance_changed(self, element, channel, value):
        self.debug('ColorBalance property: %s changed to value: %d' % (
            channel.label, value))
        self.callRemote('propertyChanged', self.comp.get_name(), channel.label,
            value)
        
class BTTV(feedcomponent.ParseLaunchComponent):
    component_medium_class = BTTVMedium
    def __init__(self, name, pipeline):
        feedcomponent.ParseLaunchComponent.__init__(self,name,
                                                    [],
                                                    ['default'],
                                                    pipeline)
                                       
    def setColorBalanceProperty(self, which, value):
        """
        Set a color balance property.

        @param which: which property to change
        @param value: what value to set it to
        """
        pipeline = self.get_pipeline() 
        element = pipeline.get_by_name('source')

        if self.cb_channels:
            for i in self.cb_channels:
                log.debug('colorbalance %s: %d <= %d <= %d' % (
                    i.label, i.min_value, element.get_value(i), i.max_value))
                if i.label == which and value >= i.min_value
                                   and value <= i.max_value:
                    element.set_value(i, value)
                    return i

    def getColorBalanceProperties(self):
        """
        Returns: a list of (label, min, max, value) tuples.
        """
        pipeline = self.get_pipeline() 
        element = pipeline.get_by_name('source')

        retval = []
        if not self.cb_channels:
            return retval
        for i in self.cb_channels:
            log.debug('colorbalance %s: %d <= %d <= %d' % (
                i.label, i.min_value, element.get_value(i), i.max_value))
            retval.append([i.label, i.min_value, i.max_value,
                element.get_value(i)])

        return retval

    # called to set initial properties based on state change
    def state_changed_cb(self, element, old, new, channel, norm,
                         hue, saturation, brightness, contrast):
        if not (old == gst.STATE_NULL and new == gst.STATE_READY):
            return
    
        if channel:
            c = element.find_channel_by_name(channel)
            if c:
                element.set_channel(c)
        if norm:
            c = element.find_norm_by_name(norm)
            if c:
                element.set_norm(c)
        
        self.cb_channels = element.list_colorbalance_channels()

        if hue:
            self.change_colorbalance('Hue', hue)
        if saturation:
            self.change_colorbalance('Saturation', saturation)
        if brightness:
            self.change_colorbalance('Brightness', brightness)
        if contrast:
            self.change_colorbalance('Contrast', contrast)
        
     
def createComponent(config):
    device = config['device']
    width = config.get('width', 320)
    height = config.get('height', 240)
    channel = config['channel']
    norm = config['signal']
    hue = config.get('hue', None)
    saturation = config.get('saturation', None)
    brightness = config.get('brightness', None)
    contrast = config.get('contrast', None)

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
    pipeline = component.get_pipeline() 
    element = pipeline.get_by_name('source')
    element.connect('state-change', component.state_changed_cb,
                    channel, norm, hue, saturation, brightness, contrast)
    
    return component
