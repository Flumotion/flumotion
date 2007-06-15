# -*- Mode: Python -*-
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


import time
from datetime import datetime, timedelta, tzinfo

from twisted.internet import reactor

from flumotion.common import log, avltree
from flumotion.component.base import watcher


# A class capturing the platform's idea of local time, from the
# documentation of datetime.tzinfo.
class LocalTimezone(tzinfo):
    STDOFFSET = timedelta(seconds=-time.timezone)
    if time.daylight:
        DSTOFFSET = timedelta(seconds=-time.altzone)
    else:
        DSTOFFSET = STDOFFSET
    DSTDIFF = DSTOFFSET - STDOFFSET
    ZERO = timedelta(0)

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


def now(tz=LOCAL):
    return datetime.now(tz)


class Event(log.Loggable):
    """
    I am an event. I have a start and stop time and a "content" that can
    be anything. I can recur.
    """

    def __init__(self, start, end, content, recur=None, now=None):
        self.debug('new event, content=%r, start=%r, end=%r', content,
                   start, end)

        if recur:
            from dateutil import rrule
            if now is None:
                now = datetime.now(LOCAL)
            if end.tzinfo is None:
                end = datetime(end.year, end.month, end.day, end.hour, 
                    end.minute, end.second, end.microsecond, LOCAL)
            endRecurRule = rrule.rrulestr(recur, dtstart=end) 
            if start.tzinfo is None:
                start = datetime(start.year, start.month, start.day, 
                    start.hour, start.minute, start.second, 
                    start.microsecond, LOCAL)
            startRecurRule = rrule.rrulestr(recur, dtstart=start)

            if end < now:
                end = endRecurRule.after(now)
                start = startRecurRule.before(end)
                self.debug("adjusting start and end times to %r, %r",
                           start, end)

        if not start.tzinfo:
            self.info('event starting at %r does not have timezone '
                      'info; using local time zone', start)
            start = start.replace(tzinfo=LOCAL)
        if not end.tzinfo:
            self.info('event ending at %r does not have timezone '
                      'info; using local time zone', end)
            end = end.replace(tzinfo=LOCAL)

        self.start = start
        self.end = end
        self.content = content
        self.recur = recur

    def reschedule(self, now=None):
        if self.recur:
            return Event(self.start, self.end, self.content, self.recur,
                         now)
        else:
            return None

    def toTuple(self):
        return self.start, self.end, self.content, self.recur

    def __repr__(self):
        return '<Event %r>' % (self.toTuple(),)

    def __lt__(self, other):
        return self.toTuple() < other.toTuple()

    def __gt__(self, other):
        return self.toTuple() > other.toTuple()

    def __eq__(self, other):
        return self.toTuple() == other.toTuple()


class EventStore(avltree.AVLTree, log.Loggable):
    def __init__(self, events):
        avltree.AVLTree.__init__(self)
        for event in events:
            self.insert(event)

    def insert(self, event):
        try:
            avltree.AVLTree.insert(self, event)
            return True
        except ValueError:
            self.warning('an identical event to %r already exists in '
                         'store', event)
            return False


