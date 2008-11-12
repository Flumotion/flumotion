# -*- Mode: Python;  test-case-name: flumotion.test.test_icalbouncer -*-
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

from datetime import datetime

from twisted.internet import defer

from flumotion.common import keycards, messages, errors
from flumotion.common import log, documentation
from flumotion.common import eventcalendar
from flumotion.common.i18n import N_, gettexter
from flumotion.component.base import scheduler
from flumotion.component.bouncers import bouncer
from flumotion.common.keycards import KeycardGeneric

__all__ = ['IcalBouncer']
__version__ = "$Rev$"
T_ = gettexter()


class IcalBouncer(bouncer.Bouncer):

    logCategory = 'icalbouncer'
    keycardClasses = (KeycardGeneric)
    events = []

    def init(self):
        self.iCalScheduler = None

    def check_properties(self, properties, addMessage):

        def missingModule(moduleName):
            m = messages.Error(T_(N_(
                "To use the iCalendar bouncer you need to have "
                "the '%s' module installed.\n"), moduleName),
                               mid='error-python-%s' % moduleName)
            documentation.messageAddPythonInstall(m, moduleName)
            addMessage(m)

        if not eventcalendar.HAS_ICALENDAR:
            missingModule('icalendar')
        if not eventcalendar.HAS_DATEUTIL:
            missingModule('dateutil')

    def do_setup(self):
        props = self.config['properties']
        self._icsfile = props['file']

        try:
            handle = open(self._icsfile, 'r')
        except IOError, e:
            m = messages.Error(T_(N_(
                "Failed to open iCalendar file '%s'. "
                "Check permissions on that file."), self._icsfile),
                               mid='error-icalbouncer-file')
            self.addMessage(m)
            return defer.fail(errors.ComponentSetupHandledError())

        try:
            self.iCalScheduler = scheduler.ICalScheduler(handle)
        except ValueError, e:
            m = messages.Error(T_(N_(
                "Error parsing ical file '%s'."), self._icsfile),
                               debug=log.getExceptionMessage(e),
                               mid="error-icalbouncer-file")
            self.addMessage(m)
            return defer.fail(errors.ComponentSetupHandledError())

        return True

    def do_authenticate(self, keycard):
        self.debug('authenticating keycard')

        # need to check if inside an event time
        # FIXME: think of a strategy for handling overlapping events
        currentEvents = self.icalScheduler.getCurrentEvents()
        if currentEvents:
            event = currentEvents[0]
            now = datetime.now()
            nowInTz = datetime(now.year, now.month, now.day,
                                  now.hour, now.minute, now.second,
                                  tzinfo=scheduler.LOCAL)
            end = event.currentEnd
            duration = end - nowInTz
            durationSecs = duration.days * 86400 + duration.seconds
            keycard.duration = durationSecs
            if self.addKeycard(keycard):
                keycard.state = keycards.AUTHENTICATED
                self.info("authenticated login, duration %d seconds",
                          durationSecs)
                return keycard
        keycard.state = keycards.REFUSED
        self.info("failed in authentication, outside hours")
        return None

    def do_stop(self):
        # we might not have an iCalScheduler, if something went wrong
        # during do_setup or do_check
        if self.iCalScheduler:
            self.iCalScheduler.cleanup()
