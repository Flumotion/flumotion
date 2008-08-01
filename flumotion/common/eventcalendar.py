# -*- Mode: Python; test-case-name:
#                flumotion.test.test_component_base_scheduler -*-
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
# Streaming Server license and using this file together with a Flumotion
# Advanced Streaming Server may only use this file in accordance with the
# Flumotion Advanced Streaming Server Commercial License Agreement.
# See "LICENSE.Flumotion" in the source distribution for more information.

# Headers in this file shall remain intact.

import datetime
import time

from icalendar import Calendar
from dateutil import rrule, tz, parser

from flumotion.extern.log.log import Loggable


class LocalTimezone(datetime.tzinfo):
    STDOFFSET = datetime.timedelta(seconds=-time.timezone)
    if time.daylight:
        DSTOFFSET = datetime.timedelta(seconds=-time.altzone)
    else:
        DSTOFFSET = STDOFFSET
    DSTDIFF = DSTOFFSET - STDOFFSET
    ZERO = datetime.timedelta(0)

    def utcoffset(self, dt):
        if self._isdst(dt):
            return self.DSTOFFSET
        else:
            return self.STDOFFSET

    def dst(self, dt):
        if self._isdst(dt):
            return self.DSTDIFF
        else:
            return self.ZERO

    def tzname(self, dt):
        return time.tzname[self._isdst(dt)]

    def _isdst(self, dt):
        tt = (dt.year, dt.month, dt.day,
              dt.hour, dt.minute, dt.second,
              dt.weekday(), 0, -1)
        return time.localtime(time.mktime(tt)).tm_isdst > 0
LOCAL = LocalTimezone()


class Point(Loggable):
    """
    I represent a start or an end point linked to an event instance
    of an event.
    """

    def __init__(self, eventInstance, which, timestamp):
        """
        @param eventInstance: An instance of an event.
        @type  eventInstance: EventInstance
        @param which: 'start' or 'end'
        @type  which: str
        @param timestamp: Timestamp of this point. It will
                          be used when comparing Points.
        @type  timestamp: datetime
        """
        self.which = which
        self.timestamp = timestamp
        self.eventInstance = eventInstance

    def __repr__(self):
        return "Point '%s' at %r for %r" % (
            self.which, self.timestamp, self.event)

    def __cmp__(self, other):
        # compare based on timestamp
        return cmp(self.timestamp, other.timestamp)


class EventInstance(Loggable):
    """
    I represent one event instance of an event.
    """

    def __init__(self, event, start, end):
        """
        @type  event: L{Event}
        @type  start:  L{datetime.datetime}
        @type  end:   L{datetime.datetime}
        """
        self.event = event
        self.start = start
        self.end = end
        #this is for recurrence events so we keep track of the
        #original start and end but also the current ones
        self.currentStart = start
        self.currentEnd = end

    def getPoints(self):
        """
        Get a list of start and end points.
        @rtype: L{Point}
        """
        ret = []

        ret.append(Point(self, 'start', self.start))
        ret.append(Point(self, 'end', self.end))

        return ret


def toDateTime(d):
    """
    If d is date, convert it to datetime.
    @type  d: It can be anything, even None. However, it will convert only if
     it is an event instance of date.
    @return: If d was an event instance of date, it returns the equivalent
     datetime.Otherwise, it returns d.
    """
    if isinstance(d, datetime.date) and not isinstance(d, datetime.datetime):
        return datetime.datetime(d.year, d.month, d.day, tzinfo=LOCAL)
    return d


