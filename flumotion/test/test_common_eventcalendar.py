# -*- Mode: Python; test-case-name:flumotion.test.test_common_eventcalendar -*-
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

import os
from datetime import datetime, timedelta, date
import time

import calendar
import icalendar

from dateutil import parser, rrule

from flumotion.common import testsuite
from flumotion.common import eventcalendar
from flumotion.common.eventcalendar import Event, Calendar
from flumotion.common import tz
from flumotion.common.tz import LOCAL, UTC, DSTTimezone

attr = testsuite.attr


def _now(tz=UTC):
    return datetime.now(tz)

_dayOfTheWeek = ['MO', 'TU', 'WE', 'TH', 'FR', 'SA', 'SU']


class ManualCalendarTest(testsuite.TestCase):

    # assertion methods

    def assertEventAttribsEqual(self, event, start, end, content,
                                rrules, exdates):
        self.assertEqual(start, event.start)
        self.assertEqual(end, event.end)
        self.assertEqual(content, event.content)
        self.assertEqual(rrules, event.rrules)
        self.assertEqual(exdates, event.exdates)

    def testAddEventsWithSameUID(self):
        # test that internally they end up in the same event set
        calendar = Calendar()

        start1 = datetime.now(UTC)
        end1 = start1 + timedelta(hours=1)
        content1 = "content1"
        exdates1 = [start1 + timedelta(hours=2)]

        start2 = start1
        end2 = start2 + timedelta(hours=1)
        content2 = "content2"
        exdates2 = [start2 + timedelta(hours=2)]

        e1 = Event('uid', start1, end1, content1, rrules=None,
                   exdates=exdates1)
        e2 = Event('uid', start2, end2, content2, rrules=None,
                   exdates=exdates2)

        calendar.addEvent(e1)
        calendar.addEvent(e2)

        # verify internals of calendar
        event1 = calendar._eventSets['uid']._events[0]
        event2 = calendar._eventSets['uid']._events[1]
        self.assertEquals(len(calendar._eventSets['uid']._events), 2)
        self.assertEventAttribsEqual(event1, start1, end1, content1,
                                     None, exdates1)
        self.assertEventAttribsEqual(event2, start2, end2, content2,
                                     None, exdates2)

    def testAddEventsWithDifferentUID(self):
        # test that internally they end up in different event sets
        calendar = Calendar()

        start1 = datetime.now(UTC)
        end1 = start1 + timedelta(hours=1)
        exdates1 = [start1 + timedelta(hours=2)]

        start2 = start1
        end2 = start2 + timedelta(hours=1)
        exdates2 = [start2 + timedelta(hours=2)]

        e1 = Event('uid1', start1, end1, 'content1', exdates=exdates1)
        e2 = Event('uid2', start2, end2, 'content2', exdates=exdates2)
        calendar.addEvent(e1)
        calendar.addEvent(e2)

        event1 = calendar._eventSets['uid1']._events[0]
        event2 = calendar._eventSets['uid2']._events[0]
        self.assertEquals(len(calendar._eventSets['uid1']._events), 1)
        self.assertEquals(len(calendar._eventSets['uid2']._events), 1)
        self.assertEventAttribsEqual(event1, start1, end1, 'content1',
            None, exdates1)
        self.assertEventAttribsEqual(event2, start2, end2, 'content2',
            None, exdates2)

    def testAddEvent(self):
        now = _now()
        start = now
        end = start + timedelta(hours=1)
        exdates = [start + timedelta(hours=2)]

        calendar = Calendar()
        calendar.addEvent(Event('uid', start, end, 'foo',
            exdates=exdates))

        event = calendar._eventSets['uid']._events[0]
        self.assertEventAttribsEqual(event, start, end, 'foo',
                                     None, exdates)

    def testGetActiveSimple(self):
        now = _now()
        start = now - timedelta(hours=1)
        end = now + timedelta(minutes=1)

        calendar = Calendar()
        calendar.addEvent(Event('uid', start, end, 'foo'))

        ei = calendar.getActiveEventInstances()[0]
        self.assertEventAttribsEqual(ei.event, start, end, 'foo',
                                     None, None)

    def testRecurrenceEventsDaily(self):
        # create a daily recurring event, starting 1 hour ago,
        # and lasting two hours
        now = _now()
        now = now.replace(microsecond=0)
        start = now - timedelta(hours=1)
        end = now + timedelta(hours=1)
        rrules = ["FREQ=DAILY;WKST=MO", ]

        self.debug('now is %s', str(now))
        self.debug('rrule starts at %s', str(start))

        cal = Calendar()
        cal.addEvent(Event('uid', start, end, "event1",
            rrules=rrules))

        # check active instances now
        eis = cal.getActiveEventInstances()
        self.assertEquals(len(eis), 1)

        self.assertEventAttribsEqual(eis[0].event, start, end,
                                     "event1", rrules, None)
        self.assertEquals(eis[0].start, now - timedelta(hours=1))
        self.assertEquals(eis[0].end, now + timedelta(hours=1))

        # check active instances 1 day later
        eis = cal.getActiveEventInstances(now + timedelta(days=1))
        self.assertEquals(len(eis), 1)

        self.assertEventAttribsEqual(eis[0].event, start, end,
                                     "event1", rrules, None)
        self.assertEquals(eis[0].start, now + timedelta(hours=23))
        self.assertEquals(eis[0].end, now + timedelta(hours=25))

    def testRecurrenceEventsHourly(self):
        # create an hourly recurring event, starting 1 hour and 58 minutes ago,
        # and lasting an hour
        now = _now()
        now = now.replace(microsecond=0)
        start = now - timedelta(minutes=118)
        end = now - timedelta(minutes=58)
        rrules = ["FREQ=HOURLY;WKST=MO", ]
        self.debug('now is %s', str(now))
        self.debug('rrule starts at %s', str(start))

        cal = Calendar()
        cal.addEvent(Event('uid', start, end, "event1",
            rrules=rrules))

        # check active instances now
        eis = cal.getActiveEventInstances()
        self.assertEquals(len(eis), 1)

        self.assertEventAttribsEqual(eis[0].event, start, end,
                                     "event1", rrules, None)
        self.assertEquals(eis[0].start, now - timedelta(hours=1) +
                          timedelta(minutes=2))
        self.assertEquals(eis[0].end, now + timedelta(minutes=2))

        # check active instances 1 hour later
        eis = cal.getActiveEventInstances(now + timedelta(hours=1))
        self.assertEquals(len(eis), 1)

        self.assertEventAttribsEqual(eis[0].event, start, end,
                                     "event1", rrules, None)
        self.assertEquals(eis[0].start, now + timedelta(minutes=2))
        self.assertEquals(eis[0].end, now + timedelta(minutes=2) +
                          timedelta(hours=1))

    def testRecurrenceEventsWhereExDateIsStartDate(self):
        """
        Recurrence rules that have exceptions.
        """
        now = _now()
        now = now.replace(microsecond=0) # recurring adjustments lose precision
        start = now - timedelta(minutes=61)
        end = now - timedelta(minutes=1)
        exdates = [start]
        rrules = ["FREQ=HOURLY;INTERVAL=1;COUNT=5", ]

        calendar = Calendar()
        calendar.addEvent(Event('uid', start, end, 'foo',
            rrules=rrules, exdates=exdates))

        eis = calendar.getActiveEventInstances(start)
        self.failIf(eis)

    def testRecurrenceEventsWhereExDateIsNotNow(self):
        """
        Recurrence rules that have exceptions.
        """
        # create an event starting 61 minutes ago, lasting 60 minutes, and
        # repeating every hour for five times;
        # but with an exception for the first instances
        now = _now()
        now = now.replace(microsecond=0) # recurring adjustments lose precision
        start = now - timedelta(minutes=61)
        end = now - timedelta(minutes=1)
        exdates = [start]
        rrules = ["FREQ=HOURLY;INTERVAL=1;COUNT=5", ]

        calendar = Calendar()
        calendar.addEvent(Event('uid', start, end, 'foo',
            rrules=rrules, exdates=exdates))

        eis = calendar.getActiveEventInstances()
        self.failUnless(eis)
        # the first event after the exception happens to start when the
        # exception would have ended
        self.assertEquals(eis[0].start, end)

    def testRecurrenceEventsWhereExDateIsNotStartDate(self):
        """
        Recurrence rules that have exceptions.
        """
        now = _now()
        now = now.replace(microsecond=0) # recurring adjustments lose precision
        start = now - timedelta(minutes=61)
        end = now - timedelta(minutes=1)
        exdates = [start + timedelta(hours=1)]
        rrules = ["FREQ=HOURLY;INTERVAL=1;COUNT=5", ]

        cal = Calendar()
        cal.addEvent(Event(
            'uid', start, end, 'content', rrules=rrules, exdates=exdates))

        self.failIf(cal.getActiveEventInstances())

    def testRecurrenceEventsOverMidnight(self):
        """
        Test weekly recurrence rules that starts on one day and spawns to
        the day after, even though they were not planned for the next day.
        """

        def yesterdayDayOfTheWeek(now):
            yesterday = now - timedelta(days=1)
            day = calendar.weekday(yesterday.year, yesterday.month,
                                   yesterday.day)
            return _dayOfTheWeek[day]

        now = _now().replace(microsecond=0)
        start = now - timedelta(days=1) - timedelta(weeks=1)
        end = now + timedelta(hours=1) - timedelta(weeks=1)
        rrules = [
            "FREQ=WEEKLY;BYDAY=" + yesterdayDayOfTheWeek(now) + ";WKST=MO",
        ]
        cal = Calendar()
        cal.addEvent(Event('uid', start, end, 'content', rrules=rrules))

        eis = cal.getActiveEventInstances()
        self.assertEquals(len(eis), 1)
        self.assertEventAttribsEqual(eis[0].event, start, end, 'content',
                                     rrules, None)

    def testOverMidnight(self):
        now = _now()
        start = now - timedelta(days=1)
        end = now + timedelta(hours=1)
        cal = Calendar()
        cal.addEvent(Event('uid', start, end, 'content'))

        eis = cal.getActiveEventInstances()
        self.assertEquals(len(eis), 1)
        self.assertEventAttribsEqual(eis[0].event, start, end, 'content',
            None, None)

    def testCurrentEventsDoNotEndBeforeNow(self):
        now = _now()
        start = now - timedelta(hours=2)
        end = now - timedelta(hours=1)

        cal = Calendar()
        cal.addEvent(Event('uid', start, end, 'content'))

        self.failIf(cal.getActiveEventInstances())

    def testCurrentEventsDoNotStartLaterThanTomorrow(self):
        now = _now()
        start = now + timedelta(days=2)
        end = now + timedelta(days=3)

        cal = Calendar()
        cal.addEvent(Event('uid', start, end, 'content'))

        self.failIf(cal.getActiveEventInstances())

    def testGetActiveRecurrenceId(self):
        # use a RECCURRENCE-ID with TZID, just to stress the code some more
        data = '''
BEGIN:VCALENDAR
PRODID:-//My calendar product//mxm.dk//
VERSION:2.0
BEGIN:VEVENT
DTSTART:20150404T060000Z
DTEND:20150404T070000Z
RRULE:FREQ=WEEKLY
SUMMARY:Test calendar
UID:uid
END:VEVENT
BEGIN:VEVENT
DTSTART:20150411T070000Z
DTEND:20150411T080000Z
RECURRENCE-ID;TZID=UTC:20150411T060000
SUMMARY:changed event one hour later
UID:uid
END:VEVENT
END:VCALENDAR
        '''
        ical = icalendar.Calendar.from_string(data)

        start = datetime(2015, 4, 4, 6, 0, 0, tzinfo=UTC)
        cal = eventcalendar.fromICalendar(ical)

        # check that the first one is here
        instances = cal.getActiveEventInstances(
            start + timedelta(seconds=1))
        self.assertEquals(len(instances), 1)
        self.assertEquals(instances[0].start, start)

        second = timedelta(seconds=1)

        # check that the second one is not there exactly a week later,
        # because it also moved an hour
        delta = timedelta(days=7)
        instances = cal.getActiveEventInstances(start + delta + second)
        self.assertEquals(len(instances), 0)

        # check that the second one is there where it should be, an hour later
        delta = timedelta(days=7, hours=1)
        instances = cal.getActiveEventInstances(start + delta + second)
        self.assertEquals(len(instances), 1)
        self.assertEquals(instances[0].start, start + delta)

        # check that the third one is back on the hour again
        delta = timedelta(days=14)
        instances = cal.getActiveEventInstances(start + delta + second)
        self.assertEquals(len(instances), 1)
        self.assertEquals(instances[0].start, start + delta)


