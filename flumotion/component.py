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

import socket

import gst
import gobject

from twisted.internet import reactor
from twisted.python import log
from twisted.spread import pb

import pbutil
import gstutils

class Component(pb.Referenceable):
    def __init__(self, name, source, host, port):
        self.component_name = name
        self.source = source
        self.host = host
        self.port = port
        self.persp = None
        self.pipeline = None
        self.pipeline_signals = []

        factory = pb.PBClientFactory()
        reactor.connectTCP(host, port, factory)
        defered = factory.login(pbutil.Username(name), client=self)
        defered.addCallback(self.got_perspective_cb)

    def got_perspective_cb(self, persp):
        #reactor.callLater(2, setattr, self, 'persp', persp)
        self.persp = persp

    def has_perspective(self):
        return self.persp == None

    def get_ip(self):
        return socket.gethostbyname(self.host)
        
    def pipeline_error_cb(self, object, element, error, arg):
        log.msg('element %s error %s %s' % (element.get_path_string(), str(error), repr(arg)))
        if self.has_perspective():
            self.persp.callRemote('error', element.get_path_string(), error.message)
        else:
            print 'skipping remote-error, no perspective'

    def pipeline_state_change_cb(self, element, old, state):
        log.msg('pipeline state-changed %s %s -> %s' % (element.get_path_string(),
                                                        gst.element_state_get_name(old),
                                                        gst.element_state_get_name(state)))
        if self.persp is not None:
            self.persp.callRemote('stateChanged', old, state)
        else:
            print 'skipping state-changed, no perspective'

    def set_state_and_iterate(self, state):
        retval = self.pipeline.set_state(state)
        if not retval:
            log.msg('WARNING: Changing state to %s failed',
                    gst.element_state_get_name(state))
        gobject.idle_add(self.pipeline.iterate)
        
    def pipeline_pause(self):
        self.set_state_and_iterate(gst.STATE_PAUSED)
        
    def pipeline_play(self):
        self.set_state_and_iterate(gst.STATE_PLAYING)

    def pipeline_stop(self):
        self.set_state_and_iterate(gst.STATE_NULL)
        
    def cleanup(self):
        assert self.pipeline == None

        if self.pipeline.get_state() != gst.STATE_NULL:
            log.msg('Pipeline was in state %s, changing to NULL' %
                    gst.element_state_get_name(self.pipeline.get_state()))
            self.pipeline.set_state(gst.STATE_NULL)
                
        # Disconnect signals
        map(self.pipeline.disconnect, self.pipeline_signals)
        self.pipeline = None
        self.pipeline_signals = []
        
    def register(self):
        log.msg('register(): creating pipeline: %s' % self.pipeline_string)
        self.pipeline = gst.parse_launch(self.pipeline_string)

        sig_id = self.pipeline.connect('error', self.pipeline_error_cb)
        self.pipeline_signals.append(sig_id)
        sig_id = self.pipeline.connect('state-change', self.pipeline_state_change_cb)
        self.pipeline_signals.append(sig_id)
        sig_id = self.pipeline.connect('deep-notify', gstutils.verbose_deep_notify_cb)
        self.pipeline_signals.append(sig_id)
        
    def remote_register(self):
        if self.persp is None:
            log.msg('WARNING: We are not ready yet, waiting 250 ms')
            reactor.callLater(0.250, self.register)
            return
        
        self.register()
        
        return {'ip' : self.get_ip(),
                'source' : self.source }
    
