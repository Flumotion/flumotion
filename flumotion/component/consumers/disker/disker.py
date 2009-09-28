# -*- Mode: Python -*-
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
# Streaming Server license may use this file in accordance with the
# Flumotion Advanced Streaming Server Commercial License Agreement.
# See "LICENSE.Flumotion" in the source distribution for more information.

# Headers in this file shall remain intact.

import errno
import os
import time
import tempfile

import gobject
import gst

from twisted.internet import reactor
from zope.interface import implements

from flumotion.component import feedcomponent
from flumotion.common import log, gstreamer, pygobject, messages, errors
from flumotion.common import documentation, format
from flumotion.common import eventcalendar, poller
from flumotion.common.i18n import N_, gettexter
from flumotion.common.mimetypes import mimeTypeToExtention
from flumotion.common.pygobject import gsignal
from flumotion.twisted.flavors import IStateCacheableListener
# proxy import
from flumotion.component.component import moods

__all__ = ['Disker']
__version__ = "$Rev$"
T_ = gettexter()

# Disk Usage polling frequency
DISKPOLL_FREQ = 60

# Maximum number of information to store in the filelist
FILELIST_SIZE = 100

"""
Disker has a property 'ical-schedule'. This allows an ical file to be
specified in the config and have recordings scheduled based on events.
This file will be monitored for changes and events reloaded if this
happens.

The filename of a recording started from an ical file will be produced
via passing the ical event summary through strftime, so that an archive
can encode the date and time that it was begun.

The time that will be given to strftime will be given in the timezone of
the ical event. In practice this will either be UTC or the local time of
the machine running the disker, as the ical scheduler does not
understand arbitrary timezones.
"""


class DiskerMedium(feedcomponent.FeedComponentMedium):
    # called when admin ui wants to stop recording. call changeFilename to
    # restart

    def remote_stopRecording(self):
        self.comp.stopRecording()

    # called when admin ui wants to change filename (this starts recording if
    # the disker isn't currently writing to disk)

    def remote_changeFilename(self, filenameTemplate=None):
        self.comp.changeFilename(filenameTemplate)

    def remote_scheduleRecordings(self, icalData):
        icalFile = tempfile.TemporaryFile()
        icalFile.write(icalData)
        icalFile.seek(0)

        self.comp.stopRecording()

        self.comp.scheduleRecordings(icalFile)
        icalFile.close()

    # called when admin ui wants updated state (current filename info)

    def remote_notifyState(self):
        self.comp.update_ui_state()


