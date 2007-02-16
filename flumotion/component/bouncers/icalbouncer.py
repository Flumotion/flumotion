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

from flumotion.common import keycards, config
from flumotion.component.bouncers import bouncer
from flumotion.common.keycards import KeycardGeneric
from datetime import datetime

__all__ = ['IcalBouncer']

try:
    # icalendar and dateutil modules needed for ical parsing
	from icalendar import Calendar
    from dateutil import rrule
    HAS_ICAL = True
except:
    HAS_ICAL = False

class IcalBouncer(bouncer.Bouncer):

    logCategory = 'icalbouncer'
    keycardClasses = (KeycardGeneric)
    events = []
    
    def do_setup(self):
        if not HAS_ICAL:
            return defer.fail(
                config.ConfigError(
                    "Please install icalendar and dateutil modules"))
        props = self.config['properties']
        self._icsfile = props['file']
        return self.parse_ics()

    def parse_ics(self):
        if self._icsfile:
            try:
                icsStr = open(self._icsfile, "rb").read()
                cal = Calendar.from_string(icsStr)
                for event in cal.walk('vevent'):
                    dtstart = event.decoded('dtstart', '')
                    dtend = event.decoded('dtend', '')
                    if dtstart and dtend:
                        self.log("event parsed with start: %r end: %r", 
                            dtstart, dtend)
                        recur = event.get('rrule', None)
                        tempEvent = {}
                        tempEvent["dtstart"] = dtstart
                        tempEvent["dtend"] = dtend
                        if recur:
                            # startRecur is a recurrence rule for the start of
                            # the event
                            startRecur = rrule.rrulestr(recur.ical(), 
                                dtstart=dtstart)
                            tempEvent["recur"] = startRecur
                        self.events.append(tempEvent)
                    else:
                        self.log("event had either no dtstart or no dtend"
                                 ", so ignoring")
                return defer.succeed(None)
            except IOError, e:
                return defer.fail(config.ConfigError(str(e)))
            except Exception, e:
                return defer.fail(config.ConfigError(str(e)))
        else:
            return defer.fail(config.ConfigError("No ics file configured"))

    def do_authenticate(self, keycard):
        self.debug('authenticating keycard')

        # need to check if inside an event time
        for event in self.events:
            if event["dtstart"] < datetime.now() and \
               event["dtend"] > datetime.now():
                keycard.state = keycards.AUTHENTICATED
                duration = event["dtend"] - datetime.now()
                durationSecs = duration.days * 86400 + duration.seconds
                keycard.duration = durationSecs
                self.addKeycard(keycard)
                self.info("autheticated login")
                return keycard
            elif "recur" in event:
                # check if in a recurrence of this event
                recurRule = event["recur"]
                dtstart = recurRule.before(datetime.now())
                totalDuration = event["dtend"] - event["dtstart"]
                dtend = dtstart + totalDuration
                if dtend > datetime.now():
                    keycard.state = keycards.AUTHENTICATED
                    duration = dtend - datetime.now()
                    durationSecs = duration.days * 86400 + duration.seconds
                    keycard.duration = durationSecs
                    self.addKeycard(keycard)
                    self.info("authenticated login")
                    return keycard
        self.info("failed in authentication, outside hours")
        return None