class Event(Loggable):
    """
    I represent a EVENT entry in a calendar for our purposes.
    I can have recurrence.
    I can be scheduled between a start time and an end time,
    returning a list of start and end points.
    I can have exception dates.
    """

    def __init__(self, uid, start, end, content, rrule=None,
        recurrenceid=None, exdates=None, now=None):
        """
        @param uid:        identifier of the event.
        @type  uid:        str
        @param start:      start time of the event.
        @type  start:      L{datetime.datetime}
        @param end:       end time of the event.
        @type  end:       L{datetime.datetime}
        @param content:    label to describe the content
        @type  content:    str
        @param rrule:      a RRULE string
        @type  rrule:      str
        @param recurrenceid: a RECURRENCE-ID string. It is used on
                            recurrence events.
        @type  recurrenceid: str
        @param exdates:     list of exceptions. It is commonly used with
                            recurrence events.
        @type  exdates:     list of L{datetime.datetime} or None
        """
        if not now:
            now = datetime.datetime.now(LOCAL)
        self.end = self.__addTimeZone(end, LOCAL)
        self.start = self.__addTimeZone(start, LOCAL)
        self.content = content
        self.uid = uid
        self.rrule = rrule
        self.recurrenceid = recurrenceid
        if exdates:
            self.exdates = []
            for exdate in exdates:
                exdate = self.__addTimeZone(exdate, LOCAL)
                self.exdates.append(exdate)
        else:
            self.exdates = None
        self.now = now
        #this is for recurrence events so we keep track of the
        #original start and end but also the current ones
        self.currentStart = start
        self.currentEnd = end

    def __addTimeZone(self, dateTime, now):
        if dateTime.tzinfo is not None:
            return dateTime
        return datetime.datetime(dateTime.year, dateTime.month, dateTime.day,
                        dateTime.hour, dateTime.minute, dateTime.second,
                        dateTime.microsecond, now)

    def __repr__(self):
        return "<Event %r >" % (self.toTuple())

    def toTuple(self):
        return (self.uid, self.start, self.end, self.content, self.rrule,
                self.exdates)

    def __lt__(self, other):
        return self.toTuple() < other.toTuple()

    def __gt__(self, other):
        return self.toTuple() > other.toTuple()

    def __eq__(self, other):
        return self.toTuple() == other.toTuple()

    def __ne__(self, other):
        return not self.__eq__(other)


class EventSet(Loggable):
    """
    I represent a set of EVENT entries in a calendar sharing the same uid.
    I can have recurrence.
    I can be scheduled between a start time and an end time,
    returning a list of start and end points in UTC.
    I can have exception dates.
    """

    def __init__(self, uid):
        """
        @param uid:      the uid shared among the events on this set
        @type  uid:      str
        """
        self.uid = uid
        self._events = []

    def __repr__(self):
        return "<EventSet for uid %r >" % (
            self.uid)

    def addEvent(self, event):
        """
        Add an event to the set. The event must have the same uid as the set.
        """
        if self.uid != event.uid:
            self.debug("my uid %s does not match Event uid %s",
                       self.uid, event.uid)
            return
        self._events.append(event)

    def removeEvent(self, event):
        """
        Remove and event from the set.
        """
        if self.uid != event.uid:
            self.debug("my uid %s does not match Event uid %s",
                       self.uid, event.uid)
        self._events.remove(event)

    def getPoints(self, start, end):
        """
        Get an ordered list of start and end points between the given start
        and end for this set of Events.
        @param start:    The start point.
        @type start:     datetime
        @param end:     The end point
        @type end:      datetime
        """
        points = []

        eventInstances = self._getEventInstances(start, end)
        for i in eventInstances:
            points.extend(i.getPoints())
        points.sort()

        return points

    def _getEventInstances(self, start, end):
        # get all instances between the given dates

        eventInstances = []

        recurring = None

        # first, find the event with the rrule if there is any
        for v in self._events:
            if v.rrule:
                if recurring:
                    self.debug("Cannot have two RRULE EVENTs with UID %s",
                               self.uid)
                    return []
                recurring = v

        # now, find all instances between the two given times
        if recurring:
            eventInstances = self._getEventInstancesRecur(
                recurring, start, end)

        # now, find all events with a RECURRENCE-ID pointing to an instance,
        # and replace with the new instance
        for v in self._events:
            # skip the main event
            if v.rrule:
                continue

            if v.recurrenceid:
                recurDateTime = parser.parse(v.recurrenceid.ical())

                # Remove recurrent instance(s) that start at this recurrenceid
                for i in eventInstances[:]:
                    if i.start == recurDateTime:
                        eventInstances.remove(i)
                        break


            i = self._getEventInstanceSingle(v, start, end)
            if i:
                eventInstances.append(i)

        # fix all incidences that lie partly outside of the range
        # to be in the range
        for i in eventInstances[:]:
            if i.start < start:
                i.start = start
                if start >= i.end:
                    eventInstances.remove(i)
            if i.end > end:
                i.end = end

        return eventInstances

    def _getEventInstanceSingle(self, event, start, end):
        # is this event within the range asked for ?
        #print self, start, self.end
        if start > event.end:
            return None
        if end < event.start:
            return None

        startTime = max(event.start, start)
        endTime = min(event.end, end)

        return EventInstance(event, startTime, endTime)

    def _getEventInstancesRecur(self, event, start, end):
        # get all event instances for this recurring event that fall between
        # the given start and end

        ret = []

        # don't calculate endPoint based on end recurrence rule, because
        # if the next one after a start point is past UNTIL then the rrule
        # returns None
        delta = event.end - event.start

        startRecurRule = rrule.rrulestr(event.rrule, dtstart=event.start)

        for startTime in startRecurRule:
            # ignore everything stopping before our start time
            if startTime + delta < start:
                continue

            # stop looping if it's past the requested end time
            if startTime >= end:
                break

            # skip if it's on our list of exceptions
            if event.exdates:
                if startTime in event.exdates:
                    continue

            endTime = startTime + delta

            i = EventInstance(event, startTime, endTime)

            ret.append(i)

        return ret

    def getEvents(self):
        """
        Return the list of events
        @rtype: L{Event}
        """
        return self._events


