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

from flumotion.common import log

from flumotion.component import feedcomponent

# this is a producer component for ivtv
class Ivtv(feedcomponent.ParseLaunchComponent):
    def get_pipeline_string(self, properties):
        width = properties.get('width', 0)
        height = properties.get('height', 0)
        device = properties.get('device', '/dev/video0')
        if width > 0 and height > 0:
            scaling_template = (" videoscale method=1 ! "
                "video/x-raw-yuv,width=%d,height=%d " % (width, height))
        else:
            scaling_template = ""
        return ("filesrc name=src location=%s ! decodebin name=d ! queue !  "
                " ffdeinterlace ! %s ! ffmpegcolorspace ! video/x-raw-yuv "
                " ! @feeder::video@ d. ! queue ! audioconvert ! audio/x-raw-int "
                " ! @feeder::audio@"
                % (device, scaling_template))
