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

class Acquisition(pb.Referenceable):
    def __init__(self, username, host, port, pipeline_string):
        factory = pb.PBClientFactory()
        reactor.connectTCP(host, port, factory)
        defered = factory.login(pbutil.Username('acq_%s' % username),
                                client=self)
        defered.addCallback(self.got_perspective_cb)
        
        self.pipeline_string = pipeline_string
        self.persp = None
        
    def got_perspective_cb(self, persp):
        #reactor.callLater(2, setattr, self, 'persp', persp)
        self.persp = persp
        
    def pipeline_error_cb(self, object, element, error, arg):
        log.msg('element %s error %s %s' % (element.get_path_string(), str(error), repr(arg)))
        if self.persp:
            self.persp.callRemote('error', element.get_path_string(), error.message)
        else:
            print 'skipping remote-error, no perspective'

        self.pipeline.set_state(gst.STATE_NULL)
        self.prepare()
        
    def pipeline_state_change_cb(self, element, old, state):
        log.msg('pipeline state-changed %s %s -> %s' % (element.get_path_string(),
                                                        gst.element_state_get_name(old),
                                                        gst.element_state_get_name(state)))
        if self.persp:
            self.persp.callRemote('stateChanged', old, state)
        else:
            print 'skipping state-changed, no perspective'
        
    def sink_pad_deep_notify_caps_cb(self, element, pad, param):
        caps = pad.get_negotiated_caps()
        log.msg('notify-caps %s::%s is %s' % (element.get_path_string(),
                                              pad.get_name(),
                                              str(caps)))

        self.sink.disconnect(self.notify_id)
        self.pipeline_pause()
        
        if self.persp:
            self.persp.callRemote('notifyCaps', str(caps))
        else:
            print 'skipping notify-caps, no perspective'
            
        self.caps = caps
        
    def pipeline_deep_notify_cb(self, object, orig, pspec):
        log.msg('deep-notify %s: %s = %s' % (orig.get_path_string(),
                                             pspec.name,
                                             orig.get_property(pspec.name)))

    def pipeline_pause(self):
        retval = self.pipeline.set_state(gst.STATE_PAUSED)
        if not retval:
            log.msg('WARNING: Changing state to PLAYING failed')
        gobject.idle_add(self.pipeline.iterate)
        
    def pipeline_play(self):
        retval = self.pipeline.set_state(gst.STATE_PLAYING)
        if not retval:
            log.msg('WARNING: Changing state to PLAYING failed')
        gobject.idle_add(self.pipeline.iterate)

    def prepare(self):
        if not self.persp:
            log.msg('WARNING: We are not ready yet, waiting 250 ms')
            reactor.callLater(0.250, self.prepare)
            return
        
        log.msg('prepare called')
        
        full_pipeline = '%s ! fakesink silent=1 name=fakesink' % self.pipeline_string
        log.msg('going to run pipeline: %s' % full_pipeline)
        self.pipeline = gst.parse_launch(full_pipeline)
        self.pipeline.connect('error', self.pipeline_error_cb)
        self.pipeline.connect('state-change', self.pipeline_state_change_cb)
        self.pipeline.connect('deep-notify', self.pipeline_deep_notify_cb)
        
        self.src = self.pipeline.get_list()[-2]
        
        self.sink = self.pipeline.get_by_name('fakesink')
        
        self.notify_id = self.sink.connect('deep-notify::caps',
                                           self.sink_pad_deep_notify_caps_cb)

        reactor.callLater(0, self.pipeline_play)

    def rewind(self):
        # Stream back to the beginning
        event = gst.event_new_seek(gst.FORMAT_TIME |
                                   gst.SEEK_METHOD_SET |
                                   gst.SEEK_FLAG_FLUSH, 0)
        self.sink.send_event(event)

    def relink(self, sink):
        # Unlink and remove
        
        self.pipeline.remove(self.sink)
        assert not self.src.unlink(self.sink)

        self.sink = sink
        
        self.pipeline.add(self.sink)
        self.src.link_filtered(self.sink, self.caps)
        
    def connect(self, hostname, port):
        log.msg('Going to connect to %s:%d' % (hostname, port))

        self.pipeline_pause()
        
        element = gst.element_factory_make('tcpclientsink')
        element.set_property('host', hostname)
        element.set_property('port', port)
        
        self.rewind()
        self.relink(element)
        
        reactor.callLater(0, self.pipeline_play)

    def listen(self, port):
        log.msg('Going to listen on port %d' % port)

        self.pipeline_pause()
        
        element = gst.element_factory_make('tcpserversink')
        element.set_property('port', port)
        
        self.rewind()
        self.relink(element)
        
        reactor.callLater(0, self.pipeline_play)
        
    # Remote interface
    def remote_prepare(self):
        self.prepare()

    def remote_connect(self, hostname, port):
        self.connect(hostname, port)

    def remote_listen(self, port):
        self.listen(port)
        
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
        print 'Usage: acquisition.py pipeline [controller-host[:port]]'
        sys.exit(2)

    name = 'johan'
    host, port = parseHostString(controller)
    log.msg('Connect to %s on port %d' % (host, port))
    client = Acquisition(name, host, port, pipeline)
    reactor.run()
    