class ICalSchedulerURGentTest(testsuite.TestCase):

    slow = True

    def setUp(self):
        __thisdir = os.path.dirname(os.path.abspath(__file__))
        self._file = open(os.path.join(__thisdir, 'urgent.ics'))
        start = time.time()
        self._calendar = eventcalendar.fromFile(self._file)
        self.debug('Parsing urgent.ics took %f seconds' % (
            time.time() - start))

    def testVerifyPoints(self):
        # on January 20, 2008, Farkli Bir Gece starts
        # at 11:00 AM CEST or 10:00 UTC
        # check 1 hour before
        dateTime = datetime(2008, 1, 20, 9, 0, 0, tzinfo=UTC)
        points = self._calendar.getPoints(dateTime,
            timedelta(seconds=5400))
        self.assertEquals(len(points), 1)

        point = points[0]
        # verify that it is in a Brussels timezone
        s = str(point.dt.tzinfo)
        event = point.eventInstance.event
        self.failUnless('Brussels' in s)
        self.failUnless(point.dt.utcoffset() == timedelta(hours=1))
        self.failUnless(point.dt.dst() == timedelta(hours=0))
        self.failUnless(event.content.startswith('Farkli Bir Gece'),
            'next change is not to Farkli Bir Gece but to %s' % event.content)
        self.assertEquals(point.which, 'start')
        self.assertEquals(point.dt,
            dateTime + timedelta(seconds=3600))

        # 3 hours later, at 14:00 AM CEST,
        # it stops, and Supercalifragilistic starts
        # check 1 minute before
        dateTime = datetime(2008, 1, 20, 12, 59, 0, tzinfo=UTC)
        points = self._calendar.getPoints(dateTime,
            timedelta(seconds=120))
        self.assertEquals(len(points), 2)

        point = points[0]
        event = point.eventInstance.event
        self.failUnless(event.content.startswith('Farkli Bir Gece'),
            'next change is not to Farkli Bir Gece but to %s' % event.content)
        self.assertEquals(point.which, 'end')
        self.assertEquals(point.dt,
            dateTime + timedelta(seconds=60))

        point = points[1]
        event = point.eventInstance.event
        self.failUnless(event.content.startswith('Supercali'),
            'next change is not to Supercali but to %s' % event.content)
        self.assertEquals(point.which, 'start')
        self.assertEquals(point.dt,
            dateTime + timedelta(seconds=60))

    def test_getActiveEventInstances(self):
        # on January 20, 2008, Farkli Bir Gece starts
        # at 11:00 AM CEST or 10:00 UTC

        # check nothing is active before
        dateTime = datetime(2008, 1, 20, 9, 0, 0, tzinfo=UTC)
        instances = self._calendar.getActiveEventInstances(dateTime)
        self.failIf(instances)

        # check one event is active right after
        dateTime = datetime(2008, 1, 20, 11, 0, 0, tzinfo=UTC)
        instances = self._calendar.getActiveEventInstances(dateTime)
        self.failUnless(instances)
        self.assertEquals(len(instances), 1)
        event = instances[0].event
        self.failUnless(event.content.startswith('Farkli Bir Gece'),
            'next change is not to Farkli Bir Gece but to %s' % event.content)

        # 3 hours later, at 14:00 AM CEST or 13:00 UTC,
        # it stops, and Supercalifragilistic starts
        # check one event is active during second show
        dateTime = datetime(2008, 1, 20, 13, 1, 0, tzinfo=UTC)
        instances = self._calendar.getActiveEventInstances(dateTime)
        self.failUnless(instances)
        self.assertEquals(len(instances), 1)
        event = instances[0].event
        self.failUnless(event.content.startswith('Supercali'),
            'next change is not to Supercali but to %s' % event.content)


