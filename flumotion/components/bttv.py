# -*- Mode: Python -*-
# vi:si:et:sw=4:sts=4:ts=4

# Flumotion - a video streaming server
# Copyright (C) 2004 Fluendo
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Street #330, Boston, MA 02111-1307, USA.

import gst
import gst.interfaces

from flumotion.components import producer

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
