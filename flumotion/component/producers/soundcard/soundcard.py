# -*- Mode: Python; test-case-name:flumotion.test.test_soundcard -*-
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

# Headers in this file shall remain intact.

import gst
import gst.interfaces

from flumotion.component import feedcomponent

def state_changed_cb(element, old, new, trackLabel):
    if old == gst.STATE_NULL and new == gst.STATE_READY:
        for track in element.list_tracks():
            element.set_record(track, track.label == trackLabel)
    
class SoundcardProducer(feedcomponent.ParseLaunchComponent):
    def __init__(self, name, feeders, pipeline):
        feedcomponent.ParseLaunchComponent.__init__(self, name,
                                                    [],
                                                    feeders,
                                                    pipeline)
                                       
def createComponent(config):
    element = config['source-element']
    device =  config['device']
    rate = config.get('rate', 22050)
    depth = config.get('depth', 16)
    channels = config.get('channels', 1)

    # FIXME: we should find a way to figure out what the card supports,
    # so we can add in correct elements on the fly
    # just adding audioscale and audioconvert always makes the soundcard
    # open in 1000 Hz, mono
    caps = 'audio/x-raw-int,rate=(int)%d,depth=%d,channels=%d,width=%d,signed=(boolean)TRUE,endianness=1234' % (rate, depth, channels, depth)
    pipeline = '%s device=%s ! %s' % (element, device, caps)
    component = SoundcardProducer(config['name'], config['feed'],  pipeline)

    return component