class DaylightSavingTimezoneTest(testsuite.TestCase):

    def makeTimezone(self, dststart, dstend, stdrrule, dstrrule):
        return DSTTimezone('Test', 'STANDARD', 'DAYLIGHT',
                           timedelta(hours=1), timedelta(hours=2),
                           timedelta(hours=2), timedelta(hours=1),
                           dststart, dstend, stdrrule, dstrrule)

    def testEuropeanStandardToDaylightChange(self):
        dststart = datetime(1970, 03, 29, 2)
        stdstart = datetime(1970, 10, 25, 3)
        stdrrule = rrule.rrulestr('FREQ=YEARLY;BYMONTH=10;BYDAY=-1SU',
                                   dtstart=stdstart)
        dstrrule = rrule.rrulestr('FREQ=YEARLY;BYMONTH=03;BYDAY=-1SU',
                                   dtstart=dststart)
        tzinfo = self.makeTimezone(stdstart, dststart, stdrrule, dstrrule)
        self.assertEquals(datetime(2011, 3, 26, 1, tzinfo=tzinfo).tzname(),
                          'STANDARD')
        self.assertEquals(datetime(2011, 3, 28, 1, tzinfo=tzinfo).tzname(),
                          'DAYLIGHT')
        self.assertEquals(datetime(2011, 3, 27, 1, tzinfo=tzinfo).tzname(),
                          'STANDARD')
        self.assertEquals(datetime(2011, 3, 27, 2, tzinfo=tzinfo).tzname(),
                          'DAYLIGHT')
        delta= datetime(2011, 3, 27, 3, tzinfo=tzinfo) - \
               datetime(2011, 3, 27, 1, tzinfo=tzinfo.copy())
        self.assertEquals(delta, timedelta(hours=1))

    def testEuropeanDaylightToStandardChange(self):
        dststart = datetime(1970, 03, 29, 2)
        stdstart = datetime(1970, 10, 25, 3)
        stdrrule = rrule.rrulestr('FREQ=YEARLY;BYMONTH=10;BYDAY=-1SU',
                                   dtstart=stdstart)
        dstrrule = rrule.rrulestr('FREQ=YEARLY;BYMONTH=03;BYDAY=-1SU',
                                   dtstart=dststart)
        tzinfo = self.makeTimezone(stdstart, dststart, stdrrule, dstrrule)
        self.assertEquals(datetime(2011, 10, 29, 1, tzinfo=tzinfo).tzname(),
                          'DAYLIGHT')
        self.assertEquals(datetime(2011, 10, 31, 1, tzinfo=tzinfo).tzname(),
                          'STANDARD')
        self.assertEquals(datetime(2011, 10, 30, 1, tzinfo=tzinfo).tzname(),
                          'DAYLIGHT')
        self.assertEquals(datetime(2011, 10, 30, 3, tzinfo=tzinfo).tzname(),
                          'STANDARD')
        delta = datetime(2011, 10, 30, 4, tzinfo=tzinfo) - \
                datetime(2011, 10, 30, 1, tzinfo=tzinfo.copy())
        self.assertEquals(delta, timedelta(hours=4))


