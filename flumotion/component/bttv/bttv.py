# -*- Mode: Python -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# flumotion/component/bttv/bttv.py: BTTV producer
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
import gst.interfaces

from flumotion.component.base import producer

def state_changed_cb(element, old, new, channel):
    if old == gst.STATE_NULL and new == gst.STATE_READY:
        c = element.find_channel_by_name(channel)
        if c:
            element.set_channel(c)
    
def createComponent(config):
    device = config['device']
    device_width = config['device-width']
    device_height = config['device-height']
    device_channel = config['channel']

    width = config.get('width', 320)
    height = config.get('height', 240)
    framerate = config.get('framerate', 25.0)
    
    pipeline = ('v4lsrc name=src device=%s copy-mode=true ! '
                'video/x-raw-yuv,width=%d,height=%d ! videoscale ! '
                'video/x-raw-yuv,width=%d,height=%d ! videorate ! '
                'video/x-raw-yuv,framerate=%f') % (device,
                                                   device_width,
                                                   device_height,
                                                   width, height,
                                                   framerate)
    config['pipeline'] = pipeline

    component = producer.createComponent(config)
    pipeline = component.get_pipeline() 
    element = pipeline.get_by_name('src')
    element.connect('state-change', state_changed_cb, device_channel)
    
    return component
