# -*- Mode: Python -*-
# Flumotion - a video streaming server
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
#

import pygtk
pygtk.require('2.0')

import re
import socket
import sys
    
import gobject
import gst

if __name__ == '__main__':
    import gstreactor
    gstreactor.install()

from twisted.internet import reactor
from twisted.python import log
from twisted.spread import pb

import pbutil
import gstutils

class Transcoder(gobject.GObject, pb.Referenceable):
    __gsignals__ = {
        'data-recieved': (gobject.SIGNAL_RUN_FIRST, gobject.TYPE_NONE,
                          (gst.Buffer,)),
    }
    def __init__(self, username, host, port, pipeline):
        self.__gobject_init__()
        self.host = host
        factory = pb.PBClientFactory()
        reactor.connectTCP(host, port, factory)
        defered = factory.login(pbutil.Username('trans_%s' % username),
                                client=self)
        defered.addCallback(self.got_perspective_cb)
        self.pipeline_string = pipeline
        
    def got_perspective_cb(self, persp):
        self.persp = persp
        
    def pipeline_error_cb(self, object, element, error, arg):
        log.msg('element %s error %s %s' % (element.get_path_string(), str(error), repr(arg)))
        self.persp.callRemote('error', element.get_path_string(), error.message)

    def pipeline_state_change_cb(self, element, old, state):
        log.msg('pipeline state-changed %s %s -> %s' % (element.get_path_string(),
                                                        gst.element_state_get_name(old),
                                                        gst.element_state_get_name(state)))
        self.persp.callRemote('stateChanged', old, state)
        
    def pipeline_pause(self):
        retval = self.pipeline.set_state(gst.STATE_PAUSED)
        if not retval:
            log.msg('Changing state to PAUSED failed')
        gobject.idle_add(self.pipeline.iterate)
        
    def pipeline_play(self):
        retval = self.pipeline.set_state(gst.STATE_PLAYING)
        if not retval:
            log.msg('Changing state to PLAYING failed')
        gobject.idle_add(self.pipeline.iterate)
        
    def start(self, source_port, sink_host, sink_port):
        log.msg('(source) Going to listen on port %d' % source_port)
        log.msg('(sink)   Going to connect to %s:%d' % (sink_host, sink_port))
        
        pipe = 'tcpclientsrc name=source ! %s ! tcpserversink name=sink'
        self.pipeline = gst.parse_launch(pipe % self.pipeline_string)
        self.pipeline.connect('deep-notify', gstutils.verbose_deep_notify_cb)
        self.pipeline.connect('error', self.pipeline_error_cb)
        self.pipeline.connect('state-change', self.pipeline_state_change_cb)
        
        source = self.pipeline.get_by_name('source')
        source.set_property('host', sink_host)
        source.set_property('port', source_port)

        sink = self.pipeline.get_by_name('sink')
        sink.set_property('port', sink_port)
        
        reactor.callLater(0, self.pipeline_play)
        log.msg('returning from listen')

    # XXX: Rename to get_controller_host or something
    def remote_prepare(self):
        return socket.gethostbyname(self.host)
    
    def remote_start(self, source_port, sink_host, sink_port):
        self.start(source_port, sink_host, sink_port)

        
def parseHostString(string, port=8890):
    if not string:
        return 'localhost', port
    
    try:
        host, port = re.search(r'(.+):(\d+)', string).groups()
    except:
        host = string
        
    return host, port
    
if __name__ == '__main__':
    log.startLogging(sys.stdout)

    if len(sys.argv) == 2:
        pipeline = sys.argv[1]
        controller = ''
    elif len(sys.argv) == 3:
        pipeline = sys.argv[1] 
        controller = sys.argv[2]
    else:
        print 'Usage: transcoder.py pipeline [controller-host[:port]]'
        sys.exit(2)
        
    name = 'johan'
    host, port = parseHostString(controller)
    log.msg('Connect to %s on port %d' % (host, port))
    client = Transcoder(name, host, port, pipeline)
    reactor.run()