class ICalendarTest(testsuite.TestCase):

    def setUp(self):
        self._icalendar = icalendar.Calendar()
        self._icalendar['prodid'] = '-//My calendar product//mxm.dk//'
        self._icalendar['version'] = '2.0'
        self._calendar = None

    def assertOneEventExpected(self, startExpected, endExpected):
        # FIXME: poking at internals
        eventSets = self._calendar._eventSets
        self.assertEquals(len(eventSets), 1)

        events = eventSets.values()[0].getEvents()
        self.assertEquals(len(events), 1)
        self.assertEquals(events[0].start, startExpected)
        self.assertEquals(events[0].end, endExpected)

    def testParseCalendarWithDates(self):
        event = icalendar.Event()
        startExpected = datetime(2015, 4, 4, 0, 0, 0, tzinfo=UTC)
        endExpected = datetime(2015, 4, 5, 0, 0, 0, tzinfo=UTC)
        event['summary'] = 'Test calendar'
        event['uid'] = '42'
        event.set('dtstart', date(2015, 4, 4))
        event.set('dtend', date(2015, 4, 5))

        self._icalendar.add_component(event)

        self._calendar = eventcalendar.fromICalendar(self._icalendar)

        self.assertOneEventExpected(startExpected, endExpected)

    def testParseCalendarWithDateTimes(self):
        event = icalendar.Event()
        startExpected = datetime(2015, 4, 4, 8, 0, 0, tzinfo=LOCAL)
        endExpected = datetime(2015, 4, 5, 8, 0, 0, tzinfo=LOCAL)
        event['summary'] = 'Test calendar'
        event['uid'] = 'uid'
        event.set('dtstart',
            datetime(2015, 4, 4, 8, 0, 0, tzinfo=LOCAL))
        event.set('dtend',
            datetime(2015, 4, 5, 8, 0, 0, tzinfo=LOCAL))

        self._icalendar.add_component(event)

        self._calendar = eventcalendar.fromICalendar(self._icalendar)

        self.assertOneEventExpected(startExpected, endExpected)

    def testParseCalendarWithStartDateAndEndDateTime(self):
        event = icalendar.Event()
        startExpected = datetime(2015, 4, 4, 0, 0, 0, tzinfo=UTC)
        endExpected = datetime(2015, 4, 5, 8, 0, 0, tzinfo=LOCAL)
        event['summary'] = 'Test calendar'
        event['uid'] = '42'
        event.set('dtstart', date(2015, 4, 4))
        event.set('dtend',
            datetime(2015, 4, 5, 8, 0, 0, tzinfo=LOCAL))

        self._icalendar.add_component(event)

        self._calendar = eventcalendar.fromICalendar(self._icalendar)

        self.assertOneEventExpected(startExpected, endExpected)

    def testParseCalendarWithStartDateTimeAndEndDate(self):
        event = icalendar.Event()
        startExpected = datetime(2015, 4, 4, 8, 0, 0, tzinfo=LOCAL)
        endExpected = datetime(2015, 4, 5, 0, 0, 0, tzinfo=UTC)
        event['summary'] = 'Test calendar'
        event['uid'] = '42'
        event.set('dtstart',
            datetime(2015, 4, 4, 8, 0, 0, tzinfo=LOCAL))
        event.set('dtend', date(2015, 4, 5))

        self._icalendar.add_component(event)

        self._calendar = eventcalendar.fromICalendar(self._icalendar)

        self.assertOneEventExpected(startExpected, endExpected)

    def testParseCalendarWithStartDateTimeAndDuration(self):
        event = icalendar.Event()
        startExpected = datetime(2015, 4, 4, 8, 0, 0, tzinfo=LOCAL)
        duration = timedelta(hours=1, minutes=38, seconds=23)
        endExpected = startExpected + duration
        event['summary'] = 'Test calendar'
        event['uid'] = '42'
        event.set('dtstart',
                datetime(2015, 4, 4, 8, 0, 0, tzinfo=LOCAL))
        event.set('duration',
                timedelta(hours=1, minutes=38, seconds=23))

        self._icalendar.add_component(event)

        self._calendar = eventcalendar.fromICalendar(self._icalendar)

        self.assertOneEventExpected(startExpected, endExpected)

    def testParseCalendar(self):
        event = icalendar.Event()
        startExpected = datetime(2015, 4, 4, 8, 0, 0, tzinfo=LOCAL)
        endExpected = datetime(2015, 4, 5, 0, 0, 0, tzinfo=UTC)
        contentExpected = 'Test calendar'
        event['summary'] = contentExpected
        uidExpected = 'uid'
        event['uid'] = uidExpected
        event.set('dtstart',
            datetime(2015, 4, 4, 8, 0, 0, tzinfo=LOCAL))
        event.set('dtend', date(2015, 4, 5))

        self._icalendar.add_component(event)

        self._calendar = eventcalendar.fromICalendar(self._icalendar)

        self.assertOneEventExpected(startExpected, endExpected)

        # FIXME: poking at internals
        eventSets = self._calendar._eventSets
        events = eventSets.values()[0].getEvents()
        self.assertEquals(events[0].content, contentExpected)
        self.assertEquals(events[0].uid, uidExpected)

    def testParseCalendarFromFile(self):
        event = icalendar.Event()
        startExpected = datetime(2015, 4, 4, 8, 0, 0, tzinfo=LOCAL)
        endExpected = datetime(2015, 4, 4, 9, 0, 0, tzinfo=LOCAL)
        contentExpected = 'Test calendar'
        uidExpected = 'uid'
        fileName = 'example.ics'
        event.add('summary', contentExpected)
        event.add('dtstart', startExpected)
        event.add('dtend', endExpected)
        event['uid'] = uidExpected

        # the calendar gets written with UTC dates
        self._icalendar.add_component(event)
        f = open(fileName, 'wb')
        f.write(self._icalendar.as_string())
        f.close()

        handle = open(fileName, 'r')
        self._calendar = eventcalendar.fromFile(handle)

        eventSets = self._calendar._eventSets
        self.assertEquals(len(eventSets), 1)
        events = eventSets.values()[0].getEvents()

        # FIXME: python-iCalendar seems to have a bug
        # the calendar write, and this assert, fails when in 'winter' time
        # see https://thomas.apestaart.org/thomas/trac/browser/tests/icalendar/
        # self.assertOneEventExpected(startExpected, endExpected)

        # FIXME: poking at internals
        eventSets = self._calendar._eventSets
        events = eventSets.values()[0].getEvents()
        self.assertEquals(events[0].content, contentExpected)
        self.assertEquals(events[0].uid, uidExpected)

    def testParseTimezones(self):
        # Create a calendar in Europe/Brussels timezone,
        # with an event starting at 1:00 on 26/10, and ending at 4:00 on 26/10
        # this event should be 4 hours long since there is a daylight
        # savings time switch from 3:00 to 2:00 during the night
        data = '''
BEGIN:VCALENDAR
PRODID:-//My calendar product//mxm.dk//
VERSION:2.0
BEGIN:VTIMEZONE
TZID:my_location
BEGIN:DAYLIGHT
TZOFFSETFROM:+0400
TZOFFSETTO:+0500
TZNAME:MOJITO
DTSTART:19700329T020000
RRULE:FREQ=YEARLY;BYMONTH=3;BYDAY=-1SU
END:DAYLIGHT
BEGIN:STANDARD
TZOFFSETFROM:+0500
TZOFFSETTO:+0400
TZNAME:TEA
DTSTART:19701025T030000
RRULE:FREQ=YEARLY;BYMONTH=10;BYDAY=-1SU
END:STANDARD
END:VTIMEZONE
BEGIN:VEVENT
DTSTART;TZID=my_location:20080926T010000
DTEND;TZID=my_location:20081126T040000
SUMMARY:4 hour event due to time zone
UID:uid
END:VEVENT
END:VCALENDAR
        '''
        ical = icalendar.Calendar.from_string(data)
        cal = eventcalendar.fromICalendar(ical)
        dateTime = datetime(2008, 9, 25, 19, 0, 0, tzinfo=UTC)
        points = cal.getPoints(dateTime, timedelta(weeks=15))
        point1 = points[0].dt
        point2 = points[1].dt
        self.failUnless(str(point1.tzinfo == 'my_location'))
        self.failUnless(point1.utcoffset() == timedelta(hours=5))
        self.failUnless(point1.dst() == timedelta(hours=1))
        self.failUnless(point1.tzname() == 'MOJITO')
        self.failUnless(str(point2.tzinfo == 'my_location'))
        self.failUnless(point2.utcoffset() == timedelta(hours=4))
        self.failUnless(point2.dst() == timedelta(hours=0))
        self.failUnless(point2.tzname() == 'TEA')


