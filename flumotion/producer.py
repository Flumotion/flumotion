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
import gstutils

class Producer(pb.Referenceable):
    def __init__(self, username, host, port, pipeline_string):
        factory = pb.PBClientFactory()
        reactor.connectTCP(host, port, factory)
        defered = factory.login(pbutil.Username('prod_%s' % username),
                                client=self)
        defered.addCallback(self.got_perspective_cb)
        
        self.pipeline_string = pipeline_string
        self.persp = None
        self.pipeline = None
        self.pipeline_signals = []
        
    def got_perspective_cb(self, persp):
        #reactor.callLater(2, setattr, self, 'persp', persp)
        self.persp = persp
        
    def pipeline_error_cb(self, object, element, error, arg):
        log.msg('element %s error %s %s' % (element.get_path_string(), str(error), repr(arg)))
        if self.persp:
            self.persp.callRemote('error', element.get_path_string(), error.message)
        else:
            print 'skipping remote-error, no perspective'

        # XXX: Maybe do this from controller
        self.prepare()
        
    def pipeline_state_change_cb(self, element, old, state):
        log.msg('pipeline state-changed %s %s -> %s' % (element.get_path_string(),
                                                        gst.element_state_get_name(old),
                                                        gst.element_state_get_name(state)))
        if self.persp is not None:
            self.persp.callRemote('stateChanged', old, state)
        else:
            print 'skipping state-changed, no perspective'
        
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
        if self.persp is None:
            log.msg('WARNING: We are not ready yet, waiting 250 ms')
            reactor.callLater(0.250, self.prepare)
            return

        log.msg('prepare called')

        if self.pipeline is not None:
            if self.pipeline.get_state() != gst.STATE_NULL:
                log.msg('Pipeline was in state %s, changing to NULL' %
                        gst.element_state_get_name(self.pipeline.get_state()))
                self.pipeline.set_state(gst.STATE_NULL)
            # Disconnect signals
            map(self.pipeline.disconnect, self.pipeline_signals)
            self.pipeline = None
            self.pipeline_signals = []
            
        pipeline = '%s ! tcpserversink name=sink' % self.pipeline_string
        
        log.msg('going to run pipeline: %s' % pipeline)
        self.pipeline = gst.parse_launch(pipeline)
        sig_id = self.pipeline.connect('error', self.pipeline_error_cb)
        self.pipeline_signals.append(sig_id)
        sig_id = self.pipeline.connect('state-change', self.pipeline_state_change_cb)
        self.pipeline_signals.append(sig_id)
        sig_id = self.pipeline.connect('deep-notify', gstutils.verbose_deep_notify_cb)
        self.pipeline_signals.append(sig_id)
        
    def listen(self, host, port):
        log.msg('Going to listen on port %d' % port)

        sink = self.pipeline.get_by_name('sink')
        if host:
            sink.set_property('host', host)
        sink.set_property('port', port)
        
        self.pipeline_play()
        
    # Remote interface
    def remote_prepare(self):
        self.prepare()

    def remote_listen(self, host, port):
        self.listen(host, port)
        
if __name__ == '__main__':
    log.startLogging(sys.stdout)
    
    if len(sys.argv) == 2:
        pipeline = sys.argv[1]
        controller = ''
    elif len(sys.argv) == 3:
        pipeline = sys.argv[1] 
        controller = sys.argv[2]
    else:
        print 'Usage: producer.py pipeline [controller-host[:port]]'
        sys.exit(2)

    name = 'johan'
    host = controller
    port = 8890
    log.msg('Connect to %s on port %d' % (host, port))
    client = Producer(name, host, port, pipeline)
    reactor.run()
    
