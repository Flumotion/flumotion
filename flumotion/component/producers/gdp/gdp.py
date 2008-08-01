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
from flumotion.common import gstreamer, messages
from flumotion.common.i18n import N_, gettexter

T_ = gettexter()

__version__ = "$Rev$"


class GDPProducer(feedcomponent.ParseLaunchComponent):
    def do_check(self):
        # handle http://bugzilla.gnome.org/show_bug.cgi?id=532364
        version = gstreamer.get_plugin_version('tcp')
        if version >= (0, 10, 18, 0) and version < (0, 10, 19, 2):
            m = messages.Error(T_(N_(
                "Version %s of the '%s' GStreamer plug-in contains a bug.\n"),
                   ".".join([str(x) for x in version]), 'tcp'),
                mid='tcp-check')
            m.add(T_(N_("The GDP producer cannot function with this bug.\n")))
            m.add(T_(N_("Please upgrade '%s' to version %s."),
                'gst-plugins-base', '0.10.20'))
            self.addMessage(m)

    def get_pipeline_string(self, properties):
        host = properties['host']
        port = properties['port']

        return 'tcpclientsrc host=%s port=%d ! gdpdepay' % (host, port)
