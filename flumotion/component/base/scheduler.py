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

import time
import datetime

from twisted.internet import reactor

from flumotion.common import log, eventcalendar
from flumotion.component.base import watcher

__version__ = "$Rev$"


def _timedeltaToSeconds(td):
    return max(td.days * 24 * 60 * 60 + td.seconds + td.microseconds / 1e6, 0)


class Scheduler(log.Loggable):
    """
    I provide notifications when events start and end.
    I use a L{eventcalendar.Calendar} for scheduling.

    @cvar windowSize: how much time to look ahead when scheduling
    @type windowSize: L{datetime.timedelta}
    """
    windowSize = datetime.timedelta(days=1)

    def __init__(self):
        self._delayedCall = None # tracks next call for scheduling
        self._subscribeId = 0    # counter fo unique sid's
        self._subscribers = {}   # sid -> tuple of callable
        self._nextStart = 0      # only used in testsuite
        self._calendar = None    # our currently active calendar

    ### public API

    def getCalendar(self):
        """
        Return the calendar used for scheduling.

        @rtype: L{eventcalendar.Calendar}
        """
        return self._calendar

    def setCalendar(self, calendar, when=None):
        """
        Set the given calendar to use for scheduling.

        This function will send start notifications for all new events that
        should currently be in progress, if they were not registered in
        the old calendar or if there was no old calendar.

        If the scheduler previously had a calendar, it will send end
        notifications for all events currently in progress that are not in the
        new calendar.

        @param calendar: the new calendar to set
        @type  calendar: L{eventcalendar.Calendar}
        @param when:     the time at which to consider the calendar to be set;
                         defaults to now
        @type  when:     L{datetime.datetime}
        """
        if not self._calendar:
            self.debug('Setting new calendar %r', calendar)
        else:
            self.debug('Replacing existing calendar %r with new %r',
                self._calendar, calendar)

        # we want to make sure we use the same when for getting old and new
        # instances if it wasn't specified
        if not when:
            when = datetime.datetime.now(eventcalendar.UTC)

        # FIXME: convert Content lists to dicts to speed things up
        # because they are used as a lookup inside loops
        oldInstances = []
        if self._calendar:
            oldInstances = self._calendar.getActiveEventInstances(when)
        oldInstancesContent = [i.event.content for i in oldInstances]

        newInstances = calendar.getActiveEventInstances(when)
        newInstancesContent = [i.event.content for i in newInstances]

        # we do comparison of instances by content, since, while the timing
        # information may have changed, if the content is still the same,
        # then the event is still considered 'active'
        self._calendar = calendar
        for instance in oldInstances:
            if instance.event.content not in newInstancesContent:
                self.debug(
                    'old active %r for %r not in new calendar, ending',
                    instance, instance.event.content)
                self._eventInstanceEnded(instance)

        for instance in newInstances:
            if instance.event.content not in oldInstancesContent:
                self.debug(
                    'new active %r for %r not in old calendar, starting',
                    instance, instance.event.content)
                self._eventInstanceStarted(instance)

        self._reschedule()

    def getPoints(self, when=None):
        """
        Get all points on this scheduler's event horizon.
        """
        if not when:
            when = datetime.datetime.now(eventcalendar.LOCAL)

        self.debug('getPoints at %s', str(when))
        earliest = when + self.windowSize

        points = self._calendar.getPoints(when, self.windowSize)

        self.debug('%d points in given windowsize %s',
            len(points), str(self.windowSize))

        return points

    def cleanup(self):
        """
        Clean up all resources used by this scheduler.

        This cancels all pending scheduling calls.
        """
        self._cancelScheduledCalls()

    ### subscription interface

    def subscribe(self, eventInstanceStarted, eventInstanceEnded):
        """
        Subscribe to event happenings in the scheduler.

        @param eventInstanceStarted: function that will be called when an
                                     event instance starts
        @type  eventInstanceStarted: function with signature L{EventInstance}
        @param eventInstanceEnded:   function that will be called when an
                                     event instance ends
        @type  eventInstanceEnded:   function with signature L{EventInstance}

        @rtype:   int
        @returns: A subscription ID that can later be passed to
                  unsubscribe().
        """
        sid = self._subscribeId
        self._subscribeId += 1
        self._subscribers[sid] = (eventInstanceStarted, eventInstanceEnded)
        return sid

    def unsubscribe(self, id):
        """
        Unsubscribe from event happenings in the scheduler.

        @type  id: int
        @param id: Subscription ID received from subscribe()
        """
        del self._subscribers[id]

    def _eventInstanceStarted(self, eventInstance):
        self.debug('notifying %d subscribers of start of instance %r',
            len(self._subscribers), eventInstance)
        for started, _ in self._subscribers.values():
            started(eventInstance)

    def _eventInstanceEnded(self, eventInstance):
        self.debug('notifying %d subscribers of end of instance %r',
            len(self._subscribers), eventInstance)
        for _, ended in self._subscribers.values():
            ended(eventInstance)

    ### private API

    def _reschedule(self):

        start = time.time()

        self.debug("reschedule events")
        self._cancelScheduledCalls()

        now = datetime.datetime.now(eventcalendar.LOCAL)

        def _getNextPoints():
            # get the next list of points in time that all start at the same
            # time
            self.debug('_getNextPoints at %s', str(now))
            result = []

            points = self.getPoints(now)

            if not points:
                return result

            earliest = points[0].dt
            for point in points:
                if point.dt > earliest:
                    break
                result.append(point)

            if result:
                self.debug('%d points at %s, first point is for %r',
                    len(result), str(result[0].dt),
                    result[0].eventInstance.event.content)

            return result

        def _handlePoints(points):
            for point in points:
                self.debug(
                    "handle %s event %r in %s at %s",
                    point.which,
                    point.eventInstance.event.content,
                    str(point.dt - now),
                    point.dt)
                if point.which == 'start':
                    self._eventInstanceStarted(point.eventInstance)
                elif point.which == 'end':
                    self._eventInstanceEnded(point.eventInstance)

            self._reschedule()

        points = _getNextPoints()

        if points:
            seconds = _timedeltaToSeconds(points[0].dt - now)
            self.debug(
                "schedule next point at %s in %.2f seconds",
                    str(points[0].dt), seconds)
            dc = reactor.callLater(seconds, _handlePoints, points)

        else:
            self.debug(
                "schedule rescheduling in %s", str(self.windowSize / 2))
            seconds = _timedeltaToSeconds(self.windowSize / 2)
            dc = reactor.callLater(seconds, self._reschedule)
        self._nextStart = seconds
        self._delayedCall = dc

        delta = time.time() - start
        if delta < 0.5:
            self.debug('_reschedule took %.3f seconds', delta)
        else:
            self.warning('Rescheduling took more than half a second')

    def _cancelScheduledCalls(self):
        if self._delayedCall:
            if self._delayedCall.active():
                self._delayedCall.cancel()
            self._delayedCall = None


