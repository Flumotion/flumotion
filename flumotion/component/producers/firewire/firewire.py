# -*- Mode: Python -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# flumotion/component/producers/soundcard/soundcard.py: soundcard producer
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


from flumotion.common import errors
from flumotion.component import feedcomponent


class Firewire(feedcomponent.ParseLaunchComponent):
    def __init__(self, name, pipeline):
        feedcomponent.ParseLaunchComponent.__init__(self, name,
                                                    [],
                                                    ['video', 'audio'],
                                                    pipeline)
                                       
# See comments in gstdvdec.c for details on the dv format.

def createComponent(config):
    height = config['height']
    width = config['width']
    scaled_width = config['scaled_width']
    is_square = config['is_square']
    framerate = config['framerate']

    width_correction = width - scaled_width

    if 12.5 < framerate <= 25:
        drop_factor = 1
    elif 6.3 < framerate <= 12.5:
        drop_factor = 2
    elif 3.2 < framerate <= 6.3:
        drop_factor = 4
    else:
        drop_factor = 8

    if is_square:
        square_pipe = ',pixel-aspect-ratio=(fraction)1/1'
    else:
        square_pipe = ''

    if width_correction > 0:
        pad_pipe = '! ffmpegcolorspace ! videobox right=-%d ' % (width - scaled_width)
    else:
        pad_pipe = ''

    # Scale down to half size and back again to lose interlacing
    # artifacts.
    if height > 288:
        interlaced_height = 576
    else:
        interlaced_height = 288
        
    template = """dv1394src ! dvdec name=dec drop-factor=%(df)d
                            ! video/x-raw-yuv,format=(fourcc)YUY2
                            ! videorate ! videoscale
                            ! video/x-raw-yuv,width=%(sw)s,height=%(ih)s%(sq)s
                            ! videoscale
                            ! video/x-raw-yuv,width=%(sw)s,height=%(h)s,framerate=%(fr)f,format=(fourcc)YUY2
                            %(pp)s
                            ! @feeder::video@

                            dec. ! audio/x-raw-int ! audiorate ! audioscale
                            ! audio/x-raw-int,rate=24000 ! @feeder::audio@
               """ % dict(df=drop_factor, ih=interlaced_height,
                          sq=square_pipe, pp=pad_pipe, sw=scaled_width,
                          h=height, fr=framerate)
    template = template.replace('\n', '')
    
    component = Firewire(config['name'], template)

    return component
