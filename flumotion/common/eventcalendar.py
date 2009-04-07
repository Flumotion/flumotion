# -*- Mode:Python; test-case-name:flumotion.test.test_common_eventcalendar -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# Flumotion - a streaming media server
# Copyright (C) 2004,2005,2006,2007,2008 Fluendo, S.L. (www.fluendo.com).
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

HAS_ICALENDAR = False
try:
    import icalendar
    HAS_ICALENDAR = True
except ImportError:
    pass

# for documentation on dateutil, see http://labix.org/python-dateutil
HAS_DATEUTIL = False
try:
    from dateutil import rrule, tz, parser
    HAS_DATEUTIL = True
except ImportError:
    pass

from flumotion.extern.log import log

"""
Implementation of a calendar that can inform about events beginning and
ending, as well as active event instances at a given time.

This uses iCalendar as defined in
http://www.ietf.org/rfc/rfc2445.txt

The users of this module should check if it has both HAS_ICALENDAR
and HAS_DATEUTIL properties and if any of them is False, they should
withhold from further using the module.
"""


def _toDateTime(d):
    """
    If d is a L{datetime.date}, convert it to L{datetime.datetime}.

    @type  d: anything

    @rtype:   L{datetime.datetime} or anything
    @returns: The equivalent datetime.datetime if d is a datetime.date;
              d if not
    """
    if isinstance(d, datetime.date) and not isinstance(d, datetime.datetime):
        return datetime.datetime(d.year, d.month, d.day, tzinfo=UTC)
    return d


class LocalTimezone(datetime.tzinfo):
    """A tzinfo class representing the system's idea of the local timezone"""
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

# A UTC class; see datetime.tzinfo documentation


class UTCTimezone(datetime.tzinfo):
    """A tzinfo class representing UTC"""
    ZERO = datetime.timedelta(0)

    def utcoffset(self, dt):
        return self.ZERO

    def tzname(self, dt):
        return "UTC"

    def dst(self, dt):
        return self.ZERO
UTC = UTCTimezone()


class Point(log.Loggable):
    """
    I represent a start or an end point linked to an event instance
    of an event.

    @type  eventInstance: L{EventInstance}
    @type  which:         str
    @type  dt:            L{datetime.datetime}
    """

    def __init__(self, eventInstance, which, dt):
        """
        @param eventInstance: An instance of an event.
        @type  eventInstance: L{EventInstance}
        @param which:         'start' or 'end'
        @type  which:         str
        @param dt:            Timestamp of this point. It will
                              be used when comparing Points.
        @type  dt:            L{datetime.datetime}
        """
        self.which = which
        self.dt = dt
        self.eventInstance = eventInstance

    def __repr__(self):
        return "Point '%s' at %r for %r" % (
            self.which, self.dt, self.eventInstance)

    def __cmp__(self, other):
        # compare based on dt, then end before start
        # relies on alphabetic order of end before start
        return cmp(self.dt, other.dt) \
            or cmp(self.which, other.which)


class EventInstance(log.Loggable):
    """
    I represent one event instance of an event.

    @type  event: L{Event}
    @type  start: L{datetime.datetime}
    @type  end:   L{datetime.datetime}
    """

    def __init__(self, event, start, end):
        """
        @type  event: L{Event}
        @type  start: L{datetime.datetime}
        @type  end:   L{datetime.datetime}
        """
        self.event = event
        self.start = start
        self.end = end

    def getPoints(self):
        """
        Get a list of start and end points.

        @rtype: list of L{Point}
        """
        ret = []

        ret.append(Point(self, 'start', self.start))
        ret.append(Point(self, 'end', self.end))

        return ret

    def __eq__(self, other):
        return self.start == other.start and self.end == other.end and \
            self.event == other.event

    def __ne__(self, other):
        return not self.__eq__(other)