class ICalScheduler(Scheduler):

    watcher = None

    # FIXME: having fileObj in the constructor causes events to be sent
    # before anything can subscribe
    # FIXME: this class should also be able to handle watching a URL
    # and downloading it when it changes

    def __init__(self, fileObj):
        """
        I am a scheduler that takes its data from an ical file and watches
        that file every timeout.

        @param fileObj: The fileObj. It must be already opened.
        @type  fileObj: file handle
        """
        Scheduler.__init__(self)

        self.watcher = None

        if not fileObj:
            return

        self._parseFromFile(fileObj)

        if hasattr(fileObj, 'name'):

            def fileChanged(filename):
                self.info("ics file %s changed", filename)
                try:
                    self._parseFromFile(open(filename, 'r'))
                except:
                    self.warning("error parsing ics file %s", filename)

            self.watcher = watcher.FilesWatcher([fileObj.name])
            fileObj.close()
            self.watcher.subscribe(fileChanged=fileChanged)
            self.watcher.start()

    def stopWatchingIcalFile(self):
        """
        Stop watching the ical file.
        """
        if self.watcher:
            self.watcher.stop()

    def cleanup(self):
        Scheduler.cleanup(self)
        self.stopWatchingIcalFile()

    def _parseFromFile(self, f):
        calendar = eventcalendar.fromFile(f)
        self.setCalendar(calendar)
