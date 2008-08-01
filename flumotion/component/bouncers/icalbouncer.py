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

"""
A bouncer that only lets in during an event scheduled with an ical file.
"""

from twisted.internet import defer

from flumotion.common import keycards, errors
from flumotion.component.bouncers import bouncer
from flumotion.common.keycards import KeycardGeneric
from datetime import datetime
from flumotion.component.base import scheduler

__all__ = ['IcalBouncer']
__version__ = "$Rev$"


try:
    # icalendar and dateutil modules needed for ical parsing
    from icalendar import Calendar
    from dateutil import rrule
    HAS_ICAL = True
except ImportError:
    HAS_ICAL = False


class IcalBouncer(bouncer.Bouncer):

    logCategory = 'icalbouncer'
    keycardClasses = (KeycardGeneric)
    events = []

    def do_setup(self):
        if not HAS_ICAL:
            return defer.fail(
                errors.ConfigError(
                    "Please install icalendar and dateutil modules"))
        props = self.config['properties']
        self._icsfile = props['file']
        self.icalScheduler = scheduler.ICalScheduler(open(
            self._icsfile, 'r'))

        return True

    def do_authenticate(self, keycard):
        self.debug('authenticating keycard')

        # need to check if inside an event time
        # FIXME: think of a strategy for handling overlapping events
        currentEvents = self.icalScheduler.getCurrentEvents()
        if currentEvents:
            event = currentEvents[0]
            keycard.state = keycards.AUTHENTICATED
            now = datetime.now()
            nowInTz = datetime(now.year, now.month, now.day,
                                  now.hour, now.minute, now.second,
                                  tzinfo=scheduler.LOCAL)
            end = event.currentEnd
            duration = end - nowInTz
            durationSecs = duration.days * 86400 + duration.seconds
            keycard.duration = durationSecs
            self.addKeycard(keycard)
            self.info("authenticated login")
            return keycard
        self.info("failed in authentication, outside hours")
        return None

    def do_stop(self):
        self.icalScheduler.stopWatchingIcalFile()
        for event in self.icalScheduler.getCurrentEvents():
            self.icalScheduler.removeEvent(event)
