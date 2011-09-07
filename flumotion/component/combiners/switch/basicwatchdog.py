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

from flumotion.component import feedcomponent
from flumotion.common import errors

from flumotion.component.combiners.switch import switch

__version__ = "$Rev$"


# These basic watchdog components switch to backup
# when the master eater(s) have gone hungry


class SingleBasicWatchdog(switch.SingleSwitch):
    logCategory = "comb-single-basic-watchdog"

    def init(self):
        switch.SingleSwitch.init(self)
        # startedFine is set to True when all sink pads to all switch elements
        # have received data
        self.startedFine = False
        self._started = []

    def feedSetInactive(self, feed):
        switch.SingleSwitch.feedSetInactive(self, feed)
        if self.startedFine:
            self.auto_switch()
        else:
            if feed in self._started:
                self._started.remove(feed)

    def feedSetActive(self, feed):
        switch.SingleSwitch.feedSetActive(self, feed)
        if self.startedFine:
            self.auto_switch()
        else:
            self._started.append(feed)
            allStarted = True
            # check if all feeds started
            for lf in self.logicalFeeds:
                if lf not in self._started:
                    allStarted = False
                    break
            if allStarted:
                self.startedFine = True
                self._started = []


class AVBasicWatchdog(switch.AVSwitch):
    logCategory = "comb-av-basic-watchdog"

    def init(self):
        switch.AVSwitch.init(self)
        # startedFine is set to True when all sink pads to all switch elements
        # have received data
        self.startedFine = False
        self._started = []

    def feedSetInactive(self, feed):
        switch.AVSwitch.feedSetInactive(self, feed)
        if self.startedFine:
            self.auto_switch()
        else:
            if feed in self._started:
                self._started.remove(feed)

    def feedSetActive(self, feed):
        switch.AVSwitch.feedSetActive(self, feed)
        if self.startedFine:
            self.auto_switch()
        else:
            self._started.append(feed)
            allStarted = True
            # check if all feeds started
            for lf in self.logicalFeeds:
                if lf not in self._started:
                    allStarted = False
                    break
            if allStarted:
                self.startedFine = True
                self._started = []
