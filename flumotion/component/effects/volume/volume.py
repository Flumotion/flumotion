# -*- Mode: Python -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# flumotion/component/effects/volume/volume.py:
# volume effect
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

class Volume(feedcomponent.Effect):
    logCategory = "volume"

    def __init__(self, name, element):
        """
        @param element: the level element
        """
        feedcomponent.Effect.__init__(self, name)
        self._element = element
        # FIXME: set notification to every 1/5th sec, but maybe make
        # configurable ?
        element.set_property('interval', 0.2)
        element.connect('level', self._level_changed_cb)

    def _level_changed_cb(self, element, time, channel,
                          rms, peak, decay):
        # notify ui of level change
        self.component.adminCallRemote("volumeChanged",
            channel, peak, rms, decay)
