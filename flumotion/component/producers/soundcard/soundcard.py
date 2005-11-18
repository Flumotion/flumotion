# -*- Mode: Python; test-case-name:flumotion.test.test_soundcard -*-
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
import gst.interfaces

from flumotion.component import feedcomponent
from flumotion.component.effects.volume import volume

    
class Soundcard(feedcomponent.ParseLaunchComponent):
    def __init__(self, config):
        element = config['source-element']
        device =  config['device']
        rate = config.get('rate', 22050)
        depth = config.get('depth', 16)
        channels = config.get('channels', 1)
        name = config['name']

        # FIXME: why do we not connect to state_changed_cb so correct
        # soundcard input is used?
        
        # FIXME: we should find a way to figure out what the card supports,
        # so we can add in correct elements on the fly
        # just adding audioscale and audioconvert always makes the soundcard
        # open in 1000 Hz, mono
        if gst.gst_version < (0,9):
            caps = 'audio/x-raw-int,rate=(int)%d,depth=%d,channels=%d,width=%d,signed=(boolean)TRUE,endianness=1234' % (rate, depth, channels, depth)
            pipeline = '%s device=%s ! %s ! level name=volumelevel signal=true' % (element, device, caps)
        else:
            caps = 'audio/x-raw-int,rate=(int)%d,depth=%d,channels=%d' % (rate, depth, channels)
            pipeline = '%s device=%s ! %s ! level name=volumelevel message=true' % (element, device, caps)

        feedcomponent.ParseLaunchComponent.__init__(self, name,
                                                    [],
                                                    ['default'],
                                                    pipeline)

        # add volume effect
        if gst.gst_version < (0,9):
            comp_level = self.get_pipeline().get_by_name('volumelevel')
            vol = volume.Volume('inputVolume', comp_level)
            self.addEffect(vol)

    def state_changed_cb(self, element, old, new, trackLabel):
        if old == gst.STATE_NULL and new == gst.STATE_READY:
            for track in element.list_tracks():
                element.set_record(track, track.label == trackLabel)

    def setVolume(self, value):
        self.debug("Volume set to: %d" % (value))
        self.warning("FIXME: soundcard.setVolume not implemented yet")
