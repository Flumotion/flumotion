# -*- Mode: Python -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# Flumotion - a streaming media server
# Copyright (C) 2004,2005,2006 Fluendo, S.L. (www.fluendo.com).
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
from flumotion.common import log, gstreamer, pygobject, messages

# proxy import
from flumotion.component.component import moods
from flumotion.common.pygobject import gsignal

from flumotion.common.messages import N_
T_ = messages.gettexter('flumotion')

__all__ = ['Disker']

try:
    # icalendar and dateutil modules needed for scheduling recordings
    from icalendar import Calendar
    from dateutil import rrule
    HAS_ICAL = True
except:
    HAS_ICAL = False

class DiskerMedium(feedcomponent.FeedComponentMedium):
    # called when admin ui wants to stop recording. call changeFilename to
    # restart
    def remote_stopRecording(self):
        self.comp.stop_recording()

    # called when admin ui wants to change filename (this starts recording if
    # the disker isn't currently writing to disk)
    def remote_changeFilename(self, filenameTemplate=None):
        self.comp.change_filename(filenameTemplate)

    def remote_scheduleRecordings(self, ical):
        self.comp.parse_ical(ical)

    # called when admin ui wants updated state (current filename info)
    def remote_notifyState(self):
        self.comp.update_ui_state()

