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
    pipe_template = 'filesink name=sink location="%s"'
    def __init__(self, name, source, location):
        self.location = location

        pipeline = self.pipe_template % location
        component.ParseLaunchComponent.__init__(self, name, [source],
                                                [], pipeline)

def createComponent(config):
    name = config['name']
    source = config['source']
    location = config['location']
    
    component = FileSinkStreamer(name, source, location)

    return component
