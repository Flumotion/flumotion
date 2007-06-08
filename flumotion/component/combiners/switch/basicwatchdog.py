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

# These basic watchdog components switch to backup
# when the master eater(s) have gone hungry
# FIXME: if a scheduled event happens so we are meant to be on backup, and then
# both backup and master go away and come back, it will switch to master
class SingleBasicWatchdog(switch.SingleSwitch):
    logCategory = "comb-single-basic-watchdog"

    def eaterSetInactive(self, feedId):
        switch.SingleSwitch.eaterSetInactive(self, feedId)
        eaterName = self.get_eater_name_for_feed_id(feedId)
        if "master" in eaterName and self.isActive("backup"):
            self.switch_to("backup")

    def eaterSetActive(self, feedId):
        switch.SingleSwitch.eaterSetActive(self, feedId)
        eaterName = self.get_eater_name_for_feed_id(feedId)
        if "master" in eaterName:
            self.debug("Switching to master")
            self.switch_to("master")

class AVBasicWatchdog(switch.AVSwitch):
    logCategory = "comb-av-basic-watchdog"

    def eaterSetInactive(self, feedId):
        switch.AVSwitch.eaterSetInactive(self, feedId)
        eaterName = self.get_eater_name_for_feed_id(feedId)
        oppositeEater = "backup"
        if self._idealEater == "backup":
            oppositeEater = "master"
        if self._idealEater in eaterName and self.is_active(oppositeEater) and \
           self.uiState.get("active-eater") == self._idealEater and \
           self._started:
            self.debug("Switching to %s, active eater is %s", oppositeEater,
                self.uiState.get("active-eater"))
            self.switch_to(oppositeEater)

    def eaterSetActive(self, feedId):
        switch.AVSwitch.eaterSetActive(self, feedId)
        eaterName = self.get_eater_name_for_feed_id(feedId)
        oppositeEater = "backup"
        if self._idealEater == "backup":
            oppositeEater = "master"
        if self._idealEater in eaterName and self.is_active(self._idealEater) \
           and self.uiState.get("active-eater") == oppositeEater and \
           self._started:
            self.debug("Switching to %s, active eater is %s", self._idealEater,
                self.uiState.get("active-eater"))
            self.switch_to(self._idealEater)
