# -*- Mode: Python -*-
# vi:si:et:sw=4:sts=4:ts=4

# Flumotion - a video streamer server
# Copyright (C) 2004 Fluendo
#
# file.py: a consumer that writes to a file
# 
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
# 
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Street #330, Boston, MA 02111-1307, USA.

import time

import gst

from flumotion.server import component

__all__ = ['FileSinkStreamer']

class FileSinkStreamer(component.ParseLaunchComponent):
    pipe_template = 'multifdsink name=sink'
    def __init__(self, name, source, location):
        
        pipeline = self.pipe_template
        component.ParseLaunchComponent.__init__(self, name, [source],
                                                [], pipeline)
        sink = self.pipeline.get_by_name('sink')
        self.fd = open(location, 'w')
        sink.emit('add', self.fd.fileno())

    def change_filename(self, filename):
        sink.emit('remove', self.fd.fileno())
        self.fd.close() # XXX: Needed?
        
        self.fd = open(location, 'w')
        sink.emit('add', self.fd.fileno())
        
def createComponent(config):
    name = config['name']
    source = config['source']
    location = config['location']
    
    component = FileSinkStreamer(name, source, location)
    component.add_filename(location)
    
    return component