def parseCalendar(cal):
    """
    Take a Calendar object and return a list of
    EventSet objects.

    @param cal:   The calendar to "parse"
    @type  cal:   icalendar.Calendar

    @rtype: list of {EventSet}
    """
    events = []

    def vDDDToDatetime(v):
        """
        Convert a vDDDType to a datetime, respecting timezones
        @param v: the time to convert
        @type v:  vDDDType

        """
        dt = toDateTime(v.dt)
        if dt.tzinfo is None:
            tzinfo = tz.gettz(v.params['TZID'])
            dt = datetime.datetime(dt.year, dt.month, dt.day,
                dt.hour, dt.minute, dt.second,
                dt.microsecond, tzinfo)
        return dt

    for event in cal.walk('vevent'):
        # extract to function ?
        start = vDDDToDatetime(event.get('dtstart', None))
        end = vDDDToDatetime(event.get('dtend', None))
        summary = event.decoded('SUMMARY', None)
        uid = event['UID']
        recur = event.get('RRULE', None)
        recurrenceid = event.get('RECURRENCE-ID', None)
        exdates = event.get('EXDATE', [])
        # When there is only one exdate, we don't get a list, but the
        # single exdate. Bad API
        if not isinstance(exdates, list):
            exdates = [exdates, ]

        # this is a list of icalendar.propvDDDTypes on which we can call
        # .dt() or .ical()
        exdates = [vDDDToDatetime(i) for i in exdates]

        # FIXME: we're not handling EXDATE at all here

        #if not start:
        #    raise AssertionError, "event %r does not have start" % event
        #if not end:
        #    raise AssertionError, "event %r does not have end" % event
        e = Event(uid, start, end, summary,
            recur and recur.ical() or None, recurrenceid, exdates)

        events.append(e)
    eventSets = {} # uid -> VEventSet
    for event in events:
        if not event.uid in eventSets.keys():
            eventSets[event.uid] = EventSet(event.uid)

        eventSets[event.uid].addEvent(event)
    return eventSets.values()


def parseCalendarFromFile(file):
    """
    Parse a given file into EventSets.

    @type  file:  file object

    @rtype: list of {EventSet}
    """
    data = file.read()
    cal = Calendar.from_string(data)
    file.close()
    return parseCalendar(cal)
