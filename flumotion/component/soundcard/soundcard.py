# -*- Mode: Python -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# flumotion/component/soundcard/soundcard.py: soundcard producer
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

from flumotion.component import feedcomponent

def state_changed_cb(element, old, new, channel):
    if old == gst.STATE_NULL and new == gst.STATE_READY:
        c = element.find_channel_by_name(channel)
        if c:
            element.set_channel(c)
    
class Soundcard(feedcomponent.ParseLaunchComponent):
    def __init__(self, name, pipeline):
        feedcomponent.ParseLaunchComponent.__init__(self, name,
                                                    [],
                                                    ['default'],
                                                    pipeline)
                                       
def createComponent(config):
    kind = 'osssrc'
    component = Soundcard(config['name'],
                          '%s name=source' % kind)

    element = component.pipeline.get_by_name('source')
    element.connect('state-change', state_changed_cb, config['input'])
    element.set_property('device', config['device'])
    #element.set_property('channels', config['channels'])
    #element.set_property('samplerate', config['samplerate'])
    #element.set_property('bitrate', config['bitrate'])
    
    return component
