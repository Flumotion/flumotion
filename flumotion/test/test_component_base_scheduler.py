# -*- test-case-name: flumotion.test.test_component_base_scheduler -*-
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

#TODO: use setUp

from datetime import datetime, date, timedelta

import calendar
from icalendar import Calendar, Event
from twisted.internet import defer, reactor

from flumotion.common import eventcalendar, testsuite
from flumotion.component.base import scheduler


def _now(tz=scheduler.LOCAL):
    return datetime.now(tz)

dayOfTheWeek = ['MO', 'TU', 'WE', 'TH', 'FR', 'SA', 'SU']


def toSeconds(td):
    return max(td.days * 24 * 3600 + td.seconds + td.microseconds / 1e6, 0)


class SchedulerTest(testsuite.TestCase):

    def assertEventAttribsEqual(self, event, start, end, content,
                                rrule, exdates):
        self.assertEqual(start, event.start)
        self.assertEqual(end, event.end)
        self.assertEqual(content, event.content)
        self.assertEqual(rrule, event.rrule)
        self.assertEqual(exdates, event.exdates)

    def setUp(self):
        self._scheduler = scheduler.Scheduler()

    def testInstantiate(self):
        self.failIf(not self._scheduler)

    def testAddEvent(self):
        start = _now()
        end = start + timedelta(hours=1)
        content = "content"
        rrule = None
        now = start
        uid = 'uid'
        exdates = [start + timedelta(hours=2)]
        self._scheduler.addEvent(uid, start, end, content,
                                 rrule, now, exdates)
        event = self._scheduler._eventSets[uid]._events[0]
        self._scheduler._cancelScheduledCalls()
        self.assertEventAttribsEqual(event, start, end, content,
                                     rrule, exdates)

    def testRemoveEvent(self):
        start = _now()
        end = start + timedelta(hours=1)
        content = "content"
        rrule = None
        now = start
        uid = 'uid'
        exdates = [start + timedelta(hours=2)]
        e1 = self._scheduler.addEvent(uid, start, end, content, rrule,
                                      now, exdates)
        self._scheduler.removeEvent(e1)
        self._scheduler._cancelScheduledCalls()
        self.failIf(self._scheduler._eventSets[e1.uid]._events)

    def testAddEventsWithSameUID(self):
        uid = 'uid'
        start1 = _now()
        end1 = start1 + timedelta(hours=1)
        content1 = "content1"
        rrule1 = None
        now1 = start1
        exdates1 = [start1 + timedelta(hours=2)]
        start2 = start1
        end2 = start2 + timedelta(hours=1)
        content2 = "content2"
        rrule2 = None
        now2 = start2
        exdates2 = [start2 + timedelta(hours=2)]
        e1 = eventcalendar.Event(uid, start1, end1, content1, rrule=rrule1,
                                 now=now1, exdates=exdates1)
        e2 = eventcalendar.Event(uid, start2, end2, content2, rrule=rrule2,
                                 now=now2, exdates=exdates2)
        self._scheduler.addEvents([e1, e2])
        event1 = self._scheduler._eventSets[uid]._events[0]
        event2 = self._scheduler._eventSets[uid]._events[1]
        self.assertEquals(len(self._scheduler._eventSets[uid]._events), 2)
        self.assertEventAttribsEqual(event1, start1, end1, content1,
                                     rrule1, exdates1)
        self.assertEventAttribsEqual(event2, start2, end2, content2,
                                     rrule2, exdates2)
        self._scheduler.removeEvent(event1)
        self._scheduler.removeEvent(event2)
        self._scheduler._cancelScheduledCalls()

    def testAddEventsWithDifferentUID(self):
        uid1 = 'uid1'
        start1 = _now()
        end1 = start1 + timedelta(hours=1)
        content1 = "content1"
        rrule1 = None
        now1 = start1
        exdates1 = [start1 + timedelta(hours=2)]
        uid2 = 'uid2'
        start2 = start1
        end2 = start2 + timedelta(hours=1)
        content2 = "content2"
        rrule2 = None
        now2 = start2
        exdates2 = [start2 + timedelta(hours=2)]
        e1 = eventcalendar.Event(uid1, start1, end1, content1, rrule=rrule1,
                                 now=now1, exdates=exdates1)
        e2 = eventcalendar.Event(uid2, start2, end2, content2, rrule=rrule2,
                                 now=now2, exdates=exdates2)
        self._scheduler.addEvents([e1, e2])
        event1 = self._scheduler._eventSets[uid1]._events[0]
        event2 = self._scheduler._eventSets[uid2]._events[0]
        self.assertEquals(len(self._scheduler._eventSets[uid1]._events), 1)
        self.assertEquals(len(self._scheduler._eventSets[uid2]._events), 1)
        self.assertEventAttribsEqual(event1, start1, end1, content1,
                                     rrule1, exdates1)
        self.assertEventAttribsEqual(event2, start2, end2, content2,
                                     rrule2, exdates2)
        self._scheduler.removeEvent(event1)
        self._scheduler.removeEvent(event2)
        self._scheduler._cancelScheduledCalls()

    def testGetCurrentsSimple(self):
        uid = 'uid'
        now = _now()
        start = now - timedelta(hours=1)
        end = now + timedelta(minutes=1)
        e = self._scheduler.addEvent(uid, start, end, 'foo', now=now)
        current_event = self._scheduler.getCurrentEvents()[0]
        self._scheduler.removeEvent(e)
        self._scheduler._cancelScheduledCalls()
        self.assertEventAttribsEqual(current_event, start, end, 'foo',
                                     None, None)
        self.failIf(self._scheduler.getCurrentEvents())

    def testSubscribe(self):
        now = _now()
        start = now - timedelta(hours=1)
        end = now + timedelta(minutes=1)
        calls = []
        started = lambda c: calls.append(('started', c.content))
        ended = lambda c: calls.append(('ended', c.content))
        sid = self._scheduler.subscribe(started, ended)
        self.assertEquals(calls, [])
        e = self._scheduler.addEvent('uid', start, end, 'foo', now=now)
        self.assertEquals(calls, [('started', 'foo')])
        current_event = self._scheduler.getCurrentEvents()[0]
        self._scheduler.removeEvent(e)
        self.assertEventAttribsEqual(current_event, start, end, 'foo',
                                     None, None)
        self.assertEquals(calls, [('started', 'foo'),
                                  ('ended', 'foo')])
        self.assertEquals(self._scheduler.getCurrentEvents(), [])
        self._scheduler.unsubscribe(sid)
        self._scheduler._cancelScheduledCalls()

    def testUnsubscribe(self):
        now = _now()
        start = now - timedelta(hours=1)
        end = now + timedelta(minutes=1)
        calls = []
        started = lambda c: calls.append(('started', c.content))
        ended = lambda c: calls.append(('ended', c.content))
        sid = self._scheduler.subscribe(started, ended)
        self._scheduler.unsubscribe(sid)
        self.assertEquals(calls, [])
        e = self._scheduler.addEvent('uid', start, end, 'foo', now=now)
        self.assertEquals(calls, [])
        self.failIf(not self._scheduler.getCurrentEvents())
        current_event = self._scheduler.getCurrentEvents()[0]
        self.assertEquals(current_event.content, 'foo')
        self._scheduler.removeEvent(e)
        self._scheduler._cancelScheduledCalls()

    def testOverlappingEvents(self):
        now = _now()
        start = now - timedelta(hours=1)
        end = now + timedelta(hours=1)
        e1 = self._scheduler.addEvent('uid', start, end, "event1", now=now)
        e2 = self._scheduler.addEvent('uid', start, end, "event2", now=now)
        current = self._scheduler.getCurrentEvents()[:]
        self._scheduler.removeEvent(e2)
        self._scheduler.removeEvent(e1)
        self._scheduler._cancelScheduledCalls()
        self.assertEquals(len(current), 2)
        self.failIf(not ((current[0].content == 'event1' and
                         current[1].content == 'event2')
                         or
                         (current[0].content == 'event2' and
                          current[1].content == 'event1')))

    def testRecurrenceEventsDaily(self):
        now = _now()
        start = now - timedelta(hours=1)
        start = start.replace(microsecond=0)
        end = now + timedelta(hours=1)
        end = end.replace(microsecond=0)
        uid = 'uid'
        rrule = "FREQ=DAILY;WKST=MO"
        e1 = self._scheduler.addEvent(uid, start, end, "event1",
                                      rrule=rrule, now=now)
        current = self._scheduler.getCurrentEvents(now)[:]
        self.assertEquals(len(current), 1)
        content = current[0].content
        currentStart = current[0].start
        currentEnd = current[0].end
        currentStartCurrent = current[0].currentStart
        currentEndCurrent = current[0].currentEnd
        current2 = self._scheduler.getCurrentEvents(now + timedelta(days=1))
        e2 = current2[0]
        currentStartCurrent2 = current2[0].currentStart
        currentEndCurrent2 = current2[0].currentEnd
        self._scheduler.removeEvent(e1)
        self._scheduler._cancelScheduledCalls()
        self.assertEventAttribsEqual(e1, currentStart, currentEnd, content,
                                     rrule, None)
        self.assertEquals(currentStartCurrent, start)
        self.assertEquals(currentEndCurrent, end)
        self.assertEquals(len(current2), 1)
        self.assertEventAttribsEqual(e2, start, end, 'event1',
                                     rrule, None)
        self.assertEquals(currentStartCurrent2, start + timedelta(days=1))
        self.assertEquals(currentEndCurrent2, end + timedelta(days=1))

    def testRecurrenceEventsHourly(self):
        now = _now()
        now = now.replace(microsecond=0)
        start = now - timedelta(hours=2) + timedelta(minutes=2)
        end = now - timedelta(hours=1) + timedelta(minutes=2)
        uid = 'uid'
        rrule = "FREQ=HOURLY;WKST=MO"
        e1 = self._scheduler.addEvent(uid, start, end, "event1",
                                      rrule=rrule, now=now)
        current = self._scheduler.getCurrentEvents(now)[:]
        self.assertEquals(len(current), 1)
        content = current[0].content
        currentStart = current[0].start
        currentEnd = current[0].end
        currentStartCurrent = current[0].currentStart
        currentEndCurrent = current[0].currentEnd
        current2 = self._scheduler.getCurrentEvents(now + timedelta(hours=1))
        self.assertEquals(len(current2), 1)
        e2 = current2[0]
        currentStartCurrent2 = current2[0].currentStart
        currentEndCurrent2 = current2[0].currentEnd
        self._scheduler.removeEvent(e1)
        self._scheduler._cancelScheduledCalls()
        self.assertEventAttribsEqual(e1, currentStart, currentEnd,
                                     content, rrule, None)
        self.assertEquals(currentStartCurrent, now - timedelta(hours=1) +
                          timedelta(minutes=2))
        self.assertEquals(currentEndCurrent, now + timedelta(minutes=2))
        self.assertEquals(len(current2), 1)
        self.assertEventAttribsEqual(e2, start, end,
                                     content, rrule, None)
        self.assertEquals(currentStartCurrent2, now + timedelta(minutes=2))
        self.assertEquals(currentEndCurrent2, now + timedelta(minutes=2) +
                          timedelta(hours=1))

    def testRecurrenceEventsWhereExDateIsStartDate(self):
        """
        Recurrence rules that have exceptions.
        """
        now = _now()
        now = now.replace(microsecond=0) # recurring adjustments lose precision
        start = now - timedelta(hours=1) - timedelta(minutes=1)
        end = now - timedelta(minutes=1)
        exdates = [start]
        rrule = "FREQ=HOURLY;INTERVAL=1;COUNT=5"
        uid = 'uid'
        e = self._scheduler.addEvent(uid, start, end, 'foo', rrule,
                                    now=now, exdates=exdates)
        current = self._scheduler.getCurrentEvents(start)[:]
        self._scheduler.removeEvent(e)
        self._scheduler._cancelScheduledCalls()
        self.failIf(current)

    def testRecurrenceEventsWhereExDateIsNotNow(self):
        """
        Recurrence rules that have exceptions.
        """
        now = _now()
        now = now.replace(microsecond=0) # recurring adjustments lose precision
        start = now - timedelta(hours=1) - timedelta(minutes=1)
        end = now - timedelta(minutes=1)
        exdates = [start]
        rrule = "FREQ=HOURLY;INTERVAL=1;COUNT=5"
        uid = 'uid'
        e = self._scheduler.addEvent(uid, start, end, 'foo', rrule, now=now,
                       exdates=exdates)
        current2 = self._scheduler.getCurrentEvents(now)[:]
        self._scheduler.removeEvent(e)
        self._scheduler._cancelScheduledCalls()
        self.failIf(not current2)

    def testRecurrenceEventsWhereExDateIsNotStartDate(self):
        """
        Recurrence rules that have exceptions.
        """
        now = _now()
        now = now.replace(microsecond=0) # recurring adjustments lose precision
        start = now - timedelta(hours=1) - timedelta(minutes=1)
        end = now - timedelta(minutes=1)
        exdates = [start + timedelta(hours=1)]
        rrule = "FREQ=HOURLY;INTERVAL=1;COUNT=5"
        uid = 'uid'
        e = self._scheduler.addEvent(uid, start, end, 'foo', rrule,
                                     now=now, exdates=exdates)
        current = self._scheduler.getCurrentEvents(now)[:]
        self._scheduler.removeEvent(e)
        self._scheduler._cancelScheduledCalls()
        self.failIf(current)

    def testRecurrenceEventsOverMidnight(self):
        """
        Test weekly recurrence rules that starts on one day and spawns to
        the day after, even though they were not planned for the next day.
        """

        def yesterdayDayOfTheWeek(now):
            yesterday = now - timedelta(days=1)
            day = calendar.weekday(yesterday.year, yesterday.month,
                                   yesterday.day)
            return dayOfTheWeek[day]

        now = _now().replace(microsecond=0)
        start = now - timedelta(days=1) - timedelta(weeks=1)
        end = now + timedelta(hours=1) - timedelta(weeks=1)
        rrule = "FREQ=WEEKLY;BYDAY="+yesterdayDayOfTheWeek(now)+";WKST=MO"
        uid = 'uid'
        content = 'content'
        e1 = self._scheduler.addEvent(uid, start, end, content,
                                      rrule=rrule, now=now)
        current = self._scheduler.getCurrentEvents()[:]
        self.assertEquals(len(current), 1)
        self._scheduler.removeEvent(e1)
        self._scheduler._cancelScheduledCalls()
        event = current[0]
        self.assertEventAttribsEqual(event, start, end, 'content',
                                     rrule, None)

    def testOverMidnight(self):
        now = _now()
        start = now - timedelta(days=1)
        end = now + timedelta(hours=1)
        uid = 'uid'
        rrule = None
        e1 = self._scheduler.addEvent(uid, start, end, "event1",
                                      rrule=rrule, now=now)
        current = self._scheduler.getCurrentEvents()[:]
        self._scheduler.removeEvent(e1)
        self._scheduler._cancelScheduledCalls()
        self.assertEquals(len(current), 1)
        event = current[0]
        self.assertEventAttribsEqual(event, start, end, 'event1',
                                     None, None)

    def testCurrentEventsDoNotEndBeforeNow(self):
        now = _now()
        start = now - timedelta(hours=2)
        end = now - timedelta(hours=1)
        uid = 'uid'
        self._scheduler.addEvent(uid, start, end, "event1", now=now)
        current = self._scheduler.getCurrentEvents()[:]
        self._scheduler._cancelScheduledCalls()
        self.failIf(current)

    def testCurrentEventsDoNotStartLaterThanTomorrow(self):
        now = _now()
        start = now + timedelta(days=2)
        end = now + timedelta(days=3)
        rrule = None
        uid = 'uid'
        e1 = self._scheduler.addEvent(uid, start, end, "event1",
                                      rrule=rrule, now=now)
        current = self._scheduler.getCurrentEvents()[:]
        self._scheduler.removeEvent(e1)
        self._scheduler._cancelScheduledCalls()
        self.failIf(current)

    def testReplaceFutureEvent(self):
        uid = 'uid'
        now = _now()
        start = now + timedelta(hours=1)
        end = start + timedelta(minutes=1)
        content = 'foo'
        self._scheduler.addEvent(uid, start, end, content, now=now)
        event = self._scheduler._eventSets[uid]._events[0]
        newStart = start + timedelta(minutes=30)
        newEnd = newStart + timedelta(minutes=2)
        newContent = 'new content'
        new_e = eventcalendar.Event(uid, newStart, newEnd, newContent,
                                    now=now)
        self._scheduler.replaceEvents([new_e])
        newEvent = self._scheduler._eventSets[uid]._events[0]
        self._scheduler.removeEvent(newEvent)
        events = self._scheduler._eventSets[uid]._events
        self._scheduler._cancelScheduledCalls()
        self.assertEventAttribsEqual(event, start, end, content,
                                     None, None)
        self.assertEventAttribsEqual(newEvent, newStart, newEnd, newContent,
                                     None, None)
        self.failIf(events)

    def testReplaceFutureEvents(self):
        uid = 'uid'
        now = _now()
        start1 = now + timedelta(hours=1)
        end1 = start1 + timedelta(minutes=1)
        content1 = 'foo'
        self._scheduler.addEvent(uid, start1, end1, content1, now=now)
        uid = 'uid'
        now = _now()
        start2 = start1 + timedelta(hours=2)
        end2 = start2 + timedelta(minutes=1)
        content2 = 'foo'
        self._scheduler.addEvent(uid, start2, end2, content2, now=now)
        newStart1 = start1 + timedelta(minutes=30)
        newEnd1 = newStart1 + timedelta(minutes=2)
        newContent1 = 'new content'
        new_e1 = eventcalendar.Event(uid, newStart1, newEnd1, newContent1,
                                     now=now)
        newStart2 = start2 + timedelta(minutes=30)
        newEnd2 = newStart1 + timedelta(minutes=2)
        newContent2 = 'new content2'
        uid2 = 'uid2'
        new_e2 = eventcalendar.Event(uid2, newStart2, newEnd2, newContent2,
                                     now=now)
        self._scheduler.replaceEvents([new_e1, new_e2])
        newEvent1 = self._scheduler._eventSets[uid]._events[0]
        newEvent2 = self._scheduler._eventSets[uid2]._events[0]
        self._scheduler.removeEvent(newEvent1)
        self._scheduler.removeEvent(newEvent2)
        events = self._scheduler._eventSets[uid]._events
        self._scheduler._cancelScheduledCalls()
        self.assertEventAttribsEqual(newEvent1, newStart1, newEnd1,
                                     newContent1, None, None)
        self.assertEventAttribsEqual(newEvent2, newStart2, newEnd2,
                                     newContent2, None, None)
        self.failIf(events)

    def testNoReplaceOnCurrentEvent(self):
        uid = 'uid'
        now = _now()
        start = now - timedelta(hours=1)
        end = now + timedelta(minutes=1)
        content = 'foo'
        self._scheduler.addEvent(uid, start, end, content, now=now)
        event = self._scheduler._eventSets[uid]._events[0]
        newStart = now + timedelta(minutes=30)
        newEnd = now + timedelta(minutes=35)
        newContent = 'new content'
        new_e = eventcalendar.Event(uid, newStart, newEnd, newContent,
                                    now=now)
        self._scheduler.replaceEvents([new_e])
        self.assertEquals(len(self._scheduler._eventSets[uid]._events), 2)
        newEvent0 = self._scheduler._eventSets[uid]._events[0]
        newEvent1 = self._scheduler._eventSets[uid]._events[1]
        self._scheduler.removeEvent(newEvent0)
        self._scheduler.removeEvent(newEvent1)
        events = self._scheduler._eventSets[uid]._events
        self._scheduler._cancelScheduledCalls()
        self.failIf(not (((newEvent0.content == event.content and
                          newEvent1.content == new_e.content) or
                        ((newEvent1.content == event.content) and
                         newEvent0.content == new_e.content))))
        self.failIf(events)

    def testNoReplaceOnNewCurrentEvent(self):
        uid = 'uid'
        now = _now()
        start = now + timedelta(hours=1)
        end = start + timedelta(minutes=1)
        content = 'foo'
        self._scheduler.addEvent(uid, start, end, content, now=now)
        newStart = now - timedelta(minutes=30)
        newEnd = now + timedelta(minutes=35)
        newContent = 'new content'
        new_e = eventcalendar.Event(uid, newStart, newEnd, newContent,
                                    now=now)
        self._scheduler.replaceEvents([new_e])
        events = self._scheduler._eventSets[uid]._events
        self._scheduler._cancelScheduledCalls()
        self.failIf(events)

    def testNotACallbackWhenInit(self):
        self.failIf(self._scheduler._delayedCall)

    def testDefaultScheduledCallbackWhenAfterTheWindowSize(self):
        now = _now()
        start = now + timedelta(days=2)
        end = start + timedelta(minutes=1)
        self._scheduler.addEvent('uid', start, end, 'content', now=now)
        resultSeconds = self._scheduler._nextStart
        expectedSeconds = toSeconds(self._scheduler.windowSize)
        self.assertEquals(round(resultSeconds / 10.0),
                          round(expectedSeconds / 10.0))
        self._scheduler._cancelScheduledCalls()

    def testDefaultScheduledCallbackWhenBeforeAndAfterTheWindowSize(self):
        now = _now()
        start = now - timedelta(days=1)
        end = now + timedelta(days=2)
        self._scheduler.addEvent('uid', start, end, 'content', now=now)
        resultSeconds = self._scheduler._nextStart
        expectedSeconds = toSeconds(self._scheduler.windowSize)
        self.assertEquals(round(resultSeconds / 10.0),
                          round(expectedSeconds / 10.0))
        self._scheduler._cancelScheduledCalls()

    def testScheduledStartCallbackWhenStartInWindowSize(self):
        now = _now()
        start = now + timedelta(minutes=30)
        end = now + timedelta(hours=1)
        self._scheduler.addEvent('uid', start, end, 'content', now=now)
        resultSeconds = self._scheduler._nextStart
        expectedSeconds = toSeconds(start - now)
        self.assertEquals(round(resultSeconds / 10.0),
                          round(expectedSeconds / 10.0))
        self._scheduler._cancelScheduledCalls()

    def testScheduledEndCallbackWhenEndInWindowSize(self):
        now = _now()
        start = now - timedelta(hours=1)
        end = now + timedelta(hours=1)
        self._scheduler.addEvent('uid', start, end, 'content', now=now)
        resultSeconds = self._scheduler._nextStart
        expectedSeconds = toSeconds(end-now)
        self.assertEquals(round(resultSeconds / 10.0),
                          round(expectedSeconds / 10.0))
        self._scheduler._cancelScheduledCalls()

    def testWindowSizeByDefault(self):
        self.assertEquals(self._scheduler.windowSize, timedelta(days=1))

    def testScheduledNotACallbackWhenCancelled(self):
        now = _now()
        start = now
        end = now + timedelta(hours=1)
        self._scheduler.addEvent('uid', start, end, 'content', now=now)
        self._scheduler._cancelScheduledCalls()
        self.failIf(self._scheduler._delayedCall)


