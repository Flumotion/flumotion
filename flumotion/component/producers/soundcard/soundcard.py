# -*- Mode: Python -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# flumotion/component/producers/soundcard/soundcard.py: soundcard producer
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

import gst
import gst.interfaces

from flumotion.component import feedcomponent

def state_changed_cb(element, old, new, channel):
    if old == gst.STATE_NULL and new == gst.STATE_READY:
        c = element.find_channel_by_name(channel)
        if c:
            element.set_channel(c)
    
class SoundcardProducer(feedcomponent.ParseLaunchComponent):
    def __init__(self, name, feeders, pipeline):
        feedcomponent.ParseLaunchComponent.__init__(self, name,
                                                    [],
                                                    feeders,
                                                    pipeline)
                                       
def createComponent(config):
    kind = 'alsasrc'
    config['device'] = 'hw:0'
    
    component = SoundcardProducer(config['name'], config['feed'],
                          '%s name=source' % kind)

    element = component.pipeline.get_by_name('source')
    #element.connect('state-change', state_changed_cb, config['input'])
    element.set_property('device', config['device'])
    #element.set_property('channels', config['channels'])
    #element.set_property('samplerate', config['samplerate'])
    #element.set_property('bitrate', config['bitrate'])
    
    return component