class Disker(feedcomponent.ParseLaunchComponent, log.Loggable):
    componentMediumClass = DiskerMedium
    pipe_template = 'multifdsink sync-method=1 name=fdsink mode=1 sync=false'
    file_fd = None
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

        rotateType = properties['rotateType']
        if rotateType == 'size':
            self.setSizeRotate(properties['size'])
        elif rotateType == 'time':
            self.setTimeRotate(properties['time'])

        return self.pipe_template

    def setTimeRotate(self, time):
        reactor.callLater(time, self._rotateTimeCallback, time)

    def setSizeRotate(self, size):
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
    
    def change_filename(self, filenameTemplate=None):
        """
        @param filenameTemplate: stftime formatted string to decide filename
        """
        self.debug("change_filename()")
        mime = self.get_mime()
        if mime == 'application/ogg':
            ext = 'ogg'
        elif mime == 'multipart/x-mixed-replace':
            ext = 'multipart'
        elif mime == 'audio/mpeg':
            ext = 'mp3'
        elif mime == 'video/x-msvideo':
            ext = 'avi'
        elif mime == 'video/x-ms-asf':
            ext = 'asf'
        elif mime == 'audio/x-flac':
            ext = 'flac'
        elif mime == 'audio/x-wav':
            ext = 'wav'
        elif mime == 'video/x-matroska':
            ext = 'mkv'
        elif mime == 'video/x-dv':
            ext = 'dv'
        else:
            ext = 'data'
        
        sink = self.get_element('fdsink')
        if sink.get_state() == gst.STATE_NULL:
            sink.set_state(gst.STATE_READY)

        if self.file_fd:
            self.file_fd.flush()
            sink.emit('remove', self.file_fd.fileno())
            self.file_fd = None
            if self.symlink_to_last_recording:
                self.update_symlink(self.location,
                                    self.symlink_to_last_recording)

        filename = ""
        if not filenameTemplate:
            date = time.strftime('%Y%m%d-%H%M%S', time.localtime())
            filename = '%s.%s.%s' % (self.getName(), date, ext)
        else:
            filename = "%s.%s" % (time.strftime(filenameTemplate,
                time.localtime()), ext)
        self.location = os.path.join(self.directory, filename)

        self.file_fd = open(self.location, 'a')
        sink.emit('add', self.file_fd.fileno())
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
                                       % (dest,))),
                                 debug=log.getExceptionMessage(e))
            self.state.append('messages', m)

    def stop_recording(self):
        sink = self.get_element('fdsink')
        if sink.get_state() == gst.STATE_NULL:
            sink.set_state(gst.STATE_READY)

        if self.file_fd:
            self.file_fd.flush()
            sink.emit('remove', self.file_fd.fileno())
            self.file_fd = None
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
            reactor.callLater(0, self.change_filename)

    # callback for when a client is removed so we can figure out
    # errors
    def _client_removed_cb(self, element, arg0, client_status):
        # check if status is error
        if client_status == 4:
            # close file descriptor
            self.file_fd.flush()
            # make element sad
            self.setMood(moods.sad)
            id = "error-writing-%s" % self.location
            m = messages.Error(T_(N_(
                "Error writing to file %s.  Maybe disk is full." % (
                    self.location))),
                id=id, priority=40)
            self.state.append('messages', m)

    def configure_pipeline(self, pipeline, properties):
        self.debug('configure_pipeline for disker')
        self.symlink_to_last_recording = \
            properties.get('symlink-to-last-recording', None)
        self.symlink_to_current_recording = \
            properties.get('symlink-to-current-recording', None)
        self._recordAtStart = properties.get('start-recording', True)
        icalfn = properties.get('ical-schedule')
        if icalfn:
            ical = open(icalfn, "rb").read()
            self.parse_ical(ical)
            self._recordAtStart = False

        sink = self.get_element('fdsink')
        sink.get_pad('sink').connect('notify::caps', self._notify_caps_cb)
        # connect to client-removed so we can detect errors in file writing
        sink.connect('client-removed', self._client_removed_cb)

    # add code that lets recordings be schedules
    # TODO: resolve overlapping events
    def schedule_recording(self, whenStart, whenEnd, recur=None):
        """
        Sets a recording to start at a time in the future for a specified
        duration.
        @param whenStart time of when to start recording
        @type whenStart datetime
        @param whenEnd time of when to end recording
        @type whenEnd datetime
        @param recur recurrence rule
        @type recur icalendar.props.vRecur
        """
        now = datetime.now()

        startRecurRule = None
        endRecurRule = None

        if recur:
            self.debug("Have a recurrence rule, parsing")
            # create dateutil.rrule from the recurrence rules
            startRecurRule = rrule.rrulestr(recur.ical(), dtstart=whenStart)
            endRecurRule = rrule.rrulestr(recur.ical(), dtstart=whenEnd) 
            if now >= whenStart:
                self.debug("Initial start before now (%r), finding new starts",
                    whenStart)
                whenStart = startRecurRule.after(now)
                whenEnd = endRecurRule.after(now)
                self.debug("New start is now %r", whenStart)

        if now < whenStart:
            start = whenStart - now
            startSecs = start.days * 86400 + start.seconds
            self.debug("scheduling a recording %d seconds away", startSecs)
            reactor.callLater(startSecs, 
                self.start_scheduled_recording, startRecurRule, whenStart)
            end = whenEnd - now
            endSecs = end.days * 86400 + end.seconds
            reactor.callLater(endSecs, 
                self.stop_scheduled_recording, endRecurRule, whenEnd)
        else:
            self.warning("attempt to schedule in the past!")

    def start_scheduled_recording(self, recurRule, when):
        self.change_filename()
        if recurRule:
            now = datetime.now()
            nextTime = recurRule.after(when)
            recurInterval = nextTime - now
            self.debug("recurring start interval: %r", recurInterval)
            recurIntervalSeconds = recurInterval.days * 86400 + \
                recurInterval.seconds
            self.debug("recurring start in %d seconds", recurIntervalSeconds)
            reactor.callLater(recurIntervalSeconds, 
                self.start_scheduled_recording,
                recurRule, nextTime)

    def stop_scheduled_recording(self, recurRule, when):
        self.stop_recording()
        if recurRule:
            now = datetime.now()
            nextTime = recurRule.after(when)
            recurInterval = nextTime - now
            recurIntervalSeconds = recurInterval.days * 86400 + \
                recurInterval.seconds
            self.debug("recurring stop in %d seconds", recurIntervalSeconds)
            reactor.callLater(recurIntervalSeconds, 
                self.stop_scheduled_recording,
                recurRule, nextTime)

    def parse_ical(self, icsStr):
        if HAS_ICAL:
            cal = Calendar.from_string(icsStr)
            for event in cal.walk('vevent'):
                dtstart = event.decoded('dtstart', '')
                dtend = event.decoded('dtend', '')
                self.debug("event parsed with start: %r end: %r", dtstart, dtend)
                recur = event.get('rrule', None)
                if dtstart and dtend:
                    self.schedule_recording(dtstart, dtend, recur)
        else:
            self.warning("Cannot parse ICAL; neccesary modules not installed")

pygobject.type_register(Disker)
