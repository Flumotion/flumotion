# -*- Mode: Python -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# flumotion/component/producers/soundcard/soundcard.py: soundcard producer
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

from flumotion.component import feedcomponent
    
class Firewire(feedcomponent.ParseLaunchComponent):
    def __init__(self, name, pipeline):
        feedcomponent.ParseLaunchComponent.__init__(self, name,
                                                    [],
                                                    ['video', 'audio'],
                                                    pipeline)
                                       
def createComponent(config):
    p = ''
    
    # read from firewire, decode video, drop every 2 frames
    p += 'dv1394src ! dvdec name=dec drop-factor=2 ! video/x-raw-yuv,format=(fourcc)YUY2 ! '
    
    # normalize rate, scale down to get rid of interlace
    p += 'videorate ! videoscale ! video/x-raw-yuv,width=384,height=288 ! '
    p += 'videoscale ! video/x-raw-yuv,width=384,height=288,framerate=12.5,format=(fourcc)YUY2 ! @feeder::video@ '
    
    # audio gets rate corrected
    p += 'dec. ! audio/x-raw-int ! audiorate ! '
    
    # downsample audio to encode it at lower bitrate
    p += 'audioscale ! audio/x-raw-int,rate=24000 ! @feeder::audio@'
            
    component = Firewire(config['name'], p)

    return component
