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
import datetime as dt
import bisect

import gobject
import gst

from twisted.internet import reactor

from flumotion.component import feedcomponent
from flumotion.common import log, gstreamer, pygobject, messages,\
                             errors, common
from flumotion.common import documentation, format
from flumotion.common import eventcalendar, poller
from flumotion.common.i18n import N_, gettexter
from flumotion.common.mimetypes import mimeTypeToExtention
from flumotion.common.pygobject import gsignal

#   the flumotion.twisted.flavors is not bundled, and as we only need it for
#   the interface, we can skip doing the import and thus not create
#   incompatibilities with workers running old versions of flavors that will be
#   asked to create diskers importing the IStateCacheableListener from that
#   module
# from flumotion.twisted.flavors import IStateCacheableListener

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


def _openFile(component, location, mode):
    try:
        file = open(location, mode)
        return file
    except IOError, e:
        component.warning("Failed to open output file %s: %s",
                   location, log.getExceptionMessage(e))
        m = messages.Error(T_(N_(
            "Failed to open output file '%s' for writing. "
            "Check permissions on the file."), location))
        component.addMessage(m)
        return None


class Index(log.Loggable):
    '''
    Creates an index of keyframes for a file, than can be used later for
    seeking in non indexed formats or whithout parsing the headers.

    The format of the index is very similar to the AVI Index, but it can also
    include information about the real time of each entry in UNIX time.
    (see 'man aviindex')

    If the index is for an indexed format, the offset of the first entry will
    not start from 0. This offset is the size of the headers.  '''

    # CHK:      Chunk number starting from 0
    # POS:      Absolute byte position of the chunk in the file
    # LEN:      Length in bytes of the chunk
    # TS:       Timestamp of the chunk (ns)
    # DUR:      Duration of the chunk (ns)
    # KF:       Whether it starts with a keyframe or not
    # TDT:      Time and date using a UNIX timestamp (s)
    # TDUR:     Duration of the chunk in UNIX time (s)
    INDEX_HEADER = "FLUIDX1 #Flumotion\n"
    INDEX_KEYS = ['CHK', 'POS', 'LEN', 'TS', 'DUR', 'KF', 'TDT', 'TDUR']
    INDEX_EXTENSION = 'index'

    def __init__(self):
        self._index = []
        self._headers_size = 0

    ### Public methods ###

    def updateStart(self, timestamp):
        '''
        Remove entries in the index older than this timestamp
        '''
        self.debug("Removing entries older than %s", timestamp)
        self._index = self._filter_index(timestamp) or []

    def addEntry(self, offset, timestamp, keyframe, tdt=0):
        '''
        Add a new entry to the the index
        '''
        if len(self._index) > 0:
            # Check that new entries have increasing timestamp, offset and tdt
            if not self._checkEntriesContinuity(offset, timestamp, tdt):
                return
            # And update the length and duration of the last entry
            self._updateLastEntry(offset, timestamp, tdt)

        self._index.append({'offset': offset, 'length': -1,
                            'timestamp': timestamp, 'duration': -1,
                            'keyframe': keyframe, 'tdt': tdt,
                            'tdt-duration': -1})

        self.debug("Added new entry to the index: offset=%s timestamp=%s "
                   "keyframe=%s tdt=%s", offset, timestamp, keyframe, tdt)

    def setHeadersSize(self, size):
        '''
        Set the headers size in bytes. Multifdsink append the stream headers
        to each client. This size is then used to adjust the offset of the
        index entries
        '''
        self._headers_size = size

    def getHeaders(self):
        '''
        Return an index entry corresponding to the headers, which is a chunk
        with 'offset' 0 and 'length' equals to the headers size
        '''
        if self._headers_size == 0:
            return None
        return {'offset': 0, 'length': self._headers_size,
                'timestamp': 0, 'duration': -1,
                'keyframe': 0, 'tdt': 0, 'tdt-duration': -1}

    def getFirstTimestamp(self):
        if len(self._index) == 0:
            return -1
        return self._index[0]['timestamp']

    def getFirstTDT(self):
        if len(self._index) == 0:
            return -1
        return self._index[0]['tdt']

    def clipTimestamp(self, start, stop):
        '''
        Clip the current index to a start and stop time, returning all the
        entries matching the boundaries using the 'timestamp'
        '''
        return self._clip('timestamp', 'duration', start, stop)

    def clipTDT(self, start, stop):
        '''
        Clip the current index to a start and stop time, returning all the
        entries matching the boundaries using the 'tdt'
        '''
        return self._clip('tdt', 'tdt-duration', start, stop)

    def clear(self):
        '''
        Clears the index
        '''
        self._index = []

    def save(self, location, start=None, stop=None):
        '''
        Saves the index in a file, using the entries from 'start' to 'stop'
        '''
        if len(self._index) == 0:
            self.warning("The index doesn't contain any entry and it will not "
                         "be saved")
            return False
        f = _openFile(self, location, 'w+')
        if not f:
            return False

        self._write_index_headers(f)
        self._write_index_entries(f, self._filter_index(start, stop))
        self.info("Index saved successfully. start=%s stop=%s location=%s ",
                   start, stop, location)
        return True

    def loadIndexFile(self, location):
        '''
        Loads the entries of the index from an index file
        '''

        def invalidIndex(reason):
            self.warning("This file is not a valid index: %s", reason)
            return False

        if not location.endswith(self.INDEX_EXTENSION):
            return invalidIndex("the extension of this file is not '%s'" %
                                self.INDEX_EXTENSION)
        try:
            self.info("Loading index file %s", location)
            file = open(location, 'r')
            indexString = file.readlines()
            file.close()
        except IOError, e:
            return invalidIndex("error reading index file (%r)" % e)
        # Check if the file is not empty
        if len(indexString) == 0:
            return invalidIndex("the file is empty")
        # Check headers
        if not indexString[0].startswith('FLUIDX1 #'):
            return invalidIndex('header is not FLUIDX1')
        # Check index keys declaration
        keysStr = ' '.join(self.INDEX_KEYS)
        if indexString[1].strip('\n') != keysStr:
            return invalidIndex('keys definition is not: %s' % keysStr)
        # Add entries
        setHeaders = True
        for entryLine in indexString[2:]:
            e = entryLine.split(' ')
            if len(e) < len(self.INDEX_KEYS):
                return invalidIndex("one of the entries doesn't have enough "
                                    "parameters (needed=%d, provided=%d)" %
                                    (len(self.INDEX_KEYS), len(e)))
            try:
                self.addEntry(int(e[1]), int(e[3]), common.strToBool(e[5]),
                              int(e[6]))
            except Exception, e:
                return invalidIndex("could not parse one of the entries: %r"
                                    % e)
            if setHeaders:
                self._headers_size = int(e[1])
                setHeaders = False
        self.info("Index parsed successfully")
        return True

    ### Private methods ###

    def _updateLastEntry(self, offset, timestamp, tdt):
        last = self._index[-1]
        last['length'] = offset - last['offset']
        last['duration'] = timestamp - last['timestamp']
        last['tdt-duration'] = tdt - last['tdt']

    def _checkEntriesContinuity(self, offset, timestamp, tdt):
        last = self._index[-1]
        for key, value in [('offset', offset), ('timestamp', timestamp),
                           ('tdt', tdt)]:
            if value < last[key]:
                self.warning("Could not add entries with a decreasing %s "
                         "(last=%s, new=%s)", key, last[key], value)
                return False
        return True

    def _clip(self, keyTS, keyDur, start, stop):
        '''
        Clip the index to a start and stop time. For an index with 10
        entries of 10 seconds starting from 0, cliping from 15 to 35 will
        return the entries 1, 2, and 3.
        '''
        if start >= stop:
            return None

        keys = [e[keyTS] for e in self._index]

        # If the last entry has a duration we add a new entry in the TS list
        # with the stop time
        lastEntry = self._index[-1]
        if lastEntry[keyDur] != -1:
            keys.append(lastEntry[keyTS] + lastEntry[keyDur])

        # Return if the start and stop time are not inside the boundaries
        if stop <= keys[0] or start >= keys[-1]:
            return None

        # Set the start and stop time to match the boundaries so that we don't
        # get indexes outside the array boundaries
        if start <= keys[0]:
            start = keys[0]
        if stop >= keys[-1]:
            stop = keys[-1] - 1

        # Do the bisection
        i_start = bisect.bisect_right(keys, start) - 1
        i_stop = bisect.bisect_right(keys, stop)

        return self._index[i_start:i_stop]

    def _filter_index(self, start=None, stop=None):
        '''
        Filter the index with a start and stop time.
        FIXME: Check performance difference with clipping
        '''
        if len(self._index) == 0:
            return
        if not start and not stop:
            return self._index
        if not start:
            start = self._index[0]['timestamp']
        if not stop:
            last_entry = self._index[len(self._index)-1]
            stop = last_entry['timestamp'] + 1
        return [x for x in self._index if (x['timestamp'] >= start and\
                x['timestamp'] <= stop)]

    def _write_index_headers(self, file):
        file.write("%s" % self.INDEX_HEADER)
        file.write("%s\n" % ' '.join(self.INDEX_KEYS))

    def _write_index_entries(self, file, entries):
        offset = self._headers_size - self._index[0]['offset']
        count = 0

        for entry in self._index:
            frmt = "%s\n" % " ".join(['%s'] * len(self.INDEX_KEYS))
            file.write(frmt % (count, entry['offset'] + offset,
                                      entry['length'],
                                      entry['timestamp'],
                                      entry['duration'],
                                      entry['keyframe'],
                                      entry['tdt'],
                                      entry['tdt-duration']))
            count += 1


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
    logCategory = "disker"

    componentMediumClass = DiskerMedium
    checkOffset = True
    pipe_template = 'multifdsink name=fdsink sync-method=2 mode=1 sync=false'
    file = None
    directory = None
    location = None
    caps = None
    last_tstamp = None
    indexLocation = None
    writeIndex = False
    syncOnTdt = False
    reactToMarks = False

    _offset = 0L
    _headers_size = 0
    _index = None
    _nextIsKF = False
    _lastTdt = None
    _startFilenameTemplate = None # template to use when starting off recording
    _startTime = None             # time of event when starting
    _rotateTimeDelayedCall = None
    _pollDiskDC = None            # _pollDisk delayed calls
    _symlinkToLastRecording = None
    _symlinkToCurrentRecording = None


    #   see the commented out import statement for IStateCacheableListener at
    #   the beginning of this file
    # implements(IStateCacheableListener)

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
        self._clock = pipeline.get_clock()
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

        self.writeIndex = properties.get('write-index', False)
        self.reactToMarks = properties.get('react-to-stream-markers', False)
        self.syncOnTdt = properties.get('sync-on-tdt', False)

        sink = self.get_element('fdsink')

        if gstreamer.element_factory_has_property('multifdsink',
                                                  'resend-streamheader'):
            sink.set_property('resend-streamheader', False)
        else:
            self.debug("resend-streamheader property not available, "
                       "resending streamheader when it changes in the caps")
        sink.get_pad('sink').connect('notify::caps', self._notify_caps_cb)
        # connect to client-removed so we can detect errors in file writing
        sink.connect('client-removed', self._client_removed_cb)

        if self.writeIndex:
            self._index = Index()

        if self.reactToMarks:
            pfx = properties.get('stream-marker-filename-prefix', '%03d.')
            self._markerPrefix = pfx

        if self.reactToMarks or self.writeIndex or self.syncOnTdt:
            sink.get_pad("sink").add_data_probe(self._src_pad_probe)


    ### our methods

    def _tdt_to_datetime(self, s):
        '''
        Can raise and Exception if the structure doesn't cotains all the
        requiered fields. Protect with try-except.
        '''
        if s.get_name() != 'tdt':
            return None
        t = dt.datetime(s['year'], s['month'], s['day'], s['hour'],
            s['minute'], s['second'])
        return time.mktime(t.timetuple())

    def _updateIndex(self, offset, timestamp, isKeyframe, tdt=0):
        self._index.addEntry(offset, timestamp, isKeyframe, tdt)

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
                self._startTime = instance.start
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

    def changeFilename(self, filenameTemplate=None, datetime=None):
        """
        @param filenameTemplate: strftime format string to decide filename
        @param time:             an aware datetime used for the filename and
                                 to compare if an existing file needs to be
                                 overwritten. defaulting to datetime.now().
        """
        mime = self.getMime()
        ext = mimeTypeToExtention(mime)

        # if the events comes from the calendar, datetime is aware and we can
        # deduce from it both the local and utc time.
        # in case datetime is None datetime.now() doesn't return an aware
        # datetime, so we need to get both the local time and the utc time.
        tm = datetime or dt.datetime.now()
        tmutc = datetime or dt.datetime.utcnow()

        # delay the stop of the current recording to ensure there are no gaps
        # in the recorded files. We could think that emitting first the signal
        # to add a new client before the one to remove the client and syncing
        # with the latest keyframe should be enough, but it doesn't ensure the
        # stream continuity if it's done close to a keyframe because when
        # multifdsink looks internally for the latest keyframe it's already to
        # late and a gap is introduced.
        if self.writeIndex and self.location:
            self.indexLocation = '.'.join([self.location,
                                           Index.INDEX_EXTENSION])
        reactor.callLater(1, self._stopRecordingFull, self.file, self.location,
                          self.last_tstamp, True)

        sink = self.get_element('fdsink')
        if sink.get_state() == gst.STATE_NULL:
            sink.set_state(gst.STATE_READY)

        filename = ""
        if not filenameTemplate:
            filenameTemplate = self._defaultFilenameTemplate
        filename = "%s.%s" % (format.strftime(filenameTemplate,
            # for the filename we want to use the local time
            tm.timetuple()), ext)
        self.location = os.path.join(self.directory, filename)

        # only overwrite existing files if it was last changed before the
        # start of this event; ie. if it is a recording of a previous event
        location = self.location
        i = 1
        while os.path.exists(location):
            mtimeTuple = time.gmtime(os.stat(location).st_mtime)
            # time.gmtime returns a time tuple in utc, so we compare against
            # the utc timetuple of the datetime
            if mtimeTuple <= tmutc.utctimetuple():
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
        self._stopRecordingFull(self.file, self.location,
                               self.last_tstamp, False)

    def _stopRecordingFull(self, file, location, lastTstamp, delayedStop):
        sink = self.get_element('fdsink')
        if sink.get_state() == gst.STATE_NULL:
            sink.set_state(gst.STATE_READY)

        if file:
            file.flush()
            sink.emit('remove', file.fileno())
            self._recordingStopped(file, location)
            file = None
            if not delayedStop:
                self.uiState.set('filename', None)
                self.uiState.set('recording', False)
            try:
                size = format.formatStorage(os.stat(location).st_size)
            except EnvironmentError, e:
                # catch File not found, permission denied, disk problems
                size = "unknown"

            # Limit number of entries on filelist, remove the oldest entry
            fl = self.uiState.get('filelist', otherwise=[])
            if FILELIST_SIZE == len(fl):
                self.uiState.remove('filelist', fl[0])

            self.uiState.append('filelist', (lastTstamp,
                                             location,
                                             size))

            if not delayedStop and self._symlinkToLastRecording:
                self._updateSymlink(location,
                                    self._symlinkToLastRecording)


    # START OF THREAD AWARE METHODS

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

        if new and self._recordAtStart and not self._syncOnTdt:
            reactor.callLater(0, self.changeFilename,
                self._startFilenameTemplate, self._startTime)

    def _client_removed_cb(self, element, arg0, client_status):
        # treat as error if we were removed because of GST_CLIENT_STATUS_ERROR
        # FIXME: can we use the symbol instead of a numeric constant ?
        if self.writeIndex:
            stats = element.emit('get-stats', arg0)
            reactor.callFromThread(self._index.updateStart, stats[6])
            reactor.callFromThread(self._index.save, self.indexLocation,
                                   stats[6], stats[7])

        if client_status == 4:
            # since we get called from the streaming thread, hand off handling
            # to the reactor's thread
            reactor.callFromThread(self._client_error_cb)

    def _handle_event(self, event):
        if event.type != gst.EVENT_CUSTOM_DOWNSTREAM:
            return True

        struct = event.get_structure()
        struct_name = struct.get_name()
        if struct_name == 'FluStreamMark' and self.reactToMarks:
            if struct['action'] == 'start':
                self._onMarkerStart(struct['prog_id'])
            elif struct['action'] == 'stop':
                self._onMarkerStop()
        elif struct_name == 'tdt' and self.syncOnTdt:
            try:
                if self._lastTdt == None:
                    self._firstTdt = True
                self._lastTdt = self._tdt_to_datetime(struct)
                self._nextIsKF = True
            except KeyError, e:
                self.warning("Error parsing tdt event: %r", e)
        return True

    def _handle_buffer(self, buf):
        # IN_CAPS Buffers
        if buf.flag_is_set(gst.BUFFER_FLAG_IN_CAPS):
            self._headers_size += buf.size
            self._index.setHeadersSize(self._headers_size)
            return True

        # re-timestamp buffers without timestamp, so that we can get from
        # multifdsink's client stats the first and last buffer received
        if buf.timestamp == gst.CLOCK_TIME_NONE:
            buf.timestamp = self._clock.get_time()

        if self.syncOnTdt:
            if self._nextIsKF:
                # That's the first buffer after a 'tdt'. we mark it as a
                # keyframe and the sink will start streaming from it.
                buf.flag_unset(gst.BUFFER_FLAG_DELTA_UNIT)
                self._nextIsKF = False
                reactor.callFromThread(self._updateIndex, self._offset,
                    buf.timestamp, False, int(self._lastTdt))
                if self._recordAtStart and self._firstTdt:
                    reactor.callLater(0, self.changeFilename,
                        self._startFilenameTemplate, self._startTime)
                    self._firstTdt = False
            else:
                buf.flag_set(gst.BUFFER_FLAG_DELTA_UNIT)
        # if we don't sync on TDT and this is a keyframe, add it to the index
        elif not buf.flag_is_set(gst.BUFFER_FLAG_DELTA_UNIT):
            reactor.callFromThread(self._updateIndex,
                self._offset, buf.timestamp, True)
        self._offset += buf.size
        return True

    def _src_pad_probe(self, pad, data):
        # Events
        if type(data) is gst.Event:
            if self.reactToMarks or self.syncOnTdt:
                return self._handle_event(data)
        # Buffers
        elif self.writeIndex:
            return self._handle_buffer(data)
        return True

    # END OF THREAD AWARE METHODS

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
            eventInstance.start)
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
