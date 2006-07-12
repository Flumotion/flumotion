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

import os
import time

import gobject
import gst

from twisted.internet import reactor

from flumotion.component import feedcomponent
from flumotion.common import log, gstreamer, pygobject, messages

# proxy import
from flumotion.component.component import moods
from flumotion.common.pygobject import gsignal

from flumotion.common.messages import N_
T_ = messages.gettexter('flumotion')

__all__ = ['Disker']

class DiskerMedium(feedcomponent.FeedComponentMedium):
    # called when admin ui wants to change filename
    def remote_changeFilename(self):
        self.comp.change_filename()

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
    
    def change_filename(self):
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

        date = time.strftime('%Y%m%d-%H%M%S', time.localtime())
        self.location = os.path.join(self.directory,
                                     '%s.%s.%s' % (self.getName(), date, ext))

        self.file_fd = open(self.location, 'a')
        sink.emit('add', self.file_fd.fileno())
        self.uiState.set('filename', self.location)
    
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

        if new:
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
        sink = self.get_element('fdsink')
        sink.get_pad('sink').connect('notify::caps', self._notify_caps_cb)
        # connect to client-removed so we can detect errors in file writing
        sink.connect('client-removed', self._client_removed_cb)
        
pygobject.type_register(Disker)