class Scheduler(log.Loggable):
    """
    I keep track of upcoming events.
    
    I can provide notifications when events stop and start, and maintain
    a set of current events.
    """

    def __init__(self):
        self.current = []
        self._delayedCall = None
        self._subscribeId = 0
        self.subscribers = {}
        self.replaceEvents([])

    def addEvent(self, start, end, content, recur=None, now=None):
        """Add a new event to the scheduler.

        @param start: wall-clock time of event start
        @type  start: datetime
        @param   end: wall-clock time of event end
        @type    end: datetime
        @param content: content of this event
        @type  content: str
        @param recur: recurrence rule
        @type  recur: str

        @returns: an Event that can later be passed to removeEvent, if
        so desired. The event will be removed or rescheduled
        automatically when it stops.
        """
        if now is None:
            now = datetime.now(LOCAL)
        event = Event(start, end, content, recur, now)
        if event.end < now:
            self.warning('attempted to schedule event in the past: %r',
                         event)
        else:
            if self.events.insert(event):
                if event.start < now:
                    self._eventStarted(event)
                self._reschedule()
        return event

    def removeEvent(self, event):
        """Remove an event from the scheduler.

        @param event: an event, as returned from addEvent()
        @type  event: Event
        """
        currentEvent = event.reschedule() or event
        self.events.delete(currentEvent)
        if currentEvent in self.current:
            self._eventStopped(currentEvent)
        self._reschedule()

    def getCurrentEvents(self):
        return [e.content for e in self.current]

    def addEvents(self, events):
        """
        Add a new list of events to the schedule.

        @param events: the new events
        @type  events: a new set of events
        """
        now = datetime.now()
        for event in events:
            if event.end > now:
                if self.events.insert(event):
                    if event.start < now:
                        self._eventStarted(event)
        if events:
            self._reschedule()

    def replaceEvents(self, events):
        """Replace the set of events in the scheduler.

        This function is different than simply removing all events then
        adding new ones, because it tries to avoid spurious
        stopped/start notifications.

        @param events: the new events
        @type  events: a sequence of Event
        """
        now = datetime.now(LOCAL)
        self.events = EventStore(events)
        current = []
        for event in self.events:
            if now < event.start:
                break
            elif event.end < now:
                # yay functional trees: we don't modify the iterator
                self.events.delete(event)
            else:
                current.append(event)
        for event in self.current[:]:
            if event not in current:
                self._eventStopped(event)
        for event in current:
            if event not in self.current:
                self._eventStarted(event)
        assert self.current == current
        self._reschedule()
        
    def subscribe(self, eventStarted, eventStopped):
        """Subscribe to event happenings in the scheduler.

        @param eventStarted: Function that will be called when an event
        starts.
        @type eventStarted: Event -> None
        @param eventStopped: Function that will be called when an event
        stops.
        @type eventStopped: Event -> None

        @returns: A subscription ID that can later be passed to
        unsubscribe().
        """
        sid = self._subscribeId
        self._subscribeId += 1
        self.subscribers[sid] = (eventStarted, eventStopped)
        return sid

    def unsubscribe(self, id):
        """Unsubscribe from event happenings in the scheduler.

        @param id: Subscription ID received from subscribe()
        """
        del self.subscribers[id]

    def _eventStarted(self, event):
        self.current.append(event)
        for started, _ in self.subscribers.values():
            started(event)

    def _eventStopped(self, event):
        self.current.remove(event)
        for _, stopped in self.subscribers.values():
            stopped(event)

    def _reschedule(self):
        def _getNextStart():
            for event in self.events:
                if event not in self.current:
                    return event
            return None

        def _getNextStop():
            t = None
            e = None
            for event in self.current:
                if not t or event.end < t:
                    t = event.end
                    e = event
            return e

        def doStart(e):
            self._eventStarted(e)
            self._reschedule()
            
        def doStop(e):
            self._eventStopped(e)
            self.events.delete(e)
            new = e.reschedule()
            if new:
                self.events.insert(new)
            self._reschedule()
            
        if self._delayedCall:
            if self._delayedCall.active():
                self._delayedCall.cancel()
            self._delayedCall = None

        start = _getNextStart()
        stop = _getNextStop()
        now = datetime.now(LOCAL)

        def toSeconds(td):
            return max(td.days*24*3600 + td.seconds + td.microseconds/1e6, 0)

        if start and (not stop or start.start < stop.end):
            dc = reactor.callLater(toSeconds(start.start - now),
                                   doStart, start)
        elif stop:
            dc = reactor.callLater(toSeconds(stop.end - now),
                                   doStop, stop)
        else:
            dc = None

        self._delayedCall = dc


class ICalScheduler(Scheduler):
    """
    I am a scheduler that takes its data from an ical file.
    """

    def __init__(self, fileObj):
        from icalendar import Calendar

        Scheduler.__init__(self)

        def parseCalendarFromFile(f):
            cal = Calendar.from_string(f.read())
            events = self.parseCalendar(cal)
            self.replaceEvents(events)
        parseCalendarFromFile(fileObj)

        if hasattr(fileObj, 'name'):
            def fileChanged(f):
                parseCalendarFromFile(open(f,'r'))
            self.watcher = watcher.FilesWatcher([fileObj.name])
            self.watcher.subscribe(fileChanged=fileChanged)
            self.watcher.start()

    def parseCalendar(self, cal):
        """
        Take a Calendar object and return a list of
        Event objects.

        @param cal: The calendar to "parse"
        @type  cal: icalendar.Calendar
        @rtype List of {flumotion.component.base.scheduler.Event}
        """
        events = []
        for event in cal.walk('vevent'):
            try:
                start = event.decoded('dtstart', None)
                end = event.decoded('dtend', None)
                summary = event.decoded('summary', None)
                recur = event.get('rrule', None)
                if start and end:
                    self.debug("start %r tzname %s end %r recur %r", start, 
                        start.tzname(), end, recur)
                    if recur:
                        e = Event(start, end, summary, recur.ical())
                    else:
                        e = Event(start, end, summary)
                    events.append(e)
                else:
                    self.warning('ical has event without start or end: '
                                 '%r', event)
            except Exception:
                self.warning("could not parse ical event %r", event)
        return events
