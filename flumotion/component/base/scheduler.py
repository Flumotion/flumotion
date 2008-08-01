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

from datetime import datetime, timedelta

from twisted.internet import reactor

from flumotion.common import log
from flumotion.component.base import watcher
from flumotion.common.eventcalendar import parseCalendar, parseCalendarFromFile
from flumotion.common.eventcalendar import Event, LOCAL, EventSet

__version__ = "$Rev$"


class Scheduler(log.Loggable):
    """
    I keep track of upcoming events.

    I can provide notifications when events end and start, and maintain
    a set of current events.
    """
    windowSize = timedelta(days=1)

    def __init__(self):
        self._delayedCall = None
        self._subscribeId = 0
        self.subscribers = {}
        self._eventSets = {}
        self._nextStart = 0

    def _addEvent(self, event):
        self.debug("adding event %s", event.uid)
        uid = event.uid
        if uid not in self._eventSets:
            self._eventSets[uid] = EventSet(uid)
        self._eventSets[uid].addEvent(event)
        if event.start < event.now < event.end:
            self._eventStarted(event)

    def addEvent(self, uid, start, end, content, rrule=None, now=None,
                 exdates=None):
        """Add a new event to the scheduler

        @param uid:     uid of event
        @type  uid:     str
        @param start:   wall-clock time of event start
        @type  start:   datetime
        @param end:     wall-clock time of event end
        @type  end:     datetime
        @param content: content of this event
        @type  content: str
        @param rrule:   recurrence rule, either as a string parseable by
                        datetime.rrule.rrulestr or as a datetime.timedelta
        @type rrule:     None, str, or datetime.timedelta

        @returns:       an Event that can later be passed to removeEvent, if
                        so desired. The event will be removed or rescheduled
                        automatically when it ends.
        """

        if now is None:
            now = datetime.now(LOCAL)
        event = Event(uid, start, end, content, rrule=rrule, exdates=exdates,
                      now=now)
        if event.end < now and not rrule:
            self.warning('attempted to schedule event in the past: %r',
                         event)
            return event

        self._addEvent(event)
        self._reschedule()
        return event

    def removeEvent(self, event):
        """Remove an event from the scheduler.

        @param event: an event, as returned from addEvent()
        @type  event: Event
        """
        self._removeEvent(event)
        self._reschedule()

    def _removeEvent(self, event):
        uid = event.uid
        if uid not in self._eventSets:
            return
        current = self.getCurrentEvents()
        if event in current:
            self._eventEnded(event)
        self._eventSets[uid].removeEvent(event)

    def getCurrentEvents(self, now=None, windowSize=None):
        """Get a list of current events.
        @param now: Use now as localtime. If not set the local time is used.
        @type now: datetime
        @param windowSize: get events on this window. If not set, the returned
                            events will be on the class windowSize member.
        @type windowSize: timedelta

        @return: Events that are being run.
        @rtype: L{Event}
        """
        if now is None:
            now = datetime.now(LOCAL)
        if windowSize is None:
            windowSize = timedelta(seconds=0)
        current = []
        for eventSet in self._eventSets.values():
            points = eventSet.getPoints(now, now + windowSize)
            for point in points:
                event = point.eventInstance.event
                event.currentStart = point.eventInstance.currentStart
                event.currentEnd = point.eventInstance.currentEnd
                if not event in current:
                    current.append(event)
        return current

    def addEvents(self, events):
        """
        Add a new list of events to the schedule.

        @param events: the new events
        @type  events: list of Event
        """
        result = []
        for event in events:
            e = self._addEvent(event)
            result.append(e)
        self._reschedule()
        return result

    def replaceEvents(self, events, now=None):
        """Replace the set of events in the scheduler.

        This function is different than simply removing all events then
        adding new ones, because it tries to avoid spurious
        ended/started notifications.

        @param events: the new events
        @type  events: a sequence of Event
        """
        if now is None:
            now = datetime.now(LOCAL)
        currentEvents = self.getCurrentEvents()
        for _, eventSet in self._eventSets.iteritems():
            eventsToRemove = eventSet.getEvents()[:]
            for event in eventsToRemove:
                if event not in currentEvents:
                    self._removeEvent(event)
        for event in events:
            self.debug("adding event %r", event.uid)
            if event.start > now or event.rrule:
                self._addEvent(event)
            else:
                self.debug("event is a past event and it is not added")
        self._reschedule()

    def subscribe(self, eventStarted, eventEnded):
        """
        Subscribe to event happenings in the scheduler.

        @param eventStarted: function that will be called when an event starts
        @type  eventStarted: function taking L{Event}
        @param eventEnded:   function that will be called when an event ends
        @type  eventEnded:   function taking L{Event}

        @returns: A subscription ID that can later be passed to
                  unsubscribe().
        """
        sid = self._subscribeId
        self._subscribeId += 1
        self.subscribers[sid] = (eventStarted, eventEnded)
        return sid

    def unsubscribe(self, id):
        """Unsubscribe from event happenings in the scheduler.

        @param id: Subscription ID received from subscribe()
        """
        del self.subscribers[id]

    def _eventStarted(self, event):
        for started, _ in self.subscribers.values():
            started(event)

    def _eventEnded(self, event):
        for _, ended in self.subscribers.values():
            ended(event)

    def _reschedule(self):

        def _getNextEvent(now):
            earliest = now + self.windowSize
            which = None
            result = None
            for event in self.getCurrentEvents(now, self.windowSize):
                self.debug("current event %s", event.uid)
                if event.currentStart < earliest and event.currentStart > now:
                    earliest = event.currentStart
                    which = 'start'
                    result = event
                if event.currentEnd < earliest:
                    earliest = event.currentEnd
                    which = 'end'
                    result = event
            return result, which

        def doStart(e):
            self._eventStarted(e)
            self._reschedule()

        def doEnd(e):
            self._eventEnded(e)
            self._eventSets[e.uid].removeEvent(e)
            self._reschedule()

        self.debug("schedule events")
        self._cancelScheduledCalls()

        now = datetime.now(LOCAL)

        event, which = _getNextEvent(now)

        def toSeconds(td):
            return max(td.days*24*3600 + td.seconds + td.microseconds/1e6, 0)

        if event:
            if which == 'start':
                self.debug(
                    "schedule start event at %s",
                    str(event.currentStart - now))
                seconds = toSeconds(event.currentStart - now)
                dc = reactor.callLater(seconds, doStart, event)
            elif which == 'end':
                self.debug(
                    "schedule end event at %s",
                    str(event.currentEnd - now))
                seconds = toSeconds(event.currentEnd - now)
                dc = reactor.callLater(seconds, doEnd, event)
        else:
            self.debug(
                "schedule rescheduling at %s", str(self.windowSize))
            seconds = toSeconds(self.windowSize)
            dc = reactor.callLater(seconds, self._reschedule)
        self._nextStart = seconds
        self._delayedCall = dc

    def _cancelScheduledCalls(self):
        if self._delayedCall:
            if self._delayedCall.active():
                self._delayedCall.cancel()
            self._delayedCall = None

class ICalScheduler(Scheduler):

    def __init__(self, fileObj):
        """
        I am a scheduler that takes its data from an ical file and watches
        that file every timeout. Very important: only future events will
        be added, not past nor present.
        @param fileObj: The fileObj. It must be already opened.
        @type fileObj: open file.
        """
        Scheduler.__init__(self)
        if not fileObj:
            return

        def parseFromFile(f):
            eventSets = parseCalendarFromFile(f)
            self._setEventSets(eventSets)
        parseFromFile(fileObj)

        if hasattr(fileObj, 'name'):
            def fileChanged(f):
                self.debug("ics file changed")
                parseFromFile(open(f, 'r'))
        self.watcher = watcher.FilesWatcher([fileObj.name])
        self.watcher.subscribe(fileChanged=fileChanged)
        self.watcher.start()

    def _setEventSets(self, eventSets):
        events = []
        for eventSet in eventSets:
            self.debug("add eventset %s", eventSet.uid)
            events.extend(eventSet.getEvents())
        self.replaceEvents(events)

    def parseCalendar(self, calendar):
        eventSets = parseCalendar(calendar)
        self._setEventSets(eventSets)

    def stopWatchingIcalFile(self):
        """
        Stop watching the ical file.
        """
        self.watcher.stop()
