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

from flumotion.common import gstreamer, messages
from flumotion.common.i18n import N_, gettexter
from flumotion.component import feedcomponent

__version__ = "$Rev$"
T_ = gettexter()


class Multipart(feedcomponent.MuxerComponent):

    def do_check(self):
        if gstreamer.get_plugin_version('multipart') <= (0, 10, 16, 0):
            m = messages.Warning(
                T_(N_("Versions up to and including %s of the '%s' "
                      "GStreamer plug-in are not suitable for streaming.\n"),
                   '0.10.16', 'multipart'))
            m.add(T_(N_("The stream served by the streamer component "
                        "will probably be unplayable.\n")))
            m.add(T_(N_("The issue will be addressed in version %s of '%s'."),
                     '0.10.17', 'gst-plugins-good'))
            self.addMessage(m)

    def get_muxer_string(self, properties):
        return 'multipartmux name=muxer'
