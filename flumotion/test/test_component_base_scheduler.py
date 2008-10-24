# -*- test-case-name: flumotion.test.test_component_base_scheduler -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# Flumotion - a streaming media server
# Copyright (C) 2006,2007,2008 Fluendo, S.L. (www.fluendo.com).
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

#TODO: use setUp

import os
import time

from datetime import datetime, date, timedelta

import calendar
import icalendar

from twisted.internet import defer, reactor

from flumotion.common import eventcalendar, testsuite
from flumotion.component.base import scheduler

LOCAL = eventcalendar.LOCAL
UTC = eventcalendar.UTC


def _now(tz=LOCAL):
    return datetime.now(tz)


def _toSeconds(td):
    return max(td.days * 24 * 3600 + td.seconds + td.microseconds / 1e6, 0)


class SchedulerTest(testsuite.TestCase):

    def assertEventAttribsEqual(self, event, start, end, content,
                                rrules, exdates):
        self.assertEqual(start, event.start)
        self.assertEqual(end, event.end)
        self.assertEqual(content, event.content)
        self.assertEqual(rrules, event.rrules)
        self.assertEqual(exdates, event.exdates)

    def setUp(self):
        self._scheduler = scheduler.Scheduler()

    def tearDown(self):
        self._scheduler.cleanup()
        self.failIf(self._scheduler._delayedCall)

    def testInstantiate(self):
        self.failIf(not self._scheduler)

    def testSubscribe(self):
        # create a list to store subscription call results
        calls = []
        started = lambda ei: calls.append(('started', ei.event.content))
        ended = lambda ei: calls.append(('ended', ei.event.content))
        sid = self._scheduler.subscribe(started, ended)
        self.assertEquals(calls, [])

        # create a calendar and put a currently active event on it
        calendar = eventcalendar.Calendar()
        now = _now()
        start = now - timedelta(hours=1)
        end = now + timedelta(minutes=1)

        calendar.addEvent(eventcalendar.Event('uid', start, end, 'foo'))
        self._scheduler.setCalendar(calendar)

        # verify that we gat a start call for the active event instance
        self.assertEquals(calls, [('started', 'foo')])

        eis = self._scheduler.getCalendar().getActiveEventInstances()

        self.assertEventAttribsEqual(eis[0].event, start, end, 'foo',
                                     None, None)

        # now set a new empty calendar on the scheduler
        calendar = eventcalendar.Calendar()
        self._scheduler.setCalendar(calendar)

        # make sure we got an end call for the previously active event instance
        self.assertEquals(calls, [('started', 'foo'),
                                  ('ended', 'foo')])
        eis = self._scheduler.getCalendar().getActiveEventInstances()
        self.failIf(eis,
            'Empty calendar so should not have active event instances')

        self._scheduler.unsubscribe(sid)

    def testUnsubscribe(self):
        # create a list to store subscription call results
        calls = []
        started = lambda c: calls.append(('started', c.content))
        ended = lambda c: calls.append(('ended', c.content))
        sid = self._scheduler.subscribe(started, ended)
        self._scheduler.unsubscribe(sid)

        now = _now()
        start = now - timedelta(hours=1)
        end = now + timedelta(minutes=1)

        calendar = eventcalendar.Calendar()
        self.assertEquals(calls, [])
        calendar.addEvent(eventcalendar.Event('uid', start, end, 'content'))

        self._scheduler.setCalendar(calendar)
        self.assertEquals(calls, [])

        eis = self._scheduler.getCalendar().getActiveEventInstances()
        self.failUnless(eis)
        self.assertEquals(eis[0].event.content, 'content')

    def testDefaultScheduledCallbackWhenAfterTheWindowSize(self):
        now = _now()
        start = now + timedelta(days=2)
        end = start + timedelta(minutes=1)

        calendar = eventcalendar.Calendar()
        calendar.addEvent(eventcalendar.Event('uid', start, end, 'content'))
        self._scheduler.setCalendar(calendar)

        resultSeconds = self._scheduler._nextStart
        expectedSeconds = _toSeconds(self._scheduler.windowSize) / 2
        self.assertEquals(round(resultSeconds / 10.0),
                          round(expectedSeconds / 10.0))

    def testDefaultScheduledCallbackWhenBeforeAndAfterTheWindowSize(self):
        now = _now()
        start = now - timedelta(days=1)
        end = now + timedelta(days=2)

        calendar = eventcalendar.Calendar()
        calendar.addEvent(eventcalendar.Event('uid', start, end, 'content'))
        self._scheduler.setCalendar(calendar)

        resultSeconds = self._scheduler._nextStart
        expectedSeconds = _toSeconds(self._scheduler.windowSize) / 2
        self.assertEquals(round(resultSeconds / 10.0),
                          round(expectedSeconds / 10.0))

    def testScheduledStartCallbackWhenStartInWindowSize(self):
        now = _now()
        start = now + timedelta(minutes=30)
        end = now + timedelta(hours=1)

        calendar = eventcalendar.Calendar()
        calendar.addEvent(eventcalendar.Event('uid', start, end, 'content'))
        self._scheduler.setCalendar(calendar)

        resultSeconds = self._scheduler._nextStart
        expectedSeconds = _toSeconds(start - now)
        self.assertEquals(round(resultSeconds / 10.0),
                          round(expectedSeconds / 10.0))

    def testScheduledEndCallbackWhenEndInWindowSize(self):
        now = _now()
        start = now - timedelta(hours=1)
        end = now + timedelta(hours=1)

        calendar = eventcalendar.Calendar()
        calendar.addEvent(eventcalendar.Event('uid', start, end, 'content'))
        self._scheduler.setCalendar(calendar)

        resultSeconds = self._scheduler._nextStart
        expectedSeconds = _toSeconds(end-now)
        self.assertEquals(round(resultSeconds / 10.0),
                          round(expectedSeconds / 10.0))

    def testWindowSizeByDefault(self):
        self.assertEquals(self._scheduler.windowSize, timedelta(days=1))

    def testScheduledNotACallbackWhenCancelled(self):
        now = _now()
        start = now
        end = now + timedelta(hours=1)

        calendar = eventcalendar.Calendar()
        calendar.addEvent(eventcalendar.Event('uid', start, end, 'content'))
        self._scheduler.setCalendar(calendar)
