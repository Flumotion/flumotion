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

from flumotion.worker.checks import check
from flumotion.component import feedcomponent


class Dirac(feedcomponent.ParseLaunchComponent):
    checkTimestamp = True
    checkOffset = True

    def do_check(self):
        return check.do_check(self, check.checkPlugin, 'schro', 'schroedinger')

    def get_pipeline_string(self, properties):
        return "ffmpegcolorspace ! schroenc name=encoder"

    def configure_pipeline(self, pipeline, properties):
        element = pipeline.get_by_name('encoder')

        bitrate = properties.get('bitrate', None)
        if bitrate:
            self.debug('Setting GStreamer property bitrate to %r' % bitrate)
            element.set_property("bitrate", int(bitrate))