class ICalSchedulerTest(testsuite.TestCase):

    def setUp(self):
        self._scheduler = scheduler.ICalScheduler(None)

    def testParseCalendarWithDates(self):
        LOCAL = scheduler.LOCAL
        start_expected = datetime(2015, 4, 4, 0, 0, 0, tzinfo=LOCAL)
        end_expected = datetime(2015, 4, 5, 0, 0, 0, tzinfo=LOCAL)
        cal = Calendar()
        cal['prodid'] = '-//My calendar product//mxm.dk//'
        cal['version'] = '2.0'
        event = Event()
        event['summary'] = 'Test calendar'
        event['uid'] = '42'
        event.set('dtstart', date(2015, 4, 4))
        event.set('dtend', date(2015, 4, 5))
        cal.add_component(event)
        self._scheduler.parseCalendar(cal)
        eventSets = self._scheduler._eventSets
        self.failIf(len(eventSets)!=1)
        events = eventSets.values()[0].getEvents()
        self._scheduler._cancelScheduledCalls()
        self.failIf(len(events) != 1)
        self.assertEquals(events[0].start, start_expected)
        self.assertEquals(events[0].end, end_expected)

    def testParseCalendarWithDateTimes(self):
        LOCAL = scheduler.LOCAL
        start_expected = datetime(2015, 4, 4, 8, 0, 0, tzinfo=LOCAL)
        end_expected = datetime(2015, 4, 5, 8, 0, 0, tzinfo=LOCAL)
        cal = Calendar()
        cal['prodid'] = '-//My calendar product//mxm.dk//'
        cal['version'] = '2.0'
        event = Event()
        event['summary'] = 'Test calendar'
        uid = 42
        event['uid'] = uid
        event.set('dtstart', datetime(2015, 4, 4, 8, 0, 0, tzinfo=LOCAL))
        event.set('dtend', datetime(2015, 4, 5, 8, 0, 0, tzinfo=LOCAL))
        cal.add_component(event)
        self._scheduler.parseCalendar(cal)
        eventSets = self._scheduler._eventSets
        self.failIf(len(eventSets) != 1)
        events = eventSets.values()[0].getEvents()
        self._scheduler._cancelScheduledCalls()
        self.failIf(len(events) != 1)
        self.assertEquals(events[0].start, start_expected)
        self.assertEquals(events[0].end, end_expected)

    def testParseCalendarWithStartDateAndEndDateTime(self):
        LOCAL = scheduler.LOCAL
        start_expected = datetime(2015, 4, 4, 0, 0, 0, tzinfo=LOCAL)
        end_expected = datetime(2015, 4, 5, 8, 0, 0, tzinfo=LOCAL)
        cal = Calendar()
        cal['prodid'] = '-//My calendar product//mxm.dk//'
        cal['version'] = '2.0'
        event = Event()
        event['summary'] = 'Test calendar'
        uid = '42'
        event['uid'] = uid
        event.set('dtstart', date(2015, 4, 4))
        event.set('dtend', datetime(2015, 4, 5, 8, 0, 0, tzinfo=LOCAL))
        cal.add_component(event)
        self._scheduler.parseCalendar(cal)
        eventSets = self._scheduler._eventSets
        self.failIf(len(eventSets) != 1)
        events = eventSets.values()[0].getEvents()
        self._scheduler._cancelScheduledCalls()
        self.failIf(len(events) != 1)
        self.assertEquals(events[0].start, start_expected)
        self.assertEquals(events[0].end, end_expected)

    def testParseCalendarWithStartDateTimeAndEndDate(self):
        LOCAL = scheduler.LOCAL
        start_expected = datetime(2015, 4, 4, 8, 0, 0, tzinfo=LOCAL)
        end_expected = datetime(2015, 4, 5, 0, 0, 0, tzinfo=LOCAL)
        cal = Calendar()
        cal['prodid'] = '-//My calendar product//mxm.dk//'
        cal['version'] = '2.0'
        event = Event()
        event['summary'] = 'Test calendar'
        event['uid'] = '42'
        event.set('dtstart', datetime(2015, 4, 4, 8, 0, 0, tzinfo=LOCAL))
        event.set('dtend', date(2015, 4, 5))
        cal.add_component(event)
        self._scheduler.parseCalendar(cal)
        eventSets = self._scheduler._eventSets
        self.failIf(len(eventSets) != 1)
        events = eventSets.values()[0].getEvents()
        self._scheduler._cancelScheduledCalls()
        self.failIf(len(events) != 1)
        self.assertEquals(events[0].start, start_expected)
        self.assertEquals(events[0].end, end_expected)

    def testParseCalendar(self):
        LOCAL = scheduler.LOCAL
        startExpected = datetime(2015, 4, 4, 8, 0, 0, tzinfo=LOCAL)
        endExpected = datetime(2015, 4, 5, 0, 0, 0, tzinfo=LOCAL)
        cal = Calendar()
        cal['prodid'] = '-//My calendar product//mxm.dk//'
        cal['version'] = '2.0'
        event = Event()
        contentExpected = 'Test calendar'
        event['summary'] = contentExpected
        uidExpected = 'uid'
        event['uid'] = uidExpected
        event.set('dtstart', datetime(2015, 4, 4, 8, 0, 0, tzinfo=LOCAL))
        event.set('dtend', date(2015, 4, 5))
        cal.add_component(event)
        self._scheduler.parseCalendar(cal)
        eventSets = self._scheduler._eventSets
        self.failIf(len(eventSets) != 1)
        events = eventSets.values()[0].getEvents()
        self._scheduler._cancelScheduledCalls()
        self.failIf(len(events) != 1)
        self.assertEquals(events[0].start, startExpected)
        self.assertEquals(events[0].end, endExpected)
        self.assertEquals(events[0].content, contentExpected)
        self.assertEquals(events[0].uid, uidExpected)

    def testParseCalendarFromFile(self):
        LOCAL = scheduler.LOCAL
        cal = Calendar()
        cal.add('prodid', '-//My calendar product//mxm.dk//')
        cal.add('version', '2.0')
        event = Event()
        startExpected = datetime(2015, 4, 4, 8, 0, 0, tzinfo=LOCAL)
        endExpected = datetime(2015, 4, 4, 8, 0, 0, tzinfo=LOCAL)
        contentExpected = 'Test calendar'
        uidExpected = 'uid'
        fileName = 'example.ics'
        event.add('summary', contentExpected)
        event.add('dtstart', startExpected)
        event.add('dtend', endExpected)
        event['uid'] = uidExpected
        cal.add_component(event)
        f = open(fileName, 'wb')
        f.write(cal.as_string())
        f.close()
        s = scheduler.ICalScheduler(open(fileName, 'r'))
        s.stopWatchingIcalFile()
        eventSets = s._eventSets
        self.failIf(len(eventSets) != 1)
        events = eventSets.values()[0].getEvents()
        s._cancelScheduledCalls()
        self.failIf(len(events) != 1)
        event = events[0]

        self.assertEquals(events[0].start, startExpected)
        self.assertEquals(events[0].end, endExpected)
        self.assertEquals(events[0].content, contentExpected)
        self.assertEquals(events[0].uid, uidExpected)


class SchedulerFunctionsTest(testsuite.TestCase):

    def testToDateTime(self):
        self.failIf(eventcalendar.toDateTime(None))
        dateTime = datetime(2015, 4, 4, 8, 0, 0, tzinfo=scheduler.LOCAL)
        self.assertEquals(dateTime, eventcalendar.toDateTime(dateTime))
        d = date(2015, 4, 4)
        dateTimeExpected = datetime(2015, 4, 4, 0, 0, 0,
                                    tzinfo=scheduler.LOCAL)
        self.assertEquals(dateTimeExpected, eventcalendar.toDateTime(d))