class FunctionsTest(testsuite.TestCase):

    def testToDateTime(self):
        self.failIf(eventcalendar._toDateTime(None))

        dateTime = datetime(2015, 4, 4, 8, 0, 0, tzinfo=UTC)
        self.assertEquals(dateTime, eventcalendar._toDateTime(dateTime))

        d = date(2015, 4, 4)
        dateTimeExpected = datetime(2015, 4, 4, 0, 0, 0,
            tzinfo=UTC)
        self.assertEquals(dateTimeExpected, eventcalendar._toDateTime(d))


class EventTest(testsuite.TestCase):

    def testSimple(self):
        """
        Test that the object contains the data. Very simple test.
        """
        now = _now()
        start = now - timedelta(hours=1)
        end = now + timedelta(minutes=1)
        rrules = ["FREQ=HOURLY;INTERVAL=2;COUNT=5", ]
        exdates = [now + timedelta(hours=2)]
        uid = 'uid'
        e = eventcalendar.Event(uid, start, end, 'foo', rrules=rrules,
            exdates=exdates)
        self.assertEquals(e.start, start)
        self.assertEquals(e.end, end)
        self.assertEquals(e.content, 'foo')
        self.assertEquals(e.rrules, ["FREQ=HOURLY;INTERVAL=2;COUNT=5", ])
        self.assertEquals(e.exdates, exdates)

    def testComparison(self):
        """
        Test the operators: < > ==
        """
        now = _now()
        hour = timedelta(hours=1)

        self.failUnless(
            eventcalendar.Event('uid', now, now + hour, 'foo') <
            eventcalendar.Event('uid', now + hour, now + 2 * hour, 'foo'))
        self.failUnless(
            eventcalendar.Event('uid', now, now + hour, 'foo') ==
            eventcalendar.Event('uid', now, now + hour, 'foo'))
        self.failUnless(
            eventcalendar.Event('uid', now + hour, now + 2 * hour, 'foo') >
            eventcalendar.Event('uid', now, now + hour, 'foo'))

    def testTimeZones(self):
        """
        Test that when no timezone given to the init parameters,
        the LOCAL timezone is added to them.
        """
        now = datetime.now()
        hour = timedelta(hours=1)
        self.assertEquals(now.tzinfo, None)
        start = now
        end = now + hour
        exdates = [start]
        event = eventcalendar.Event('uid', start, end, 'foo', exdates=exdates)
        self.assertEquals(event.start.tzinfo, UTC)
        self.assertEquals(event.start, start.replace(tzinfo=UTC))
        self.assertEquals(event.end.tzinfo, UTC)
        self.assertEquals(event.end, end.replace(tzinfo=UTC))
        self.assertEquals(event.exdates[0].tzinfo, UTC)
        self.assertEquals(event.exdates[0], exdates[0].replace(tzinfo=UTC))