class Event(log.Loggable):
    """
    I represent a VEVENT entry in a calendar for our purposes.
    I can have recurrence.
    I can be scheduled between a start time and an end time,
    returning a list of start and end points.
    I can have exception dates.
    """

    def __init__(self, uid, start, end, content, rrules=None,
        recurrenceid=None, exdates=None):
        """
        @param uid:          identifier of the event
        @type  uid:          str
        @param start:        start time of the event
        @type  start:        L{datetime.datetime}
        @param end:          end time of the event
        @type  end:          L{datetime.datetime}
        @param content:      label to describe the content
        @type  content:      unicode
        @param rrules:       a list of RRULE string
        @type  rrules:       list of str
        @param recurrenceid: a RECURRENCE-ID string, used with
                             recurrence events
        @type  recurrenceid: str
        @param exdates:      list of exceptions to the recurrence rule
        @type  exdates:      list of L{datetime.datetime} or None
        """
        self.start = self._ensureTimeZone(start)
        self.end = self._ensureTimeZone(end)
        self.content = content
        self.uid = uid
        self.rrules = rrules
        if rrules and len(rrules) > 1:
            raise NotImplementedError(
                "Events with multiple RRULE are not yet supported")
        self.recurrenceid = recurrenceid
        if exdates:
            self.exdates = []
            for exdate in exdates:
                exdate = self._ensureTimeZone(exdate)
                self.exdates.append(exdate)
        else:
            self.exdates = None

    def _ensureTimeZone(self, dateTime, tz=UTC):
        # add timezone information if it is not specified for some reason
        if dateTime.tzinfo:
            return dateTime

        return datetime.datetime(dateTime.year, dateTime.month, dateTime.day,
                        dateTime.hour, dateTime.minute, dateTime.second,
                        dateTime.microsecond, tz)

    def __repr__(self):
        return "<Event %r >" % (self.toTuple(), )

    def toTuple(self):
        return (self.uid, self.start, self.end, self.content, self.rrules,
                self.exdates)

    # FIXME: these are only here so the rrdmon stuff can use Event instances
    # in an avltree

    def __lt__(self, other):
        return self.toTuple() < other.toTuple()

    def __gt__(self, other):
        return self.toTuple() > other.toTuple()

    # FIXME: but these should be kept, so that events with different id
    # but same properties are the same

    def __eq__(self, other):
        return self.toTuple() == other.toTuple()

    def __ne__(self, other):
        return not self.__eq__(other)


