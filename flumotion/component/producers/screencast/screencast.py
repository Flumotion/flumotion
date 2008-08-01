# -*- Mode: Python -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# Flumotion - a streaming media server
# Copyright (C) 2004,2005,2006,2007 Fluendo, S.L. (www.fluendo.com).
# All rights reserved.

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

from flumotion.common import errors, gstreamer, messages
from flumotion.component import feedcomponent
from flumotion.component.effects.volume import volume

__version__ = "$Rev$"


class Screencast(feedcomponent.ParseLaunchComponent):
    def get_pipeline_string(self, properties):
        def getProps():
            ret = []
            for k, default in (('width', 320),
                               ('height', 240),
                               ('x-offset', 0),
                               ('y-offset', 0),
                               ('framerate', (5, 1))):
                ret.append(properties.get(k, default))
            return ret
        width, height, x_offset, y_offset, framerate = getProps()

        src = 'ximagesrc'
        if not gstreamer.element_factory_exists(src):
            raise errors.MissingElementError(src)

        return (
            '%s startx=%d starty=%d endx=%d endy=%d use-damage=false'
            ' ! ffmpegcolorspace'
            ' ! video/x-raw-yuv,framerate=(fraction)%s,format=(fourcc)I420'
            % (src, x_offset, y_offset, width + x_offset, height + y_offset,
               '%d/%d' % framerate))