class Disker(feedcomponent.ParseLaunchComponent, log.Loggable):
    componentMediumClass = DiskerMedium
    checkOffset = True
    pipe_template = 'multifdsink sync-method=1 name=fdsink mode=1 sync=false'
    file = None
    directory = None
    location = None
    caps = None
    last_tstamp = None

    _startFilenameTemplate = None # template to use when starting off recording
    _startTimeTuple = None        # time tuple of event when starting
    _rotateTimeDelayedCall = None
    _pollDiskDC = None            # _pollDisk delayed calls
    _symlinkToLastRecording = None
    _symlinkToCurrentRecording = None

    implements(IStateCacheableListener)

    ### BaseComponent methods

    def init(self):
        self._can_schedule = (eventcalendar.HAS_ICALENDAR and
                              eventcalendar.HAS_DATEUTIL)
        self.uiState.addKey('filename', None)
        self.uiState.addKey('recording', False)
        self.uiState.addKey('can-schedule', self._can_schedule)
        self.uiState.addKey('has-schedule', False)
        self.uiState.addKey('rotate-type', None)
        self.uiState.addKey('disk-free', None)
        # list of (dt (in UTC, without tzinfo), which, content)
        self.uiState.addListKey('next-points')
        self.uiState.addListKey('filelist')

        self._diskPoller = poller.Poller(self._pollDisk,
                                         DISKPOLL_FREQ,
                                         start=False)

    ### uiState observer triggers

    def observerAppend(self, observer, num):
        # PB may not have finished setting up its state and doing a
        # remoteCall immediately here may cause some problems to the other
        # side. For us to send the initial disk usage value with no
        # noticeable delay, we will do it in a callLater with a timeout
        # value of 0
        self.debug("observer has started watching us, starting disk polling")
        if not self._diskPoller.running and not self._pollDiskDC:
            self._pollDiskDC = reactor.callLater(0,
                                                 self._diskPoller.start,
                                                 immediately=True)
        # Start the BaseComponent pollers
        feedcomponent.ParseLaunchComponent.observerAppend(self, observer, num)

    def observerRemove(self, observer, num):
        if num == 0:
            # cancel delayed _pollDisk calls if there's any
            if self._pollDiskDC:
                self._pollDiskDC.cancel()
                self._pollDiskDC = None

            self.debug("no more observers left, shutting down disk polling")
            self._diskPoller.stop()
        # Stop the BaseComponent pollers
        feedcomponent.ParseLaunchComponent.observerRemove(self, observer, num)

    ### ParseLaunchComponent methods

    def get_pipeline_string(self, properties):
        directory = properties['directory']

        self.directory = directory

        self.fixRenamedProperties(properties, [('rotateType', 'rotate-type')])

        rotateType = properties.get('rotate-type', 'none')

        # validate rotate-type and size/time properties first
        if not rotateType in ['none', 'size', 'time']:
            m = messages.Error(T_(N_(
                "The configuration property 'rotate-type' should be set to "
                "'size', time', or 'none', not '%s'. "
                "Please fix the configuration."),
                    rotateType), mid='rotate-type')
            self.addMessage(m)
            raise errors.ComponentSetupHandledError()

        # size and time types need the property specified
        if rotateType in ['size', 'time']:
            if rotateType not in properties.keys():
                m = messages.Error(T_(N_(
                    "The configuration property '%s' should be set. "
                    "Please fix the configuration."),
                        rotateType), mid='rotate-type')
                self.addMessage(m)
                raise errors.ComponentSetupHandledError()

        # now act on the properties
        if rotateType == 'size':
            self.setSizeRotate(properties['size'])
            self.uiState.set('rotate-type',
                             'every %sB' % \
                             format.formatStorage(properties['size']))
        elif rotateType == 'time':
            self.setTimeRotate(properties['time'])
            self.uiState.set('rotate-type',
                             'every %s' % \
                             format.formatTime(properties['time']))
        else:
            self.uiState.set('rotate-type', 'disabled')
        # FIXME: should add a way of saying "do first cycle at this time"

        return self.pipe_template

    def configure_pipeline(self, pipeline, properties):
        self.debug('configure_pipeline for disker')
        self._symlinkToLastRecording = \
            properties.get('symlink-to-last-recording', None)
        self._symlinkToCurrentRecording = \
            properties.get('symlink-to-current-recording', None)
        self._recordAtStart = properties.get('start-recording', True)
        self._defaultFilenameTemplate = properties.get('filename',
            '%s.%%Y%%m%%d-%%H%%M%%S' % self.getName())
        self._startFilenameTemplate = self._defaultFilenameTemplate
        icalfn = properties.get('ical-schedule')
        if self._can_schedule and icalfn:
            self.scheduleRecordings(open(icalfn, 'r'))
        elif icalfn:
            # ical schedule is set, but self._can_schedule is False

            def missingModule(moduleName):
                m = messages.Error(T_(N_(
                    "An iCal file has been specified for scheduling, "
                    "but the '%s' module is not installed.\n"), moduleName),
                    mid='error-python-%s' % moduleName)
                documentation.messageAddPythonInstall(m, moduleName)
                self.debug(m)
                self.addMessage(m)

            if not eventcalendar.HAS_ICALENDAR:
                missingModule('icalendar')
            if not eventcalendar.HAS_DATEUTIL:
                missingModule('dateutil')
            # self._can_schedule is False, so one of the above surely happened
            raise errors.ComponentSetupHandledError()

        sink = self.get_element('fdsink')
        sink.get_pad('sink').connect('notify::caps', self._notify_caps_cb)
        # connect to client-removed so we can detect errors in file writing
        sink.connect('client-removed', self._client_removed_cb)

        # set event probe if we should react to video mark events
        react_to_marks = properties.get('react-to-stream-markers', False)
        if react_to_marks:
            pfx = properties.get('stream-marker-filename-prefix', '%03d.')
            self._markerPrefix = pfx
            sink.get_pad('sink').add_event_probe(self._markers_event_probe)

    ### our methods

    def _pollDisk(self):
        # Figure out the remaining disk space where the disker is saving
        # files to
        self._pollDiskDC = None
        s = None
        try:
            s = os.statvfs(self.directory)
        except Exception, e:
            self.debug('failed to figure out disk space: %s',
                       log.getExceptionMessage(e))

        if not s:
            free = None
        else:
            free = format.formatStorage(s.f_frsize * s.f_bavail)

        if self.uiState.get('disk-free') != free:
            self.debug("disk usage changed, reporting to observers")
            self.uiState.set('disk-free', free)

    def setTimeRotate(self, time):
        """
        @param time: duration of file (in seconds)
        """
        if self._rotateTimeDelayedCall:
            self._rotateTimeDelayedCall.cancel()
        self._rotateTimeDelayedCall = reactor.callLater(
            time, self._rotateTimeCallLater, time)

    def setSizeRotate(self, size):
        """
        @param size: size of file (in bytes)
        """
        reactor.callLater(5, self._rotateSizeCallLater, size)

    def _rotateTimeCallLater(self, time):
        self.changeFilename()

        # reschedule ourselves indefinitely
        self._rotateTimeDelayedCall = reactor.callLater(
            time, self._rotateTimeCallLater, time)

    def _rotateSizeCallLater(self, size):
        if not self.location:
            self.warning('Cannot rotate file, no file location set')
        else:
            if os.stat(self.location).st_size > size:
                self.changeFilename()

        # Add a new one
        reactor.callLater(5, self._rotateSizeCallLater, size)

    def getMime(self):
        if self.caps:
            return self.caps.get_structure(0).get_name()

    # FIXME: is this method used anywhere ?

    def get_content_type(self):
        mime = self.getMime()
        if mime == 'multipart/x-mixed-replace':
            mime += ";boundary=ThisRandomString"
        return mime

    def scheduleRecordings(self, icalFile):
        self.uiState.set('has-schedule', True)
        self.debug('Parsing iCalendar file %s' % icalFile)
        from flumotion.component.base import scheduler
        try:
            self.icalScheduler = scheduler.ICalScheduler(icalFile)
            self.icalScheduler.subscribe(self.eventInstanceStarted,
                self.eventInstanceEnded)
            # FIXME: this should be handled through the subscription
            # handlers; for that, we should subscribe before the calendar
            # gets added
            cal = self.icalScheduler.getCalendar()
            eventInstances = cal.getActiveEventInstances()
            if eventInstances:
                instance = eventInstances[0]
                content = instance.event.content
                self.info('Event %s is in progress, start recording' %
                    content)
                self._startFilenameTemplate = content
                self._startTimeTuple = instance.start.utctimetuple()
                self._recordAtStart = True
            else:
                self.info('No events in progress')
                self._recordAtStart = False
            self._updateNextPoints()
        except (ValueError, IndexError, KeyError), e:
            m = messages.Warning(T_(N_(
                "Error parsing ical file %s, so not scheduling any"
                " events." % icalFile)),
                debug=log.getExceptionMessage(e), mid="error-parsing-ical")
            self.addMessage(m)

    def changeFilename(self, filenameTemplate=None, timeTuple=None):
        """
        @param filenameTemplate: strftime format string to decide filename
        @param timeTuple:        a valid time tuple to pass to strftime,
                                 defaulting to time.localtime().
        """
        mime = self.getMime()
        ext = mimeTypeToExtention(mime)

        self.stopRecording()

        sink = self.get_element('fdsink')
        if sink.get_state() == gst.STATE_NULL:
            sink.set_state(gst.STATE_READY)

        filename = ""
        if not filenameTemplate:
            filenameTemplate = self._defaultFilenameTemplate
        filename = "%s.%s" % (format.strftime(filenameTemplate,
            timeTuple or time.localtime()), ext)
        self.location = os.path.join(self.directory, filename)

        # only overwrite existing files if it was last changed before the
        # start of this event; ie. if it is a recording of a previous event
        location = self.location
        i = 1
        while os.path.exists(location):
            mtimeTuple = time.gmtime(os.stat(location).st_mtime)
            if mtimeTuple <= timeTuple:
                self.info(
                    "Existing recording %s from previous event, overwriting",
                    location)
                break

            self.info(
                "Existing recording %s from current event, changing name",
                location)
            location = self.location + '.' + str(i)
            i += 1
        self.location = location

        self.info("Changing filename to %s", self.location)
        try:
            self.file = open(self.location, 'wb')
        except IOError, e:
            self.warning("Failed to open output file %s: %s",
                       self.location, log.getExceptionMessage(e))
            m = messages.Error(T_(N_(
                "Failed to open output file '%s' for writing. "
                "Check permissions on the file."), self.location))
            self.addMessage(m)
            return
        self._recordingStarted(self.file, self.location)
        sink.emit('add', self.file.fileno())
        self.last_tstamp = time.time()
        self.uiState.set('filename', self.location)
        self.uiState.set('recording', True)

        if self._symlinkToCurrentRecording:
            self._updateSymlink(self.location,
                                self._symlinkToCurrentRecording)

    def _updateSymlink(self, src, dest):
        if not dest.startswith('/'):
            dest = os.path.join(self.directory, dest)
        # this should read:
        # "updating symbolic link /tmp/current to point to /tmp/video-XXX.data"
        # hence the order of parameters should be dest, src
        self.debug("updating symbolic link %s to point to %s", dest, src)
        try:
            try:
                os.symlink(src, dest)
            except OSError, e:
                if e.errno == errno.EEXIST and os.path.islink(dest):
                    os.unlink(dest)
                    os.symlink(src, dest)
                else:
                    raise
        except Exception, e:
            self.info("Failed to update link %s: %s", dest,
                      log.getExceptionMessage(e))
            m = messages.Warning(T_(N_("Failed to update symbolic link "
                                 "'%s'. Check your permissions."), dest),
                                 debug=log.getExceptionMessage(e))
            self.addMessage(m)

    def stopRecording(self):
        sink = self.get_element('fdsink')
        if sink.get_state() == gst.STATE_NULL:
            sink.set_state(gst.STATE_READY)

        if self.file:
            self.file.flush()
            sink.emit('remove', self.file.fileno())
            self._recordingStopped(self.file, self.location)
            self.file = None
            self.uiState.set('filename', None)
            self.uiState.set('recording', False)
            try:
                size = format.formatStorage(os.stat(self.location).st_size)
            except EnvironmentError, e:
                # catch File not found, permission denied, disk problems
                size = "unknown"

            # Limit number of entries on filelist, remove the oldest entry
            fl = self.uiState.get('filelist', otherwise=[])
            if FILELIST_SIZE == len(fl):
                self.uiState.remove('filelist', fl[0])

            self.uiState.append('filelist', (self.last_tstamp,
                                             self.location,
                                             size))

            if self._symlinkToLastRecording:
                self._updateSymlink(self.location,
                                    self._symlinkToLastRecording)

    def _notify_caps_cb(self, pad, param):
        caps = pad.get_negotiated_caps()
        if caps == None:
            return

        caps_str = gstreamer.caps_repr(caps)
        self.debug('Got caps: %s' % caps_str)

        new = True
        if not self.caps == None:
            self.warning('Already had caps: %s, replacing' % caps_str)
            new = False

        self.debug('Storing caps: %s' % caps_str)
        self.caps = caps

        if new and self._recordAtStart:
            reactor.callLater(0, self.changeFilename,
                self._startFilenameTemplate, self._startTimeTuple)

    # multifdsink::client-removed

    def _client_removed_cb(self, element, arg0, client_status):
        # treat as error if we were removed because of GST_CLIENT_STATUS_ERROR
        # FIXME: can we use the symbol instead of a numeric constant ?
        if client_status == 4:
            # since we get called from the streaming thread, hand off handling
            # to the reactor's thread
            reactor.callFromThread(self._client_error_cb)

    def _client_error_cb(self):
        self.file.close()
        self.file = None

        self.setMood(moods.sad)
        messageId = "error-writing-%s" % self.location
        m = messages.Error(T_(N_(
            "Error writing to file '%s'."), self.location),
            mid=messageId, priority=40)
        self.addMessage(m)

    def eventInstanceStarted(self, eventInstance):
        self.debug('starting recording of %s', eventInstance.event.content)
        self.changeFilename(eventInstance.event.content,
            eventInstance.start.timetuple())
        self._updateNextPoints()

    def eventInstanceEnded(self, eventInstance):
        self.debug('ending recording of %s', eventInstance.event.content)
        self.stopRecording()
        self._updateNextPoints()

    def _updateNextPoints(self):
        # query the scheduler for what the next points are in its window
        # and set it on the UI state

        current = self.uiState.get('next-points')[:]
        points = self.icalScheduler.getPoints()
        new = []

        # twisted says 'Currently can't jelly datetime objects with tzinfo',
        # so convert all to UTC then remove tzinfo.

        def _utcAndStripTZ(dt):
            from flumotion.common import eventcalendar
            return dt.astimezone(eventcalendar.UTC).replace(tzinfo=None)

        for p in points:
            dtUTC = _utcAndStripTZ(p.dt)
            dtStart = p.eventInstance.start.replace(tzinfo=None)
            new.append((dtUTC, p.which,
                format.strftime(p.eventInstance.event.content,
                    dtStart.timetuple())))

        for t in current:
            if t not in new:
                self.debug('removing tuple %r from next-points', t)
                self.uiState.remove('next-points', t)

        for t in new:
            if t not in current:
                self.debug('appending tuple %r to next-points', t)
                self.uiState.append('next-points', t)

    def _recordingStarted(self, file, location):
        socket = 'flumotion.component.consumers.disker.disker_plug.DiskerPlug'
        # make sure plugs are configured with our socket, see #732
        if socket not in self.plugs:
            return
        for plug in self.plugs[socket]:
            self.debug('invoking recordingStarted on '
                       'plug %r on socket %s', plug, socket)
            plug.recordingStarted(file, location)

    def _recordingStopped(self, file, location):
        socket = 'flumotion.component.consumers.disker.disker_plug.DiskerPlug'
        # make sure plugs are configured with our socket, see #732
        if socket not in self.plugs:
            return
        for plug in self.plugs[socket]:
            self.debug('invoking recordingStopped on '
                       'plug %r on socket %s', plug, socket)
            plug.recordingStopped(file, location)

    ### marker methods

    def _markers_event_probe(self, element, event):
        if event.type == gst.EVENT_CUSTOM_DOWNSTREAM:
            evt_struct = event.get_structure()
            if evt_struct.get_name() == 'FluStreamMark':
                if evt_struct['action'] == 'start':
                    self._onMarkerStart(evt_struct['prog_id'])
                elif evt_struct['action'] == 'stop':
                    self._onMarkerStop()
        return True

    def _onMarkerStop(self):
        self.stopRecording()

    def _onMarkerStart(self, data):
        tmpl = self._defaultFilenameTemplate
        if self._markerPrefix:
            try:
                tmpl = '%s%s' % (self._markerPrefix % data,
                                 self._defaultFilenameTemplate)
            except TypeError, err:
                m = messages.Warning(T_(N_('Failed expanding filename prefix: '
                                           '%r <-- %r.'),
                                        self._markerPrefix, data),
                                     mid='expand-marker-prefix')
                self.addMessage(m)
                self.warning('Failed expanding filename prefix: '
                             '%r <-- %r; %r' %
                             (self._markerPrefix, data, err))
        self.changeFilename(tmpl)

    def do_stop(self):
        if self._pollDiskDC:
            self._pollDiskDC.cancel()
            self._pollDiskDC = None
        self._diskPoller.stop()
