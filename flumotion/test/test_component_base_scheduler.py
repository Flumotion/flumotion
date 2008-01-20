# -*- Mode: Python; test-case-name: flumotion.test.test_component_base_scheduler -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# Flumotion - a streaming media server
# Copyright (C) 2006,2007 Fluendo, S.L. (www.fluendo.com).
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

__version__ = "$Rev$"


from datetime import datetime, timedelta

from twisted.trial import unittest

from flumotion.common import testsuite
from flumotion.component.base import scheduler


def _now(tz=scheduler.LOCAL):
    return datetime.now(tz)


class EventTest(testsuite.TestCase):
    def testSimple(self):
        now = _now()
        start = now - timedelta(hours=1)
        end = now + timedelta(minutes=1)
        e = scheduler.Event(start, end, 'foo')
        self.assertEquals(e.start, start)
        self.assertEquals(e.end, end)
        self.assertEquals(e.content, 'foo')
        self.assertEquals(e.recur, None)

    def testUpdateRecurring(self):
        now = _now()
        now = now.replace(microsecond=0) # recurring adjustments lose precision
        start = now - timedelta(hours=1)
        end = now - timedelta(minutes=1)
        recur = "FREQ=HOURLY;INTERVAL=2;COUNT=5"

        try:
            e = scheduler.Event(start, end, 'foo', recur, now)
        except ImportError:
            raise unittest.SkipTest("don't have dateutil python "
                                    "package installed")

        self.assertEquals(e.start, start + timedelta(hours=2))
        self.assertEquals(e.end, end + timedelta(hours=2))
        self.assertEquals(e.content, 'foo')
        self.assertEquals(e.recur, recur)

        # time passes...
        now += timedelta(hours=2)
        e = e.reschedule(now)
        self.assertEquals(e.start, start + timedelta(hours=4))
        self.assertEquals(e.end, end + timedelta(hours=4))
        self.assertEquals(e.content, 'foo')
        self.assertEquals(e.recur, recur)

    def testComparison(self):
        now = _now()
        hour = timedelta(hours=1)

        self.failUnless(scheduler.Event(now, now+hour, 'foo') <
                        scheduler.Event(now+hour, now+2*hour, 'foo'))
        self.failUnless(scheduler.Event(now, now+hour, 'foo') ==
                        scheduler.Event(now, now+hour, 'foo'))
        self.failUnless(scheduler.Event(now+hour, now+2*hour, 'foo') >
                        scheduler.Event(now, now+hour, 'foo'))

    def testTimeZones(self):
        now = datetime.now()
        hour = timedelta(hours=1)

        self.assertEquals(now.tzinfo, None)

        event = scheduler.Event(now, now+hour, 'foo')
        self.assertEquals(event.start.tzinfo, scheduler.LOCAL)
        self.assertEquals(event.start, now.replace(tzinfo=scheduler.LOCAL))


class SchedulerTest(testsuite.TestCase):
    def testInstantiate(self):
        scheduler.Scheduler()

    def testSimple(self):
        now = _now()
        start = now - timedelta(hours=1)
        end = now + timedelta(minutes=1)

        calls = []
        started = lambda c: calls.append(('started', c.content))
        stopped = lambda c: calls.append(('stopped', c.content))

        s = scheduler.Scheduler()
        sid = s.subscribe(started, stopped)

        self.assertEquals(calls, [])

        s.addEvent(start, end, 'foo', now=now)
        # add again to show that the same event, added twice, is treated
        # as one, and that the new returned event can always be passed
        # to removeEvent
        e = s.addEvent(start, end, 'foo', now=now)
        s.addEvent(start, end, 'foo', now=now)

        self.assertEquals(calls, [('started', 'foo')])
        self.assertEquals(s.getCurrentEvents(), ['foo'])

        s.removeEvent(e)

        self.assertEquals(calls, [('started', 'foo'),
                                  ('stopped', 'foo')])
        self.assertEquals(s.getCurrentEvents(), [])

        s.unsubscribe(sid)
