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

import re
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

class ClientFactory(pb.PBClientFactory):
    def __repr__(self):
        return '<ClientFactory at 0x%x>' % id(self)
    
class Acquisition(pb.Referenceable):
    def __init__(self, pipeline_string):
        self.pipeline_string = pipeline_string

    def gotPerspective(self, persp):
        self.persp = persp
        
    def pipeline_error_cb(self, object, element, error, arg):
        log.msg('element %s error %s %s' % (element.get_path_string(), str(error), repr(arg)))
        self.persp.callRemote('error', element.get_path_string(), error.message)

    def pipeline_state_change_cb(self, element, old, state):
        log.msg('pipeline state-changed %s %s -> %s' % (element.get_path_string(),
                                                        gst.element_state_get_name(old),
                                                        gst.element_state_get_name(state)))
        self.persp.callRemote('stateChanged', old, state)
        
    def sink_pad_deep_notify_caps_cb(self, element, pad, param):
        caps = pad.get_negotiated_caps()
        log.msg('notify-caps %s::%s is %s' % (element.get_path_string(),
                                              pad.get_name(),
                                              str(caps)))

        self.sink.disconnect(self.notify_id)
        self.pipeline_pause()
        
        self.persp.callRemote('notifyCaps', str(caps))

    def pipeline_pause(self):
        self.pipeline.set_state(gst.STATE_PAUSED)
        
    def pipeline_play(self):
        self.pipeline.set_state(gst.STATE_PLAYING)
        
    def pipeline_iterate(self):
        return self.pipeline.iterate()
    
    def remote_prepare(self):
        log.msg('start called')
        
        self.pipeline = gst.parse_launch('%s ! fakesink name=fakesink' % self.pipeline_string)
        self.pipeline.connect('error', self.pipeline_error_cb)
        self.pipeline.connect('state-change', self.pipeline_state_change_cb)
        
        self.src = self.pipeline.get_list()[-2]
        
        self.sink = self.pipeline.get_by_name('fakesink')
        
        # XXX: Disconnect signal?
        self.notify_id = self.sink.connect('deep-notify::caps',
                                           self.sink_pad_deep_notify_caps_cb)

        reactor.callLater(0, self.pipeline_play)
        gobject.idle_add(self.pipeline_iterate)

    def remote_connect(self, hostname, port):
        # Pause
        self.pipeline.set_state(gst.STATE_PAUSED)
        
        # Stream back to the beginning
        event = gst.event_new_seek(gst.FORMAT_TIME |
                                   gst.SEEK_METHOD_SET |
                                   gst.SEEK_FLAG_FLUSH, 0)
        self.sink.send_event(event)

        # Unlink and remove
        self.pipeline.remove(self.sink)
        assert not self.src.unlink(self.sink)

        self.sink = gst.element_factory_make('tcpclientsink')
        self.sink.set_property('host', hostname)
        self.sink.set_property('port', port)
        
        self.sink.connect('error', self.error_cb)
        self.pipeline.add(self.sink)
        self.src.link(self.sink)
    
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

    if len(sys.argv) > 3:
        controller = sys.argv[1]
        pipeline = sys.argv[2]
    elif len(sys.argv) == 2:
        controller = ''
        pipeline = sys.argv[1]
    else:
        print 'Usage: client [controller] pipeline'
        sys.exit(1)

    name = 'johan'
    host, port = parseHostString(controller)
    log.msg('Connect to %s on port %d' % (host, port))
    factory = ClientFactory()
    reactor.connectTCP(host, port, factory)
    client = Acquisition(pipeline)
    defered = factory.login(pbutil.Username('acq_%s' % name),
                            client=client)
    defered.addCallback(client.gotPerspective)
    reactor.run()
    
