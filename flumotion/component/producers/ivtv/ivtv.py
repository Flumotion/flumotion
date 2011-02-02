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
from flumotion.component.effects.deinterlace import deinterlace
from flumotion.component.effects.videorate import videorate
from flumotion.component.effects.videoscale import videoscale

__version__ = "$Rev$"


class Ivtv(feedcomponent.ParseLaunchComponent):

    def check_properties(self, props, addMessage):
        deintMode = props.get('deinterlace-mode', 'auto')
        deintMethod = props.get('deinterlace-method', 'ffmpeg')

        if deintMode not in deinterlace.DEINTERLACE_MODE:
            msg = messages.Error(T_(N_("Configuration error: '%s' " \
                "is not a valid deinterlace mode." % deintMode)))
            addMessage(msg)
            raise errors.ConfigError(msg)

        if deintMethod not in deinterlace.DEINTERLACE_METHOD:
            msg = messages.Error(T_(N_("Configuration error: '%s' " \
                "is not a valid deinterlace method." % deintMethod)))
            self.debug("'%s' is not a valid deinterlace method",
                deintMethod)
            addMessage(msg)
            raise errors.ConfigError(msg)

    def get_pipeline_string(self, properties):
        p = properties
        device = p.get('device', '/dev/video0')
        deinterlacer = p.get('deinterlacer', '')
        self.is_square = p.get('is-square', False)
        self.width = p.get('width', 0)
        self.height = p.get('height', 0)
        if not self.is_square and not self.height:
            self.height = int(576 * self.width/720.) # assuming PAL
        self.add_borders = p.get('add-borders', True)
        self.deintMode = p.get('deinterlace-mode', 'auto')
        self.deintMethod = p.get('deinterlace-method', 'ffmpeg')

        fr = p.get('framerate', None)
        if fr is not None:
            self.framerate = gst.Fraction(fr[0], fr[1])
        else:
            self.framerate = None

        template = ("filesrc name=src location=%s"
                    "   ! decodebin name=dec "
                    "  dec. ! identity silent=true name=video ! @feeder:video@"
                    "  dec. ! audioconvert ! audio/x-raw-int "
                    "   ! @feeder:audio@" % device)

        return template

    def configure_pipeline(self, pipeline, properties):
        video = pipeline.get_by_name('video')
        vr = videorate.Videorate('videorate',
            video.get_pad("src"), pipeline, self.framerate)
        self.addEffect(vr)
        vr.plug()

        deinterlacer = deinterlace.Deinterlace('deinterlace',
            vr.effectBin.get_pad("src"), pipeline,
            self.deintMode, self.deintMethod)
        self.addEffect(deinterlacer)
        deinterlacer.plug()

        videoscaler = videoscale.Videoscale('videoscale', self,
            deinterlacer.effectBin.get_pad("src"), pipeline,
            self.width, self.height, self.is_square, self.add_borders)
        self.addEffect(videoscaler)
        videoscaler.plug()