class EventSet(log.Loggable):
    """
    I represent a set of VEVENT entries in a calendar sharing the same uid.
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

        @param event: the event to add.
        @type  event: L{Event}
        """
        assert self.uid == event.uid, \
            "my uid %s does not match Event uid %s" % (self.uid, event.uid)
        assert event not in self._events, "event %r already in set %r" % (
            event, self._events)

        self._events.append(event)

    def removeEvent(self, event):
        """
        Remove an event from the set.

        @param event: the event to add.
        @type  event: L{Event}
        """
        assert self.uid == event.uid, \
            "my uid %s does not match Event uid %s" % (self.uid, event.uid)
        self._events.remove(event)

    def getPoints(self, start=None, delta=None, clip=True):
        """
        Get an ordered list of start and end points from the given start
        point, with the given delta, in this set of Events.

        start defaults to now.
        delta defaults to 0, effectively returning all points at this time.
        the returned list includes the extremes (start and start + delta)

        @param start: the start time
        @type  start: L{datetime.datetime}
        @param delta: the delta
        @type  delta: L{datetime.timedelta}
        @param clip:  whether to clip all event instances to the given
                      start and end
        """
        if start is None:
            start = datetime.datetime.now(UTC)

        if delta is None:
            delta = datetime.timedelta(seconds=0)

        points = []

        eventInstances = self._getEventInstances(start, start + delta, clip)
        for i in eventInstances:
            for p in i.getPoints():
                if p.dt >= start and p.dt <= start + delta:
                    points.append(p)
        points.sort()

        return points

    def _getRecurringEvent(self):
        recurring = None

        # get the event in the event set that is recurring, if any
        for v in self._events:
            if v.rrules:
                assert not recurring, \
                    "Cannot have two RRULE VEVENTs with UID %s" % self.uid
                recurring = v
            else:
                if len(self._events) > 1:
                    assert v.recurrenceid, \
                        "With multiple VEVENTs with UID %s, " \
                        "each VEVENT should either have a " \
                        "reccurrence rule or have a recurrence id" % self.uid

        return recurring

    def _getEventInstances(self, start, end, clip):
        # get all instances whose start and/or end fall between the given
        # datetimes
        # clips the event to the given start and end if asked for
        # FIXME: decide if clip is inclusive or exclusive; maybe compare
        # to dateutil's solution

        eventInstances = []

        recurring = self._getRecurringEvent()

        # find all instances between the two given times
        if recurring:
            eventInstances = self._getEventInstancesRecur(
                recurring, start, end)

        # an event that has a recurrence id overrides the instance of the
        # recurrence with a start time matching the recurrence id, so
        # throw it out
        for event in self._events:
            # skip the main event
            if event is recurring:
                continue

            if event.recurrenceid:
                recurDateTime = parser.parse(event.recurrenceid.ical())

                # Remove recurrent instance(s) that start at this recurrenceid
                for i in eventInstances[:]:
                    if i.start == recurDateTime:
                        eventInstances.remove(i)
                        break

            i = self._getEventInstanceSingle(event, start, end)
            if i:
                eventInstances.append(i)

        if clip:
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
        if start > event.end:
            return None
        if end < event.start:
            return None

        return EventInstance(event, event.start, event.end)

    def _getEventInstancesRecur(self, event, start, end):
        # get all event instances for this recurring event that start before
        # the given end time and end after the given start time.
        # The UNTIL value applies to the start of a recurring event,
        # not to the end.  So if you would calculate based on the end for the
        # recurrence rule, and there is a recurring instance that starts before
        # UNTIL but ends after UNTIL, it would not be taken into account.

        ret = []

        # don't calculate endPoint based on end recurrence rule, because
        # if the next one after a start point is past UNTIL then the rrule
        # returns None
        delta = event.end - event.start

        # FIXME: support multiple RRULE; see 4.8.5.4 Recurrence Rule
        r = None
        if event.rrules:
            r = event.rrules[0]
        startRecurRule = rrule.rrulestr(r, dtstart=event.start)

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

    def getActiveEventInstances(self, dt=None):
        """
        Get all event instances active at the given dt.

        @type  dt:     L{datetime.datetime}

        @rtype: list of L{EventInstance}
        """
        if not dt:
            dt = datetime.datetime.now(tz=UTC)

        result = []

        # handle recurrence events first
        recurring = self._getRecurringEvent()
        if recurring:
            # FIXME: support multiple RRULE; see 4.8.5.4 Recurrence Rule
            startRecurRule = rrule.rrulestr(recurring.rrules[0],
                dtstart=recurring.start)
            dtstart = startRecurRule.before(dt)

            if dtstart:
                skip = False
                # ignore if we have another event with this recurrence-id
                for event in self._events:
                    if event.recurrenceid:
                        r = parser.parse(event.recurrenceid.ical())
                        if r == dtstart:
                            self.log(
                                'event %r, recurrenceid %s matches dtstart %r',
                                    event, event.recurrenceid, dtstart)
                            skip = True

                # add if it's not on our list of exceptions
                if recurring.exdates and dtstart in recurring.exdates:
                    self.log('recurring event %r has exdate for %r',
                        recurring, dtstart)
                    skip = True

                if not skip:
                    delta = recurring.end - recurring.start
                    dtend = dtstart + delta
                    if dtend >= dt:
                        # starts before our dt, and ends after, so add
                        result.append(EventInstance(recurring, dtstart, dtend))

        # handle all other events
        for event in self._events:
            if event is recurring:
                continue

            if event.start < dt < event.end:
                result.append(EventInstance(event, event.start, event.end))

        self.log('events active at %s: %r', str(dt), result)

        return result

    def getEvents(self):
        """
        Return the list of events.

        @rtype: list of L{Event}
        """
        return self._events


