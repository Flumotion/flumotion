# -*- Mode: Python -*-
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
# Streaming Server license may use this file in accordance with the
# Flumotion Advanced Streaming Server Commercial License Agreement.
# See "LICENSE.Flumotion" in the source distribution for more information.

# Headers in this file shall remain intact.

import errno
import os
import time
from datetime import datetime

import gobject
import gst
import time

from twisted.internet import reactor

from flumotion.component import feedcomponent
from flumotion.common import log, gstreamer, pygobject, messages, errors
from flumotion.common import documentation
from flumotion.common.format import strftime
from flumotion.common.i18n import N_, gettexter
from flumotion.common.mimetypes import mimeTypeToExtention
from flumotion.common.pygobject import gsignal
# proxy import
from flumotion.component.component import moods

__all__ = ['Disker']
__version__ = "$Rev$"
T_ = gettexter()

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

HAS_ICALENDAR = False
HAS_DATEUTIL = False

try:
    from icalendar import Calendar
    HAS_ICALENDAR = True
except ImportError:
    pass
try:
    from dateutil import rrule
    HAS_DATEUTIL = True
except ImportError:
    pass

HAS_ICAL = HAS_ICALENDAR and HAS_DATEUTIL


class DiskerMedium(feedcomponent.FeedComponentMedium):
    # called when admin ui wants to stop recording. call changeFilename to
    # restart

    def remote_stopRecording(self):
        self.comp.stop_recording()

    # called when admin ui wants to change filename (this starts recording if
    # the disker isn't currently writing to disk)

    def remote_changeFilename(self, filenameTemplate=None):
        self.comp.change_filename(filenameTemplate)

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

    def init(self):
        self.uiState.addKey('filename', None)
        self.uiState.addKey('recording', False)
        self.uiState.addKey('can-schedule', HAS_ICAL)

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
        elif rotateType == 'time':
            self.setTimeRotate(properties['time'])
        # FIXME: should add a way of saying "do first cycle at this time"

        return self.pipe_template

    def setTimeRotate(self, time):
        """
        @param time: duration of file (in seconds)
        """
        reactor.callLater(time, self._rotateTimeCallback, time)

    def setSizeRotate(self, size):
        """
        @param size: size of file (in bytes)
        """
        reactor.callLater(5, self._rotateSizeCallback, size)

    def _rotateTimeCallback(self, time):
        self.change_filename()

        # Add a new one
        reactor.callLater(time, self._rotateTimeCallback, time)

    def _rotateSizeCallback(self, size):
        if not self.location:
            self.warning('Cannot rotate file, no file location set')
        else:
            if os.stat(self.location).st_size > size:
                self.change_filename()

        # Add a new one
        reactor.callLater(5, self._rotateTimeCallback, size)

    def get_mime(self):
        if self.caps:
            return self.caps.get_structure(0).get_name()

    def get_content_type(self):
        mime = self.get_mime()
        if mime == 'multipart/x-mixed-replace':
            mime += ";boundary=ThisRandomString"
        return mime

    def change_filename(self, filenameTemplate=None, timeOrTuple=None):
        """
        @param filenameTemplate: strftime formatted string to decide filename
        @param timeOrTuple: a valid time to pass to strftime, defaulting
        to time.localtime(). A 9-tuple may be passed instead.
        """
        mime = self.get_mime()
        ext = mimeTypeToExtention(mime)

        self.stop_recording()

        sink = self.get_element('fdsink')
        if sink.get_state() == gst.STATE_NULL:
            sink.set_state(gst.STATE_READY)

        filename = ""
        if not filenameTemplate:
            filenameTemplate = self._defaultFilenameTemplate
        filename = "%s.%s" % (strftime(filenameTemplate,
            timeOrTuple or time.localtime()), ext)
        self.location = os.path.join(self.directory, filename)
        self.info("Changing filename to %s", self.location)
        try:
            self.file = open(self.location, 'a')
        except IOError, e:
            self.warning("Failed to open output file %s: %s",
                       self.location, log.getExceptionMessage(e))
            m = messages.Error(T_(N_(
                "Failed to open output file '%s' for writing. "
                "Check permissions on the file."), self.location))
            self.addMessage(m)
            return
        self._plug_recording_started(self.file, self.location)
        sink.emit('add', self.file.fileno())
        self.uiState.set('filename', self.location)
        self.uiState.set('recording', True)

        if self.symlink_to_current_recording:
            self.update_symlink(self.location,
                                self.symlink_to_current_recording)

    def update_symlink(self, src, dest):
        if not dest.startswith('/'):
            dest = os.path.join(self.directory, dest)
        self.debug("updating symbolic link %s to point to %s", src, dest)
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
                                       "%s. Check your permissions."
                                       % (dest, ))),
                                 debug=log.getExceptionMessage(e))
            self.addMessage(m)

    def stop_recording(self):
        sink = self.get_element('fdsink')
        if sink.get_state() == gst.STATE_NULL:
            sink.set_state(gst.STATE_READY)

        if self.file:
            self.file.flush()
            sink.emit('remove', self.file.fileno())
            self._plug_recording_stopped(self.file, self.location)
            self.file = None
            self.uiState.set('filename', None)
            self.uiState.set('recording', False)
            if self.symlink_to_last_recording:
                self.update_symlink(self.location,
                                    self.symlink_to_last_recording)

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
            reactor.callLater(0, self.change_filename,
                self._startFilenameTemplate)

    # callback for when a client is removed so we can figure out
    # errors

    def _client_removed_cb(self, element, arg0, client_status):
        # check if status is error
        if client_status == 4:
            reactor.callFromThread(self._client_error_cb)

    def _client_error_cb(self):
        self.file.close()
        self.file = None
        # make element sad
        self.setMood(moods.sad)
        messageId = "error-writing-%s" % self.location
        m = messages.Error(T_(N_(
            "Error writing to file %s.  Maybe disk is full." % (
            self.location))),
            mid=messageId, priority=40)
        self.addMessage(m)

    def configure_pipeline(self, pipeline, properties):
        self.debug('configure_pipeline for disker')
        self.symlink_to_last_recording = \
            properties.get('symlink-to-last-recording', None)
        self.symlink_to_current_recording = \
            properties.get('symlink-to-current-recording', None)
        self._recordAtStart = properties.get('start-recording', True)
        self._defaultFilenameTemplate = properties.get('filename',
            '%s.%%Y%%m%%d-%%H%%M%%S' % self.getName())
        self._startFilenameTemplate = self._defaultFilenameTemplate
        icalfn = properties.get('ical-schedule')
        if HAS_ICAL and icalfn:
            self.debug('Parsing iCalendar file %s' % icalfn)
            from flumotion.component.base import scheduler
            try:
                self.icalScheduler = scheduler.ICalScheduler(open(
                    icalfn, 'r'))
                self.icalScheduler.subscribe(self.eventStarted,
                    self.eventEnded)
                currentEvents = self.icalScheduler.getCurrentEvents()
                if currentEvents:
                    self.debug('Event %s is in progress, start recording' %
                        currentEvents[0].content)
                    self._startFilenameTemplate = currentEvents[0].content
                    self._recordAtStart = True
                else:
                    self.debug('No events in progress')
                    self._recordAtStart = False
            except ValueError:
                m = messages.Warning(T_(N_(
                    "Error parsing ical file %s, so not scheduling any"
                    " events." % icalfn)), mid="error-parsing-ical")
                self.addMessage(m)

        elif icalfn:

            def missingModule(moduleName):
                m = messages.Error(T_(N_(
                    "An iCal file has been specified for scheduling, "
                    "but the '%s' module is not installed.\n"), moduleName),
                    mid='error-python-%s' % moduleName)
                documentation.messageAddPythonInstall(m, moduleName)
                self.debug(m)
                self.addMessage(m)

            if not HAS_ICALENDAR:
                missingModule('icalendar')
            if not HAS_DATEUTIL:
                missingModule('dateutil')

        sink = self.get_element('fdsink')
        sink.get_pad('sink').connect('notify::caps', self._notify_caps_cb)
        # connect to client-removed so we can detect errors in file writing
        sink.connect('client-removed', self._client_removed_cb)

        # set event probe if we should react to video mark events
        react_to_marks = properties.get('react-to-stream-markers', False)
        if react_to_marks:
            pfx = properties.get('stream-marker-filename-prefix', '%03d.')
            self._marker_prefix = pfx
            sink.get_pad('sink').add_event_probe(self._markers_event_probe)

    def eventStarted(self, event):
        self.debug('starting recording of %s', event.content)
        self.change_filename(event.content, event.currentStart.timetuple())

    def eventEnded(self, event):
        self.debug('ending recording of %s', event.content)
        self.stop_recording()

    def parse_ical(self, icsStr):
        if HAS_ICAL:
            cal = Calendar.from_string(icsStr)
            if self.icalScheduler:
                events = self.icalScheduler.parseCalendar(cal)
                if events:
                    self.icalScheduler.addEvents(events)
                else:
                    self.warning("No events found in the ical string")
        else:
            self.warning("Cannot parse ICAL; neccesary modules not installed")

    def _plug_recording_started(self, file, location):
        socket = 'flumotion.component.consumers.disker.disker_plug.DiskerPlug'
        # make sure plugs are configured with our socket, see #732
        if socket not in self.plugs:
            return
        for plug in self.plugs[socket]:
            self.debug('invoking recording_started on '
                       'plug %r on socket %s', plug, socket)
            plug.recording_started(file, location)

    def _plug_recording_stopped(self, file, location):
        socket = 'flumotion.component.consumers.disker.disker_plug.DiskerPlug'
        # make sure plugs are configured with our socket, see #732
        if socket not in self.plugs:
            return
        for plug in self.plugs[socket]:
            self.debug('invoking recording_stopped on '
                       'plug %r on socket %s', plug, socket)
            plug.recording_stopped(file, location)

    def _markers_event_probe(self, element, event):
        if event.type == gst.EVENT_CUSTOM_DOWNSTREAM:
            evt_struct = event.get_structure()
            if evt_struct.get_name() == 'FluStreamMark':
                if evt_struct['action'] == 'start':
                    self._on_marker_start(evt_struct['prog_id'])
                elif evt_struct['action'] == 'stop':
                    self._on_marker_stop()
        return True

    def _on_marker_stop(self):
        self.stop_recording()

    def _on_marker_start(self, data):
        tmpl = self._defaultFilenameTemplate
        if self._marker_prefix:
            try:
                tmpl = '%s%s' % (self._marker_prefix % data,
                                 self._defaultFilenameTemplate)
            except TypeError, err:
                m = messages.Warning(T_(N_('Failed expanding filename prefix: '
                                           '%r <-- %r.'),
                                        self._marker_prefix, data),
                                     mid='expand-marker-prefix')
                self.addMessage(m)
                self.warning('Failed expanding filename prefix: '
                             '%r <-- %r; %r' %
                             (self._marker_prefix, data, err))
        self.change_filename(tmpl)