class EventSetTestCase(testsuite.TestCase):

    def testRecurrenceOverMidnight(self):
        """
        Test weekly recurrence rules that starts on one day and spawns to
        the day after, even though they were not planned for the next day.
        """

        def yesterdayDayOfTheWeek(now):
            yesterday = now-timedelta(days=1)
            day = calendar.weekday(yesterday.year, yesterday.month,
                                   yesterday.day)
            return _dayOfTheWeek[day]

        now = datetime.now().replace(microsecond=0)
        start = now - timedelta(days=1) - timedelta(weeks=1)
        end = now + timedelta(hours=1) - timedelta(weeks=1)
        rrules = [
            "FREQ=WEEKLY;BYDAY=" + yesterdayDayOfTheWeek(now) + ";WKST=MO",
        ]
        uid = 'uid'
        content = 'content'
        event = eventcalendar.Event(uid, start, end, content, rrules=rrules)
        eventSet = eventcalendar.EventSet(uid)
        eventSet.addEvent(event)
        p = eventSet.getPoints(event.start + timedelta(weeks=1),
            event.end - event.start)
        self.assertEquals(p[0].dt,
            event.start + timedelta(weeks=1))
        self.assertEquals(p[0].which, 'start')
        self.assertEquals(p[1].dt,
            event.end + timedelta(weeks=1))
        self.assertEquals(p[1].which, 'end')

    def testExAsStartDateWithRecurrence(self):
        """
        Exception to a recurrence rule.
        """
        start = datetime(2007, 12, 22, 9, 0, 0, 0, LOCAL)
        end = datetime(2007, 12, 22, 11, 0, 0, 0, LOCAL)
        uid = 'uid'
        content = 'content'
        rrules = ["FREQ=DAILY;WKST=MO", ]
        exdate = start
        exdates = [exdate]
        event = eventcalendar.Event(uid, start, end, content,
            rrules=rrules, exdates=exdates)
        set = eventcalendar.EventSet(uid)
        set.addEvent(event)
        p = set.getPoints(start, end - start)
        self.failIf(p)

    def testExWithRecurrence(self):
        """
        Exception to a recurrence rule.
        """
        start = datetime(2007, 12, 22, 9, 0, 0, 0, LOCAL)
        end = datetime(2007, 12, 22, 11, 0, 0, 0, LOCAL)
        uid = 'uid'
        content = 'content'
        rrules = ["FREQ=DAILY;WKST=MO", ]
        exdate = datetime(2007, 12, 23, 9, 0, 0, 0, LOCAL)
        exdates = [exdate]
        event = eventcalendar.Event(uid, start, end, content,
            rrules=rrules, exdates=exdates)
        set = eventcalendar.EventSet(uid)
        set.addEvent(event)
        p = set.getPoints(start, end - start)
        self.assertEquals(p[0].dt, start)
        self.assertEquals(p[0].which, 'start')
        self.assertEquals(p[1].which, 'end')
        p = set.getPoints(exdate, timedelta(days=1))
        self.failIf(p)

    def testGetPointSingle(self):
        start = datetime(2007, 12, 22, 9, 0, 0, 0, LOCAL)
        end = datetime(2007, 12, 22, 11, 0, 0, 0, LOCAL)
        uid = 'uid'
        content = 'content'
        event = eventcalendar.Event(uid, start, end, content)
        set = eventcalendar.EventSet(uid)
        set.addEvent(event)
        p = set.getPoints(start, end - start)
        self.assertEquals(p[0].dt, start)
        self.assertEquals(p[1].dt, end)
        p = set.getPoints(start - timedelta(hours=1),
            timedelta(hours=3))
        self.assertEquals(p[0].dt, start)
        self.assertEquals(p[1].dt, end)
        p = set.getPoints(start + timedelta(minutes=30),
            timedelta(minutes=60))
        self.assertEquals(p[0].dt,
            start + timedelta(minutes=30))
        self.assertEquals(p[1].dt, end - timedelta(minutes=30))

    def testGetPointsRecur(self):
        start = datetime(2007, 12, 22, 9, 0, 0, 0, LOCAL)
        end = datetime(2007, 12, 22, 11, 0, 0, 0, LOCAL)
        uid = 'uid'
        content = 'content'
        rrules = ["FREQ=DAILY;WKST=MO", ]
        event = eventcalendar.Event(uid, start, end, content,
            rrules=rrules)
        set = eventcalendar.EventSet(uid)
        set.addEvent(event)
        p = set.getPoints(start, end - start)
        self.assertEquals(p[0].dt, start)
        self.assertEquals(p[0].which, 'start')
        self.assertEquals(p[1].which, 'end')
        p = set.getPoints(start + timedelta(days=2),
            end - start)
        self.assertEquals(p[0].dt, start + timedelta(days=2))
        self.assertEquals(p[0].which, 'start')
        self.assertEquals(p[1].which, 'end')
        p = set.getPoints(end, timedelta(days=1))
        self.assertEquals(len(p), 2)
        self.assertNotEquals(p[0].dt, end)

    def testGetPointsRecurUntil(self):
        start = datetime(2007, 12, 22, 9, 0, 0, 0, LOCAL)
        end = datetime(2007, 12, 22, 11, 0, 0, 0, LOCAL)
        event = eventcalendar.Event('uid', start, end, 'content',
            rrules=["FREQ=DAILY;UNTIL=20071224T073000Z;WKST=MO", ])
        set = eventcalendar.EventSet('uid')
        set.addEvent(event)
        p = set.getPoints(start, end - start)
        self.assertEquals(p[0].dt, start)
        self.assertEquals(p[0].which, 'start')
        self.assertEquals(p[1].which, 'end')
        p = set.getPoints(start, end - start + timedelta(days=4))
        self.assertEquals(len(p), 4)
        self.assertEquals(p[0].dt, start)
        self.assertEquals(p[0].which, 'start')
        self.assertEquals(p[3].dt, end + timedelta(days=1))
        self.assertEquals(p[3].which, 'end')
        p = set.getPoints(start + timedelta(hours=1),
            end - start + timedelta(hours=22))
        self.assertEquals(len(p), 4)
        self.assertEquals(p[0].dt, start + timedelta(hours=1))
        self.assertEquals(p[0].which, 'start')
        self.assertEquals(p[1].dt, start + timedelta(hours=2))
        self.assertEquals(p[1].which, 'end')
        self.assertEquals(p[3].dt,
            end + timedelta(days=1) - timedelta(hours=1))
        self.assertEquals(p[3].which, 'end')
        p = set.getPoints(start + timedelta(days=3),
            end - start)
        self.assertEquals(len(p), 0)


