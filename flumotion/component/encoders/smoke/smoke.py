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

from flumotion.component import feedcomponent
from flumotion.common import messages, gstreamer
from flumotion.common.i18n import N_, gettexter

__version__ = "$Rev$"
T_ = gettexter()


class Smoke(feedcomponent.EncoderComponent):

    def get_pipeline_string(self, properties):
        return 'ffmpegcolorspace ! smokeenc name=encoder'

    def configure_pipeline(self, pipeline, properties):
        element = pipeline.get_by_name('encoder')

        for p in ('qmin', 'qmax', 'threshold', 'keyframe'):
            if p in properties:
                element.set_property(p, properties[p])

        jpegVersion = gstreamer.get_plugin_version('jpeg')
        if jpegVersion < (0, 10, 11, 1):
            m = messages.Warning(
                T_(N_("The 'smoke' encoder has a bug in versions previous "
                      "to 0.10.11. It will not work unless it is updated.")),
                mid="smokeenc-bug")
            self.addMessage(m)
