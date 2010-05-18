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

from flumotion.common import gstreamer, messages
from flumotion.common.i18n import N_, gettexter
from flumotion.worker.checks import check
from flumotion.component import feedcomponent


T_ = gettexter()


class Dirac(feedcomponent.EncoderComponent):
    checkTimestamp = True
    checkOffset = True

    def do_check(self):
        d = check.do_check(self, check.checkPlugin, 'schro', 'gst-plugins-bad')

        def check_schroenc_bug(result, component):
            if gstreamer.get_plugin_version('schro') == (1, 0, 7, 0):
                m = messages.Warning(
                    T_(N_("Version %s of the '%s' GStreamer plug-in "
                          "contains a bug.\n"), '1.0.7', 'schroenc'))
                m.add(T_(N_("The downstream components might stay hungry.\n")))
                m.add(T_(N_("The bug has been fixed during the transition of "
                            "'%s' to the '%s' plug-ins set. "
                            "Please upgrade '%s' to version %s, "
                            "which contains the fixed plug-in."),
                         'schroenc', 'gst-plugins-bad', 'schroenc', '0.10.14'))
                component.addMessage(m)
                return result
        return d.addCallback(check_schroenc_bug, self)

    def get_pipeline_string(self, properties):
        return "ffmpegcolorspace ! schroenc name=encoder"

    def configure_pipeline(self, pipeline, properties):
        element = pipeline.get_by_name('encoder')

        bitrate = properties.get('bitrate', None)
        if bitrate:
            self.debug('Setting GStreamer property bitrate to %r' % bitrate)
            element.set_property("bitrate", int(bitrate))
