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
    pipe_template = 'multifdsink sync-clients=1 name=fdsink mode=1'
    def __init__(self, name, source, location):
        component.ParseLaunchComponent.__init__(self, name, [source],
                                                [], self.pipe_template)
        self.file_fd = None
        self.location = location
        self.change_filename()

    def change_filename(self):
        sink = self.pipeline.get_by_name('fdsink')
        if sink.get_state() == gst.STATE_NULL:
            sink.set_state(gst.STATE_READY)

        if self.file_fd:
            self.file_fd.flush()
            sink.emit('remove', self.file_fd.fileno())
            self.file_fd = None
            
        date = time.strftime('%Y%m%d-%H:%M:%S', time.localtime())
        if '%s' in self.location:
            location = self.location.replace('%s', date)
        else:
            location = self.location + '.' + date
            
        self.file_fd = open(location, 'a')
        fno = self.file_fd.fileno()
        sink.emit('add', fno)

    def feed_state_change_cb(self, element, old, state):
        component.BaseComponent.feed_state_change_cb(self, element,
                                                     old, state, '')
        if state == gst.STATE_PLAYING:
            self.debug('Ready')
            
    def link_setup(self, sources, feeds):
        sink = self.pipeline.get_by_name('fdsink')
        sink.connect('state-change', self.feed_state_change_cb)
        
from twisted.protocols import http
from twisted.web import server, resource
from twisted.internet import reactor

ERROR_TEMPLATE = """<!doctype html public "-//IETF//DTD HTML 2.0//EN">
<html>
<head>
  <title>%(code)d %(error)s</title>
</head>
<body>
<h2>%(code)d %(error)s</h2>
</body>
</html>
"""

class FileStreamingResource(resource.Resource):
    def __init__(self, streamer):
        self.streamer = streamer

        resource.Resource.__init__(self)

    def isAuthenticated(self, request):
        if (request.getUser() == 'fluendo' and
            request.getPassword() == 's3kr3t'):
            return True
        return False

    def getChild(self, path, request):
        return self

    def makeError(self, request, error_code):
        request.setResponseCode(error_code)
        request.setHeader('content-type', 'text/html')
        request.setHeader('WWW-Authenticate', 'Basic realm="Restricted Access"')
        
        return ERROR_TEMPLATE % dict(code=error_code,
                                     error=http.RESPONSES[error_code])

    def restart(self):
        self.streamer.change_filename()
        
    def restart_form(self, request):
        return '''<form action="/" method="POST">
  <input type=submit value="Restart">
</form>'''
    
    def render_POST(self, request):
        if not self.isAuthenticated(request):
            return self.makeError(request, http.UNAUTHORIZED)

        self.restart()
        
        return '''<b>Restarted</b><br><br>''' + self.restart_form(request)
    
    def render_GET(self, request):
        if not self.isAuthenticated(request):
            return self.makeError(request, http.UNAUTHORIZED)

        return self.restart_form(request)
    
def createComponent(config):
    name = config['name']
    source = config['source']
    location = config['location']
    port = int(config.get('auth-port', 9999))
    component = FileSinkStreamer(name, source, location)

    resource = FileStreamingResource(component)
    factory = server.Site(resource=resource)
    component.debug('Listening on %d' % port)
    reactor.listenTCP(port, factory)
    
    return component
