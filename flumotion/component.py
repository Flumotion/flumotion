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

import sys
import optik
import socket

import gst
import gobject

from twisted.internet import reactor
from twisted.python import log
from twisted.spread import pb

import pbutil
import gstutils

class BaseComponent(pb.Referenceable):
    def __init__(self, name, sources, host, port, pipeline_string=''):
        self.component_name = name
        self.sources = sources
        self.host = host
        self.port = port
        self.remote = None
        self.pipeline = None
        self.pipeline_signals = []
        self.pipeline_string = self.get_pipeline(pipeline_string)
        print 'pipeline: %s' % self.pipeline_string
        
        # Prefix our login name with the name of the component
        username = '%s_%s' % (self.getName(), name)

        log.msg('Connecting to controller %s:%d' % (host, port))
        factory = pb.PBClientFactory()
        reactor.connectTCP(host, port, factory)
        defered = factory.login(pbutil.Username(username), client=self)
        defered.addCallback(self.got_perspective_cb)

    def got_perspective_cb(self, perspective):
        #reactor.callLater(2, setattr, self, 'persp', persp)
        self.remote = perspective

    def hasPerspective(self):
        return self.remote != None

    def getName(self):
        assert hasattr(self, 'name')
        return self.name

    def getSources(self):
        return self.sources
    
    def getIP(self):
        return socket.gethostbyname(self.host)
        
    def pipeline_error_cb(self, object, element, error, arg):
        log.msg('element %s error %s %s' % (element.get_path_string(), str(error), repr(arg)))
        if self.hasPerspective():
            self.remote.callRemote('error', element.get_path_string(), error.message)
        else:
            print 'skipping remote-error, no perspective'
            
        self.cleanup()
        self.setup_pipeline()
        
    def pipeline_state_change_cb(self, element, old, state):
        log.msg('pipeline state-changed %s %s ' % (element.get_path_string(),
                                                   gst.element_state_get_name(state)))
        if self.hasPerspective():
            self.remote.callRemote('stateChanged', old, state)
        else:
            print 'skipping state-changed, no perspective'

    def set_state_and_iterate(self, state):
        retval = self.pipeline.set_state(state)
        if not retval:
            log.msg('WARNING: Changing state to %s failed' %
                    gst.element_state_get_name(state))
        gobject.idle_add(self.pipeline.iterate)
        
    def pipeline_pause(self):
        self.set_state_and_iterate(gst.STATE_PAUSED)
        
    def pipeline_play(self):
        self.set_state_and_iterate(gst.STATE_PLAYING)

    def pipeline_stop(self):
        self.set_state_and_iterate(gst.STATE_NULL)
        
    def cleanup(self):
        log.msg("cleaning up")
        
        assert self.pipeline != None

        if self.pipeline.get_state() != gst.STATE_NULL:
            log.msg('Pipeline was in state %s, changing to NULL' %
                    gst.element_state_get_name(self.pipeline.get_state()))
            self.pipeline.set_state(gst.STATE_NULL)
                
        # Disconnect signals
        map(self.pipeline.disconnect, self.pipeline_signals)
        self.pipeline = None
        self.pipeline_signals = []
        
    def setup_pipeline(self):
        log.msg('register(): creating pipeline: %s' % self.pipeline_string)
        self.pipeline = gst.parse_launch(self.pipeline_string)

        sig_id = self.pipeline.connect('error', self.pipeline_error_cb)
        self.pipeline_signals.append(sig_id)
        sig_id = self.pipeline.connect('state-change', self.pipeline_state_change_cb)
        self.pipeline_signals.append(sig_id)
        sig_id = self.pipeline.connect('deep-notify', gstutils.verbose_deep_notify_cb)
        self.pipeline_signals.append(sig_id)
        
    def remote_register(self):
        if not self.hasPerspective():
            log.msg('WARNING: We are not ready yet, waiting 250 ms')
            reactor.callLater(0.250, self.remote_register)
            return
        
        self.setup_pipeline()
        
        return {'ip' : self.getIP(),
                'sources' : self.getSources() }
    
    def remote_get_free_port(self):
        start = 5500
        fd = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        while 1:
            try:
                fd.bind(('', start))
            except socket.error:
                start += 1
                continue
            break
        return start

class OptionError(Exception):
    pass
    
def get_options_for(kind, args):
    if kind == 'producer':
        need_pipeline = True
        need_sources = False
    elif kind == 'converter':
        need_pipeline = True
        need_sources = True
    elif kind == 'streamer':
        need_pipeline = False
        need_sources = True
    else:
        raise AssertionError
    
    parser = optik.OptionParser()
    parser.add_option('-c', '--controller-host',
                      action="store", type="string", dest="host",
                      default="localhost",
                      help="Controller to connect to [default localhost]")
    parser.add_option('', '--controller-port',
                      action="store", type="int", dest="port",
                      default=8890,
                      help="Controller port to connect to [default 8890]")
    parser.add_option('-n', '--name',
                      action="store", type="string", dest="name",
                      default=None,
                      help="Name of component")
    if need_pipeline:
        parser.add_option('-p', '--pipeline',
                          action="store", type="string", dest="pipeline",
                          default=None,
                          help="Pipeline to run")
    parser.add_option('-v', '--verbose',
                      action="store_true", dest="verbose",
                      help="Be verbose")

    if need_sources:
        parser.add_option('-s', '--sources',
                          action="store", type="string", dest="sources",
                          default="",
                          help="Host sources to get data from, separated by ,")

    if kind == 'streamer':
        parser.add_option('-p', '--protocol',
                          action="store", type="string", dest="protocol",
                          default="http",
                          help="Protocol to use [default http]")
        parser.add_option('-o', '--listen-port',
                          action="store", type="int", dest="listen_port",
                          default=8080,
                          help="Port to bind to [default 8080]")
        
    # Eek, strip out gst options
    args = [arg for arg in args if not arg.startswith('--gst')]
        
    options, args = parser.parse_args(args)

    if options.name is None:
        raise OptionError, 'Need a name'
    elif need_pipeline and options.pipeline is None:
        raise OptionError, 'Need a pipeline'
    elif need_sources and options.sources is None:
        raise OptionError, 'Need a source'
    elif kind == 'streamer':
        if not options.protocol:
            raise OptionError, 'Need a protocol'
        elif not options.listen_port:
            raise OptionError, 'Need a listen_port'
            return 2
        
    if options.verbose:
        log.startLogging(sys.stdout)

    if need_sources:
        if ',' in  options.sources:
            options.sources = options.sources.split(',')
        else:
            options.sources = [options.sources]

    return options
