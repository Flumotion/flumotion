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

import string
from twisted.internet import defer

from flumotion.common import gstreamer, messages
from flumotion.common.i18n import N_, gettexter
from flumotion.worker.checks import check

__version__ = "$Rev$"
T_ = gettexter()


def checkOgg():
    """
    Check for a recent enough Ogg muxer.
    """
    result = messages.Result()
    version = gstreamer.get_plugin_version('ogg')
    if version >= (0, 10, 3, 0) and version < (0, 10, 4, 0):
        m = messages.Warning(T_(
            N_("Version %s of the '%s' GStreamer plug-in contains a bug.\n"),
               string.join([str(x) for x in version], '.'), 'ogg'),
            mid='ogg-check')
        m.add(T_(N_("The generated Ogg stream will not be fully compliant, "
            "and possibly not even play correctly.\n")))
        m.add(T_(N_("Please upgrade '%s' to version %s."), 'gst-plugins-base',
            '0.10.4'))
        result.add(m)

    result.succeed(None)
    return defer.succeed(result)