class iCalTestCase(testsuite.TestCase):

    def setUp(self):
        self._path = os.path.join(os.path.split(__file__)[0],
                                  'test-google.ics')
        handle = open(self._path, 'r')
        self._cal = icalendar.Calendar.from_string(handle.read())
        self._events = self._cal.walk('vevent')

    def testRecurrenceId(self):
        rid = self._events[0].get('RECURRENCE-ID')
        self.failUnless(rid)
        riddatetime = parser.parse(str(rid))
        self.failUnless(str(rid).endswith('Z'))
        start = self._events[1].decoded('dtstart')
        self.failUnless(start)
        if start.tzinfo is None:
            tzinfo = tz.gettz(
                self._events[1]['dtstart'].params['TZID'])
            start = datetime(start.year, start.month, start.day,
                start.hour, start.minute, start.second,
                start.microsecond, tzinfo)
        rrulestr = str(self._events[1].get('RRULE'))
        self.failUnless(rrulestr)
        r = rrule.rrulestr(rrulestr, dtstart=start)
        self.failUnless(riddatetime in r)

    def testGetPoints(self):
        start = datetime(2007, 12, 22, 9, 0, 0, 0, LOCAL)
        end = datetime(2007, 12, 22, 11, 0, 0, 0, LOCAL)
        eventSet1 = eventcalendar.EventSet('uid1')
        eventSet2 = eventcalendar.EventSet('uid2')
        event1 = eventcalendar.Event('uid1', start, end, 'content')
        eventSet1.addEvent(event1)
        event2 = eventcalendar.Event('uid2', start, end, 'content')
        eventSet2.addEvent(event2)
        rid = self._events[0].get('RECURRENCE-ID')
        self.failUnless(rid)
        riddatetime = parser.parse(str(rid))
        self.failUnless(str(rid).endswith('Z'))
        start = self._events[1].decoded('dtstart')
        self.failUnless(start)
        if start.tzinfo is None:
            tzinfo = tz.gettz(
                self._events[1]['dtstart'].params['TZID'])
            start = datetime(start.year, start.month, start.day,
                start.hour, start.minute, start.second,
                start.microsecond, tzinfo)
        rrulestr = str(self._events[1].get('RRULE'))
        self.failUnless(rrulestr)
        r = rrule.rrulestr(rrulestr, dtstart=start)
        self.failUnless(riddatetime in r)


