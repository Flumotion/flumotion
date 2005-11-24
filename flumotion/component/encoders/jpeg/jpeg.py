# -*- Mode: Python -*-
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

from flumotion.component import feedcomponent

import gst

class JPEG(feedcomponent.ParseLaunchComponent):
    def __init__(self, config):
        name = config['name']
        eaters = config['source']

        framerate = ''
        if config.has_key('framerate'):
            frac = config['framerate']
            if gst.gst_version < (0,9):
                framerate = '(double)%f' % (float(frac[0])/frac[1])
            else:
                framerate = '(fraction)%d/%d' % (frac[0], frac[1])

            framerate = (' ! videorate ! video/x-raw-yuv,framerate=%s '
                         % framerate)
        pipeline = 'ffmpegcolorspace %s ! jpegenc name=encoder' % framerate

        feedcomponent.ParseLaunchComponent.__init__(self, name,
                                                    eaters,
                                                    ['default'],
                                                    pipeline)
        
        element = self.pipeline.get_by_name('encoder')
        if 'quality' in config:
            element.set_property('quality', config['quality'])
