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

from datetime import datetime, timedelta

from twisted.internet import defer

from flumotion.common import keycards, messages, errors
from flumotion.common import log, documentation
from flumotion.common import eventcalendar
from flumotion.common.i18n import N_, gettexter
from flumotion.component.base import scheduler
from flumotion.component.bouncers.algorithms import base

__all__ = ['IcalBouncerAlgorithm']
__version__ = "$Rev$"
T_ = gettexter()


class IcalBouncerAlgorithm(base.BouncerAlgorithm):

    logCategory = 'icalbouncer'
    events = []
    maxKeyCardDuration = timedelta(days=1)

    def get_namespace(self):
        return 'icalbouncer'

    def start(self, component):
        self.props = self.args['properties']
        self.iCalScheduler = None
        self.subscriptionToken = None
        self.check_properties(component)
        self.setup(component)

    def check_properties(self, component):

        def missingModule(moduleName):
            m = messages.Error(T_(N_(
                "To use the iCalendar bouncer you need to have "
                "the '%s' module installed.\n"), moduleName),
                               mid='error-python-%s' % moduleName)
            documentation.messageAddPythonInstall(m, moduleName)
            component.addMessage(m)

        if not eventcalendar.HAS_ICALENDAR:
            missingModule('icalendar')
        if not eventcalendar.HAS_DATEUTIL:
            missingModule('dateutil')

    def setup(self, component):
        self._icsfile = self.props['file']

        try:
            handle = open(self._icsfile, 'r')
        except IOError, e:
            m = messages.Error(T_(N_(
                "Failed to open iCalendar file '%s'. "
                "Check permissions on that file."), self._icsfile),
                               mid='error-icalbouncer-file')
            component.addMessage(m)
            raise errors.ComponentSetupHandledError()

        try:
            self.iCalScheduler = scheduler.ICalScheduler(handle)
        except (ValueError, IndexError, KeyError), e:
            m = messages.Error(T_(N_(
                "Error parsing ical file '%s'."), self._icsfile),
                               debug=log.getExceptionMessage(e),
                               mid="error-icalbouncer-file")
            component.addMessage(m)
            raise errors.ComponentSetupHandledError()
        self.subscriptionToken = \
            self.iCalScheduler.subscribe(self._do_nothing, self._eventEnded)

    def authenticate(self, keycard):
        self.debug('authenticating keycard')

        # need to check if inside an event time
        cal = self.iCalScheduler.getCalendar()
        now = datetime.now(eventcalendar.UTC)
        eventInstances = cal.getActiveEventInstances()
        if not eventInstances:
            keycard.state = keycards.REFUSED
            self.info("failed in authentication, outside hours")
            return None
        last_end = now
        while eventInstances:
            # decorate-sort-undecorate to get the event ending last
            instance = max([(ev.end, ev) for ev in eventInstances])[1]
            duration = instance.end - now

            if duration > self.maxKeyCardDuration:
                duration = self.maxKeyCardDuration
                break
            if last_end == instance.end:
                break
            eventInstances = cal.getActiveEventInstances(instance.end)
            last_end = instance.end

        durationSecs = duration.days * 86400 + duration.seconds
        keycard.duration = durationSecs
        keycard.state = keycards.AUTHENTICATED
        self.info("authenticated login, duration %d seconds",
                  durationSecs)
        return keycard

    def stop(self, component):
        # we might not have an iCalScheduler, if something went wrong
        # during do_setup or do_check
        if self.iCalScheduler:
            self.iCalScheduler.cleanup()
        if self.subscriptionToken:
            self.iCalScheduler.unsubscribe(self.subscriptionToken)
            self.subscriptionToken = None

    def _eventEnded(self, event):
        self.debug("_eventEnded")
        if not event.start < datetime.now(eventcalendar.UTC) < event.end:
            return
        cal = self.iCalScheduler.getCalendar()
        eventInstances = cal.getActiveEventInstances()
        if not eventInstances:
            self.debug("We're now outside hours, revoking all keycards")
            self._expire_all_keycards()

    def _expire_all_keycards(self):
        self.expire(self.keycards.keys())

    def _do_nothing(self, _):
        pass