class CalendarParserTestCase(testsuite.TestCase):

    def setUp(self):
        self._path = os.path.join(os.path.split(__file__)[0],
                                  'test-exdate.ics')

    def testExDate(self):
        TZMADRID = tz.gettz('Europe/Madrid')
        start = datetime(2007, 11, 1, 0, 0, 0, 0, TZMADRID)
        end = datetime(2008, 1, 1, 0, 0, 0, 0, TZMADRID)
        calendar = eventcalendar.fromFile(open(self._path, 'r'))
        sets = calendar._eventSets.values()
        self.assertEquals(len(sets), 1)
        set = sets[0]
        self.assertEquals(set.uid, 'b0s4akee4lbvdnbr1h925vl0i4@google.com')
        points = set.getPoints(start, end - start)
        self.assertEquals(len(points), 44)
        exdatetime = datetime(2007, 11, 12, 20, 0, 0, 0, TZMADRID)
        for p in points:
            self.assertNotEquals(p.dt, exdatetime)

    def testMultipleRRule(self):
        # FIXME: not implemented, so raises for now.  See 4.8.5.4

        data = '''
BEGIN:VCALENDAR
PRODID:-//My calendar product//mxm.dk//
VERSION:2.0
BEGIN:VEVENT
DTEND:20150404T070000Z
DTSTART:20150404T060000Z
RRULE:FREQ=WEEKLY;COUNT=5;INTERVAL=2
RRULE:FREQ=WEEKLY;COUNT=5;INTERVAL=3
SUMMARY:Test calendar
UID:uid
END:VEVENT
END:VCALENDAR
        '''
        ical = icalendar.Calendar.from_string(data)
        self.assertRaises(NotImplementedError,
            eventcalendar.fromICalendar, ical)

    def testExDate(self):
        # FIXME: already implemented, but lacking testcase

        data = '''
BEGIN:VCALENDAR
PRODID:-//My calendar product//mxm.dk//
VERSION:2.0
BEGIN:VEVENT
DTEND:20150404T070000Z
DTSTART:20150404T060000Z
RRULE:FREQ=WEEKLY;COUNT=5;INTERVAL=2
EXDATE:20150404T060000Z
SUMMARY:Test calendar
UID:uid
END:VEVENT
END:VCALENDAR
        '''
        ical = icalendar.Calendar.from_string(data)
        self.assertRaises(NotImplementedError,
            eventcalendar.fromICalendar, ical)
    testExDate.skip = "Implemented, but lacks testcase"

    def testDaylightSavingsChange(self):
        # Create a calendar in Europe/Brussels timezone,
        # with an event starting at 1:00 on 26/10, and ending at 4:00 on 26/10
        # this event should be 4 hours long since there is a daylight
        # savings time switch from 3:00 to 2:00 during the night
        data = '''
BEGIN:VCALENDAR
PRODID:-//My calendar product//mxm.dk//
VERSION:2.0
BEGIN:VTIMEZONE
TZID:Europe/Brussels
X-LIC-LOCATION:Europe/Brussels
BEGIN:DAYLIGHT
TZOFFSETFROM:+0100
TZOFFSETTO:+0200
TZNAME:CEST
DTSTART:19700329T020000
RRULE:FREQ=YEARLY;BYMONTH=3;BYDAY=-1SU
END:DAYLIGHT
BEGIN:STANDARD
TZOFFSETFROM:+0200
TZOFFSETTO:+0100
TZNAME:CET
DTSTART:19701025T030000
RRULE:FREQ=YEARLY;BYMONTH=10;BYDAY=-1SU
END:STANDARD
END:VTIMEZONE
BEGIN:VEVENT
DTSTART;TZID=Europe/Brussels:20081026T010000
DTEND;TZID=Europe/Brussels:20081026T040000
SUMMARY:4 hour event due to time zone
UID:uid
END:VEVENT
END:VCALENDAR
        '''
        ical = icalendar.Calendar.from_string(data)
        cal = eventcalendar.fromICalendar(ical)
        dateTime = datetime(2008, 10, 25, 23, 0, 0, tzinfo=UTC)
        points = cal.getPoints(dateTime,
            timedelta(hours=5))
        self.assertEquals(len(points), 2)
        delta = points[1].dt - points[0].dt
        self.assertEquals(delta, timedelta(hours=4))
