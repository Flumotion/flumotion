# -*- Mode: Python -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# flumotion/component/file/file.py: file consumer
#
# Flumotion - a streaming media server
# Copyright (C) 2004 Fluendo (www.fluendo.com)

# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
# See "LICENSE.GPL" in the source distribution for more information.

# This program is also licensed under the Flumotion license.
# See "LICENSE.Flumotion" in the source distribution for more information.

import os
import time

import gst

from twisted.internet import reactor

from flumotion.component import feedcomponent

__all__ = ['FileSinkStreamer']

class FileSinkStreamer(feedcomponent.ParseLaunchComponent):
    pipe_template = 'multifdsink sync-clients=1 name=fdsink mode=1'
    def __init__(self, name, source, directory):
        feedcomponent.ParseLaunchComponent.__init__(self, name,
                                                    [source],
                                                    [],
                                                    self.pipe_template)
        self.file_fd = None
        self.directory = directory
        self.location = None
        
        # Set initial filename
        self.change_filename()

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
        
    def change_filename(self):
        sink = self.get_element('fdsink')
        if sink.get_state() == gst.STATE_NULL:
            sink.set_state(gst.STATE_READY)

        if self.file_fd:
            self.file_fd.flush()
            sink.emit('remove', self.file_fd.fileno())
            self.file_fd = None
            
        date = time.strftime('%Y%m%d-%H:%M:%S', time.localtime())
        self.location = os.path.join(self.directory,
                                     self.get_name() + '_' + date)

        self.file_fd = open(self.location, 'a')
        sink.emit('add', self.file_fd.fileno())
    
    def feeder_state_change_cb(self, element, old, state):
        feedcomponent.FeedComponent.feeder_state_change_cb(self, element,
                                                           old, state, '')
        if state == gst.STATE_PLAYING:
            self.debug('Ready')
            
    def link_setup(self, eaters, feeders):
        sink = self.get_element('fdsink')
        sink.connect('state-change', self.feeder_state_change_cb)
        
def createComponent(config):
    name = config['name']
    source = config['source']
    directory = config['directory']
    
    component = FileSinkStreamer(name, source, directory)

    rotate_type = config['rotate_type']
    if rotate_type == 'size':
        component.setSizeRotate(config['size'])
    elif rotate_type == 'time':
        component.setTimeRotate(config['time'])
        
    return component