class Calendar(log.Loggable):
    """
    I represent a parsed iCalendar resource.
    I have a list of VEVENT sets from which I can be asked to schedule
    points marking the start or end of event instances.
    """

    logCategory = 'calendar'

    def __init__(self):
        self._eventSets = {} # uid -> EventSet

    def addEvent(self, event):
        """
        Add a parsed VEVENT definition.

        @type  event: L{Event}
        """
        uid = event.uid
        self.log("adding event %s with content %r", uid, event.content)
        if uid not in self._eventSets:
            self._eventSets[uid] = EventSet(uid)
        self._eventSets[uid].addEvent(event)

    def getPoints(self, start=None, delta=None):
        """
        Get all points from the given start time within the given delta.
        End Points will be ordered before Start Points with the same time.

        All points have a dt in the timezone as specified in the calendar.

        start defaults to now.
        delta defaults to 0, effectively returning all points at this time.

        @type  start: L{datetime.datetime}
        @type  delta: L{datetime.timedelta}

        @rtype: list of L{Point}
        """
        result = []

        for eventSet in self._eventSets.values():
            points = eventSet.getPoints(start, delta=delta, clip=False)
            result.extend(points)

        result.sort()

        return result

    def getActiveEventInstances(self, when=None):
        """
        Get a list of active event instances at the given time.

        @param when: the time to check; defaults to right now
        @type  when: L{datetime.datetime}

        @rtype: list of L{EventInstance}
        """
        result = []

        if not when:
            when = datetime.datetime.now(UTC)

        for eventSet in self._eventSets.values():
            result.extend(eventSet.getActiveEventInstances(when))

        self.debug('%d active event instances at %s', len(result), str(when))
        return result


def fromICalendar(iCalendar):
    """
    Parse an icalendar Calendar object into our Calendar object.

    @param iCalendar: The calendar to parse
    @type  iCalendar: L{icalendar.Calendar}

    @rtype: L{Calendar}
    """
    calendar = Calendar()

    def vDDDToDatetime(v):
        """
        Convert a vDDDType to a datetime, respecting timezones.

        @param v: the time to convert
        @type  v: L{icalendar.prop.vDDDTypes}

        """
        dt = _toDateTime(v.dt)
        if dt.tzinfo is None:
            # We might have a "floating" DATE-TIME value here, in
            # which case we will not have a TZID parameter; see
            # 4.3.5, FORM #3
            # Using None as the parameter for tz.gettz will create a
            # tzinfo object representing local time, which is the
            # Right Thing
            tzinfo = tz.gettz(v.params.get('TZID', None))
            dt = datetime.datetime(dt.year, dt.month, dt.day,
                dt.hour, dt.minute, dt.second,
                dt.microsecond, tzinfo)
        return dt

    for event in iCalendar.walk('vevent'):
        # extract to function ?

        # DTSTART is REQUIRED in VEVENT; see 4.8.2.4
        start = vDDDToDatetime(event.get('dtstart'))
        # DTEND is optional; see 4.8.2.3
        end = vDDDToDatetime(event.get('dtend', None))
        # FIXME: this implementation does not yet handle DURATION, which
        # is an alternative to DTEND

        # an event without DURATION or DTEND is defined to not consume any
        # time; see 6; so we skip it
        if not end:
            continue

        if end == start:
            continue

        assert end >= start, "end %r should not be before start %r" % (
            end, start)

        summary = event.decoded('SUMMARY', None)
        uid = event['UID']
        # When there is only one rrule, we don't get a list, but the
        # single rrule Bad API
        recur = event.get('RRULE', [])
        if not isinstance(recur, list):
            recur = [recur, ]
        recur = [r.ical() for r in recur]

        recurrenceid = event.get('RECURRENCE-ID', None)
        exdates = event.get('EXDATE', [])
        # When there is only one exdate, we don't get a list, but the
        # single exdate. Bad API
        if not isinstance(exdates, list):
            exdates = [exdates, ]

        # this is a list of icalendar.propvDDDTypes on which we can call
        # .dt() or .ical()
        exdates = [vDDDToDatetime(i) for i in exdates]

        if event.get('RDATE'):
            raise NotImplementedError("We don't handle RDATE yet")

        if event.get('EXRULE'):
            raise NotImplementedError("We don't handle EXRULE yet")

        #if not start:
        #    raise AssertionError, "event %r does not have start" % event
        #if not end:
        #    raise AssertionError, "event %r does not have end" % event
        e = Event(uid, start, end, summary, recur, recurrenceid, exdates)

        calendar.addEvent(e)

    return calendar


def fromFile(file):
    """
    Create a new calendar from an open file object.

    @type  file: file object

    @rtype: L{Calendar}
    """
    data = file.read()

    # FIXME Google calendar recently started introducing things like
    # CREATED:0000XXXXTXXXXXXZ, which means: created in year 0000
    # this breaks the icalendar parsing code. Guard against that.
    data = data.replace('\nCREATED:0000', '\nCREATED:2008')
    cal = icalendar.Calendar.from_string(data)
    return fromICalendar(cal)
