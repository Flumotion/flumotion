# -*- Mode: Python -*-
# vi:si:et:sw=4:sts=4:ts=4

# Flumotion - a streaming media server
# Copyright (C) 2004,2005,2006,2007,2008,2009 Fluendo, S.L.
# Copyright (C) 2010,2011 Flumotion Services, S.A.
# All rights reserved.
#
# This file may be distributed and/or modified under the terms of
# the GNU Lesser General Public License version 2.1 as published by
# the Free Software Foundation.
# This file is distributed without any warranty; without even the implied
# warranty of merchantability or fitness for a particular purpose.
# See "LICENSE.LGPL" in the source distribution for more information.
#
# Headers in this file shall remain intact.


from flumotion.component import feedcomponent

__version__ = "$Rev$"


# this is a producer component for rtsp sources eg axis network cameras


class Rtsp(feedcomponent.ParseLaunchComponent):

    def get_pipeline_string(self, properties):
        width = properties.get('width', 0)
        height = properties.get('height', 0)
        location = properties.get('location')
        framerate = properties.get('framerate', (25, 2))
        has_audio = properties.get('has-audio', True)
        if width > 0 and height > 0:
            scaling_template = (" videoscale method=1 ! "
                "video/x-raw-yuv,width=%d,height=%d !" % (width, height))
        else:
            scaling_template = ""
        if has_audio:
            audio_template = "d. ! queue ! audioconvert ! audio/x-raw-int"
        else:
            audio_template = "fakesrc silent=true ! audio/x-raw-int"
        return ("rtspsrc name=src location=%s ! decodebin name=d ! queue "
                " ! %s ffmpegcolorspace ! video/x-raw-yuv "
                " ! videorate ! video/x-raw-yuv,framerate=%d/%d ! "
                " @feeder:video@ %s ! @feeder:audio@"
                % (location, scaling_template, framerate[0],
                   framerate[1], audio_template))
