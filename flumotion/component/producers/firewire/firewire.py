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

# Headers in this file shall remain intact.

from flumotion.component import feedcomponent
    
class Firewire(feedcomponent.ParseLaunchComponent):
    def __init__(self, name, pipeline):
        feedcomponent.ParseLaunchComponent.__init__(self, name,
                                                    [],
                                                    ['video', 'audio'],
                                                    pipeline)
                                       
def createComponent(config):
    width = config.get('width', 384)
    height = config.get('height', 288)
    framerate = config.get('framerate', 12.5)

    if 12.5 < framerate <= 25:
        drop_factor = 1
    elif 6.3 < framerate <= 12.5:
        drop_factor = 2
    elif 3.2 < framerate <= 6.3:
        drop_factor = 4
    else:
        drop_factor = 8

    if height > 288:
        interlaced_height = 576
    else:
        interlaced_height = 288
        
    template = """dv1394src ! dvdec name=dec drop-factor=%(drop_factor)d ! video/x-raw-yuv,format=(fourcc)YUY2 !
    videorate ! videoscale ! video/x-raw-yuv,width=%(width)s,height=%(interlaced_height)s !
    videoscale ! video/x-raw-yuv,width=%(width)s,height=%(height)s,framerate=%(framerate)f,format=(fourcc)YUY2 ! @feeder::video@
    dec. ! audio/x-raw-int ! audiorate !
    audioscale ! audio/x-raw-int,rate=24000 ! @feeder::audio@""" % dict(drop_factor=drop_factor,
                                                                        interlaced_height=interlaced_height,
                                                                        width=width,
                                                                        height=height,
                                                                        framerate=framerate)
    template = template.replace('\n', '')
    
    component = Firewire(config['name'], template)

    return component
