# -*- Mode: Python -*-
# vi:si:et:sw=4:sts=4:ts=4

# Flumotion - a video streamer server
# Copyright (C) 2004 Fluendo
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
# Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.

import time

import gst

from flumotion.server import component

class FileSinkStreamer(component.ParseLaunchComponent):
    kind = 'streamer'
    pipe_template = 'filesink name=sink location="%s"'
    def __init__(self, name, sources, location):
        self.location = location

        pipeline = self.pipe_template % self.get_location()
        component.ParseLaunchComponent.__init__(self, name, sources,
                                                [], pipeline)

    def create_admin(self):
        from twisted.manhole.telnet import ShellFactory
        from flumotion.twisted.shell import Shell
        
        ts = ShellFactory()
        ts.username = 'fluendo'
        ts.protocol = Shell
        ts.namespace['self'] = self
        ts.namespace['restart'] = self.local_restart

        return ts
    
    def get_location(self):
        if self.location.find('%') != -1:
            timestamp = time.strftime('%Y-%m-%d-%H:%M:%S', time.localtime())
            return self.location % timestamp

        return self.location

    def local_restart(self):
        if self.pipeline is None:
            self.msg('Not started yet, skipping')
            return

        self.pipeline.set_state(gst.STATE_PAUSED)

        # Save and close file
        sink = self.pipeline.get_by_name('sink')
        sink.set_state(gst.STATE_READY)

        location = self.get_location()
        self.msg('setting location to', location)
        sink.set_property('location', location)
        
        self.pipeline.set_state(gst.STATE_PLAYING)

    # connect() is already taken by gobject.GObject
    def connect_to(self, sources):
        self.setup_sources(sources)
        sink = self.pipeline.get_by_name('sink')
        sink.connect('state-change', self.feed_state_change_cb, '')

        self.pipeline_play()

    remote_connect = connect_to

def createComponent(config):
    name = config['name']
    source = config['source']
    location = config['location']
    
    # XXX: How can we do this properly?
    FileSinkStreamer.kind = 'streamer'

    component = FileSinkStreamer(name, [source], location)

    # Administrative interface
    #factory = component.create_admin()
    #self.msg('Starting admin factory on port %d' % c.port)
    #reactor.listenTCP(port, factory)

    return component
