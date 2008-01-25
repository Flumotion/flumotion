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
from flumotion.common import errors

from flumotion.component.combiners.switch import switch

__version__ = "$Rev$"


# These basic watchdog components switch to backup
# when the master eater(s) have gone hungry
class SingleBasicWatchdog(switch.SingleSwitch):
    logCategory = "comb-single-basic-watchdog"

    def feedSetInactive(self, feed):
        switch.SingleSwitch.feedSetInactive(self, feed)
        self.auto_switch()

    def feedSetActive(self, feed):
        switch.SingleSwitch.feedSetActive(self, feed)
        self.auto_switch()

class AVBasicWatchdog(switch.AVSwitch):
    logCategory = "comb-av-basic-watchdog"

    def feedSetInactive(self, feed):
        switch.AVSwitch.feedSetInactive(self, feed)
        self.auto_switch()

    def feedSetActive(self, feed):
        switch.AVSwitch.feedSetActive(self, feed)
        self.auto_switch()
