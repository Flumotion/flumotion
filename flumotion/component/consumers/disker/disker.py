# -*- Mode: Python -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# flumotion/component/consumers/disker/disker.py: archive to disk
#
# Flumotion - a streaming media server
# Copyright (C) 2004 Fluendo, S.L. (www.fluendo.com). All rights reserved.

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

import os
import time

import gst

from twisted.internet import reactor

from flumotion.component import feedcomponent
from flumotion.common import log
from flumotion.utils import gstutils

__all__ = ['Disker']

class Disker(feedcomponent.ParseLaunchComponent, log.Loggable):
    pipe_template = 'multifdsink sync-clients=1 name=fdsink mode=1'
    def __init__(self, name, source, directory):
        self.file_fd = None
        self.directory = directory
        self.location = None
        self.caps = None
        
        feedcomponent.ParseLaunchComponent.__init__(self, name,
                                                    [source],
                                                    [],
                                                    self.pipe_template)
    def setTimeRotate(self, time):
        reactor.callLater(time, self._rotateTimeCallback, time)

    def setSizeRotate(self, size):
        reactor.callLater(5, self._rotateSizeCallback, size)
        
    def _rotateTimeCallback(self, time):
        self.change_filename()
        
        # Add a new one
        reactor.callLater(time, self._rotateTimeCallback, time)

    def _rotateSizeCallback(self, size):
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
        mime = self.get_mime()
        if mime == 'application/ogg':
            ext = 'ogg'
        elif mime == 'multipart/x-mixed-replace':
            ext = 'multipart'
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
                                     '%s.%s.%s' % (self.get_name(), date, ext))

        self.file_fd = open(self.location, 'a')
        sink.emit('add', self.file_fd.fileno())
    
    def _notify_caps_cb(self, element, pad, param):
        caps = pad.get_negotiated_caps()
        if caps is None:
            return
        
        caps_str = gstutils.caps_repr(caps)
        self.debug('Got caps: %s' % caps_str)

        new = True
        if not self.caps is None:
            self.warning('Already had caps: %s, replacing' % caps_str)
            new = False
            
        self.debug('Storing caps: %s' % caps_str)
        self.caps = caps

        if new:
            reactor.callLater(0, self.change_filename)

    def _feeder_state_change_cb(self, element, old, state):
        feedcomponent.FeedComponent.feeder_state_change_cb(self, element,
                                                           old, state, '')
        if state == gst.STATE_PLAYING:
            self.debug('Ready')
            
    def link_setup(self, eaters, feeders):
        sink = self.get_element('fdsink')
        sink.connect('state-change', self._feeder_state_change_cb)
        sink.connect('deep-notify::caps', self._notify_caps_cb)
        
def createComponent(config):
    name = config['name']
    source = config['source']
    directory = config['directory']
    
    component = Disker(name, source, directory)

    rotateType = config['rotateType']
    if rotateType == 'size':
        component.setSizeRotate(config['size'])
    elif rotateType == 'time':
        component.setTimeRotate(config['time'])
        
    return component
