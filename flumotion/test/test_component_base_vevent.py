import calendar
from datetime import datetime, timedelta, tzinfo
from dateutil import rrule, tz, parser
import os

from icalendar import Calendar

from flumotion.common import testsuite
from flumotion.common.eventcalendar import parseCalendarFromFile
from flumotion.common.eventcalendar import Event, EventSet, LOCAL


def _now(tz=LOCAL):
    return datetime.now(tz)

dayOfTheWeek = ['MO', 'TU', 'WE', 'TH', 'FR', 'SA', 'SU']


class EventTest(testsuite.TestCase):

    def testSimple(self):
        """
        Test that the object contains the data. Very simple test.
        """
        now = _now()
        start = now - timedelta(hours=1)
        end = now + timedelta(minutes=1)
        recurr = "FREQ=HOURLY;INTERVAL=2;COUNT=5"
        exdates = [now + timedelta(hours=2)]
        uid = 'uid'
        e = Event(uid, start, end, 'foo', rrule = recurr, now=now,
                  exdates=exdates)
        self.assertEquals(e.start, start)
        self.assertEquals(e.end, end)
        self.assertEquals(e.content, 'foo')
        self.assertEquals(e.rrule, "FREQ=HOURLY;INTERVAL=2;COUNT=5")
        self.assertEquals(e.exdates, exdates)

    def testComparison(self):
        """
        Test the operators: < > ==
        """
        now = _now()
        hour = timedelta(hours=1)

        self.failUnless(Event('uid', now, now+hour, 'foo') <
                        Event('uid', now+hour, now+2*hour, 'foo'))
        self.failUnless(Event('uid', now, now+hour, 'foo') ==
                        Event('uid', now, now+hour, 'foo'))
        self.failUnless(Event('uid', now+hour, now+2*hour, 'foo') >
                        Event('uid', now, now+hour, 'foo'))

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
        event = Event('uid', start, end, 'foo', exdates = exdates)
        self.assertEquals(event.start.tzinfo, LOCAL)
        self.assertEquals(event.start, start.replace(tzinfo=LOCAL))
        self.assertEquals(event.end.tzinfo, LOCAL)
        self.assertEquals(event.end, end.replace(tzinfo=LOCAL))
        self.assertEquals(event.exdates[0].tzinfo, LOCAL)
        self.assertEquals(event.exdates[0], exdates[0].replace(tzinfo=LOCAL))


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
            return dayOfTheWeek[day]

        now = datetime.now().replace(microsecond=0)
        start = now - timedelta(days=1) - timedelta(weeks=1)
        end = now + timedelta(hours=1) - timedelta(weeks=1)
        rrule = "FREQ=WEEKLY;BYDAY="+yesterdayDayOfTheWeek(now)+";WKST=MO"
        uid = 'uid'
        content = 'content'
        event = Event(uid, start, end, content,
            rrule=rrule)
        eventSet = EventSet(uid)
        eventSet.addEvent(event)
        p = eventSet.getPoints(event.start+timedelta(weeks=1),
                          event.end+timedelta(weeks=1))
        self.assertEquals(p[0].timestamp, event.start + timedelta(weeks=1))
        self.assertEquals(p[0].which, 'start')
        self.assertEquals(p[1].timestamp, event.end + timedelta(weeks=1))
        self.assertEquals(p[1].which, 'end')

    def testExAsStartDateWithRecurrence(self):
        """
        Exception to a recurrence rule.
        """
        start = datetime(2007, 12, 22, 9, 0, 0, 0, LOCAL)
        end = datetime(2007, 12, 22, 11, 0, 0, 0, LOCAL)
        uid = 'uid'
        content = 'content'
        rrule = "FREQ=DAILY;WKST=MO"
        exdate = start
        exdates = [exdate]
        event = Event(uid, start, end, content,
            rrule=rrule, exdates=exdates)
        set = EventSet(uid)
        set.addEvent(event)
        p = set.getPoints(start, end)
        self.failIf(p)

    def testExWithRecurrence(self):
        """
        Exception to a recurrence rule.
        """
        start = datetime(2007, 12, 22, 9, 0, 0, 0, LOCAL)
        end = datetime(2007, 12, 22, 11, 0, 0, 0, LOCAL)
        uid = 'uid'
        content = 'content'
        rrule = "FREQ=DAILY;WKST=MO"
        exdate = datetime(2007, 12, 23, 9, 0, 0, 0, LOCAL)
        exdates = [exdate]
        event = Event(uid, start, end, content,
            rrule=rrule, exdates=exdates)
        set = EventSet(uid)
        set.addEvent(event)
        p = set.getPoints(start, end)
        self.assertEquals(p[0].timestamp, start)
        self.assertEquals(p[0].which, 'start')
        self.assertEquals(p[1].which, 'end')
        p = set.getPoints(exdate, exdate+timedelta(days=1))
        self.failIf(p)

    def testGetPointSingle(self):
        start = datetime(2007, 12, 22, 9, 0, 0, 0, LOCAL)
        end = datetime(2007, 12, 22, 11, 0, 0, 0, LOCAL)
        uid = 'uid'
        content = 'content'
        event = Event(uid, start, end, content)
        set = EventSet(uid)
        set.addEvent(event)
        p = set.getPoints(start, end)
        self.assertEquals(p[0].timestamp, start)
        self.assertEquals(p[1].timestamp, end)
        p = set.getPoints(start - timedelta(hours=1),
            end + timedelta(hours=1))
        self.assertEquals(p[0].timestamp, start)
        self.assertEquals(p[1].timestamp, end)
        p = set.getPoints(start + timedelta(minutes=30),
            end - timedelta(minutes=30))
        self.assertEquals(p[0].timestamp, start + timedelta(minutes=30))
        self.assertEquals(p[1].timestamp, end - timedelta(minutes=30))

    def testGetPointsRecur(self):
        start = datetime(2007, 12, 22, 9, 0, 0, 0, LOCAL)
        end = datetime(2007, 12, 22, 11, 0, 0, 0, LOCAL)
        uid = 'uid'
        content = 'content'
        rrule = "FREQ=DAILY;WKST=MO"
        event = Event(uid, start, end, content,
            rrule=rrule)
        set = EventSet(uid)
        set.addEvent(event)
        p = set.getPoints(start, end)
        self.assertEquals(p[0].timestamp, start)
        self.assertEquals(p[0].which, 'start')
        self.assertEquals(p[1].which, 'end')
        p = set.getPoints(start + timedelta(days=2), end + timedelta(days=2))
        self.assertEquals(p[0].timestamp, start + timedelta(days=2))
        self.assertEquals(p[0].which, 'start')
        self.assertEquals(p[1].which, 'end')
        p = set.getPoints(end, end + timedelta(days=1))
        self.assertEquals(len(p), 2)
        self.assertNotEquals(p[0].timestamp, end)

    def testGetPointsRecurUntil(self):
        start = datetime(2007, 12, 22, 9, 0, 0, 0, LOCAL)
        end = datetime(2007, 12, 22, 11, 0, 0, 0, LOCAL)
        event = Event('uid', start, end, 'content',
            rrule="FREQ=DAILY;UNTIL=20071224T073000Z;WKST=MO")
        set = EventSet('uid')
        set.addEvent(event)
        p = set.getPoints(start, end)
        self.assertEquals(p[0].timestamp, start)
        self.assertEquals(p[0].which, 'start')
        self.assertEquals(p[1].which, 'end')
        p = set.getPoints(start, end + timedelta(days=4))
        self.assertEquals(len(p), 4)
        self.assertEquals(p[0].timestamp, start)
        self.assertEquals(p[0].which, 'start')
        self.assertEquals(p[3].timestamp, end + timedelta(days=1))
        self.assertEquals(p[3].which, 'end')
        p = set.getPoints(start + timedelta(hours=1),
            end + timedelta(days=1) - timedelta(hours=1))
        self.assertEquals(len(p), 4)
        self.assertEquals(p[0].timestamp, start + timedelta(hours=1))
        self.assertEquals(p[0].which, 'start')
        self.assertEquals(p[1].timestamp, start + timedelta(hours=2))
        self.assertEquals(p[1].which, 'end')
        self.assertEquals(p[3].timestamp,
            end + timedelta(days=1) - timedelta(hours=1))
        self.assertEquals(p[3].which, 'end')
        p = set.getPoints(start + timedelta(days=3), end + timedelta(days=3))
        self.assertEquals(len(p), 0)


