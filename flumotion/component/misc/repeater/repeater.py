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

from flumotion.common import gstreamer, messages, errors
from flumotion.common.i18n import N_, gettexter
from flumotion.component import feedcomponent

T_ = gettexter()
__version__ = "$Rev$"


class Repeater(feedcomponent.ParseLaunchComponent):

    def get_pipeline_string(self, properties):
        dp = ""
        if 'drop-probability' in properties:
            vt = gstreamer.get_plugin_version('coreelements')
            if not vt:
                raise errors.MissingElementError('identity')
            if not vt > (0, 10, 12, 0):
                self.addMessage(
                    messages.Warning(T_(N_(
                        "The 'drop-probability' property is specified, but "
                        "it only works with GStreamer core newer than 0.10.12."
                        " You should update your version of GStreamer."))))
            else:
                drop_probability = properties['drop-probability']
                if drop_probability < 0.0 or drop_probability > 1.0:
                    self.addMessage(
                        messages.Warning(T_(N_(
                            "The 'drop-probability' property can only be "
                            "between 0.0 and 1.0."))))
                else:
                    dp = " drop-probability=%f" % drop_probability

        return 'identity silent=true %s' % dp
