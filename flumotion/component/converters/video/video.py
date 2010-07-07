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

from flumotion.common import errors, messages
from flumotion.common.i18n import N_, gettexter
from flumotion.component import feedcomponent
from flumotion.component.effects.videorate import videorate
from flumotion.component.effects.videoscale import videoscale
from flumotion.component.effects.deinterlace import deinterlace

__all__ = ['Converter']
__version__ = "$Rev$"
T_ = gettexter()


class Converter(feedcomponent.ParseLaunchComponent):
    logCategory = 'videoconvert'

    def check_properties(self, props, addMessage):
        props = self.config['properties']
        deintMode = props.get('deinterlace-mode', 'auto')
        deintMethod = props.get('deinterlace-method', 'ffmpeg')
        is_square = props.get('is-square', False)
        width = props.get('width', None)
        height = props.get('height', None)

        if deintMode not in deinterlace.DEINTERLACE_MODE:
            msg = "'%s' is not a valid deinterlace mode." % deintMode
            raise errors.ConfigError(msg)
        if deintMethod not in deinterlace.DEINTERLACE_METHOD:
            msg = "'%s' is not a valid deinterlace method." % deintMethod
            raise errors.ConfigError(msg)

    def get_pipeline_string(self, properties):
        return 'identity name=identity'

    def configure_pipeline(self, pipeline, properties):
        self.deintMode = properties.get('deinterlace-mode', "auto")
        self.deintMethod = properties.get('deinterlace-method', "ffmpeg")
        self.framerate = properties.get('framerate', None)
        self.width = properties.get('width', None)
        self.height = properties.get('height', None)
        self.is_square = properties.get('is-square', False)

        identity = pipeline.get_by_name("identity")
        # Add videorate effect. The videorate is usually decreased, so it's
        # usefull to have this effect always first, because it reduces the
        # number of frames to process.
        vr = videorate.Videorate('videorate',
            identity.get_pad("src"), pipeline, self.framerate)
        self.addEffect(vr)
        vr.plug()
        # Add deinterlace effect. Deinterlacing must always be done
        # before scaling.
        deinterlacer = deinterlace.Deinterlace('deinterlace',
            vr.effectBin.get_pad("src"),
            pipeline, self.deintMode, self.deintMethod)
        self.addEffect(deinterlacer)
        deinterlacer.plug()
        # Add videoscale effect
        videoscaler = videoscale.Videoscale('videoscale', self,
            deinterlacer.effectBin.get_pad("src"), pipeline,
            self.width, self.height, self.is_square)
        self.addEffect(videoscaler)
        videoscaler.plug()