class iCalTestCase(testsuite.TestCase):

    def setUp(self):
        self._path = os.path.join(os.path.split(__file__)[0],
                                  'test-google.ics')
        self._cal = Calendar.from_string(open(self._path, 'r').read())
        self._events = self._cal.walk('vevent')

    def testRecurrenceId(self):
        rid = self._events[0].get('RECURRENCE-ID')
        self.failUnless(rid)
        riddatetime = parser.parse(str(rid))
        self.failUnless(str(rid).endswith('Z'))
        start = self._events[1].decoded('dtstart')
        self.failUnless(start)
        if start.tzinfo is None:
            tzinfo = tz.gettz(self._events[1]['dtstart'].params['TZID'])
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
        eventSet1 = EventSet('uid1')
        eventSet2 = EventSet('uid2')
        event1 = Event('uid1', start, end, 'content')
        eventSet1.addEvent(event1)
        event2 = Event('uid2', start, end, 'content')
        eventSet2.addEvent(event2)
        rid = self._events[0].get('RECURRENCE-ID')
        self.failUnless(rid)
        riddatetime = parser.parse(str(rid))
        self.failUnless(str(rid).endswith('Z'))
        start = self._events[1].decoded('dtstart')
        self.failUnless(start)
        if start.tzinfo is None:
            tzinfo = tz.gettz(self._events[1]['dtstart'].params['TZID'])
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
        sets = parseCalendarFromFile(open(self._path, 'r'))
        self.assertEquals(len(sets), 1)
        set = sets[0]
        self.assertEquals(set.uid, 'b0s4akee4lbvdnbr1h925vl0i4@google.com')
        points = set.getPoints(start, end)
        self.assertEquals(len(points), 44)
        exdatetime = datetime(2007, 11, 12, 20, 0, 0, 0, TZMADRID)
        for p in points:
            self.assertNotEquals(p.timestamp, exdatetime)
