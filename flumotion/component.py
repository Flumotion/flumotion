# -*- Mode: Python -*-
# vi:si:et:sw=4:sts=4:ts=4

# Flumotion - a video streaming server
# Copyright (C) 2004 Fluendo
 
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
 
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
 
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.

import os
import time
import optik
import socket
import sys
import string

import gst
import gobject

from twisted.internet import reactor
from twisted.python import log
from twisted.spread import pb

import pbutil
import gstutils
import errors

class ClientFactory(pbutil.ReconnectingPBClientFactory):
    __super_init = pbutil.ReconnectingPBClientFactory.__init__
    __super_login = pbutil.ReconnectingPBClientFactory.startLogin
    def __init__(self, component):
        self.__super_init()
        self.component = component
        
    def login(self, username):
        self.__super_login(pbutil.Username(username),
                           client=self.component)

    def gotPerspective(self, perspective):
        self.component.remote = perspective
        
class BaseComponent(pb.Referenceable):
    def __init__(self, name, sources, pipeline_string=''):
        self.component_name = name
        self.sources = sources
        self.remote = None
        self.pipeline = None
        self.pipeline_signals = []
        self.pipeline_string = self.get_pipeline(pipeline_string)

        # Prefix our login name with the name of the component
        self.username = '%s_%s' % (self.getKind(), name)
        self.factory = ClientFactory(self)
        self.factory.login(self.username)

        self.setup_pipeline()
        
    def msg(self, *args):
        log.msg('[%s] %s' % (self.component_name, string.join(args)))

    def get_pipeline(self, pipeline):
        sources = self.getSources()
        if pipeline == '' and not sources:
            raise TypeError, "Need a pipeline or a source"

        need_sink = True
        if pipeline == '':
            assert sources
            pipeline = 'fakesink signal-handoffs=1 silent=1 name=sink'
            need_sink = False
        elif pipeline.find('name=sink') != -1:
            need_sink = False
            
        assert pipeline != ''
        if len(sources) == 1:
            source_name = sources[0]
            if pipeline.find(source_name) != -1:
                pipeline = pipeline.replace('@' + source_name, 'tcpclientsrc name=%s' % source_name)
            else:
                pipeline = 'tcpclientsrc name=%s ! %s' % (source_name, pipeline)
        else:
            for source in sources:
                if ' ' in source:
                    raise TypeError, "spaces not allowed in sources"
            
                source_name = '@%s' % source
                if pipeline.find(source_name) == -1:
                    raise TypeError, "%s needs to be specified in the pipeline" % source_name
            
                pipeline = pipeline.replace(source_name, 'tcpclientsrc name=%s' % source)

        if need_sink:
            pipeline = '%s ! tcpserversink name=sink' % pipeline

        #pipeline = '{ %s } ' % pipeline
        self.msg('pipeline for %s is %s' % (self.component_name, pipeline))
        
        return pipeline

    def hasPerspective(self):
        return self.remote != None

    def getKind(self):
        assert hasattr(self, 'kind')
        return self.kind

    def getSources(self):
        return self.sources
    
    def getIP(self):
        assert self.remote
        peer = self.remote.broker.transport.getPeer()
        return socket.gethostbyname(peer[1])

    def callRemote(self, name, *args, **kwargs):
        if not self.hasPerspective():
            print 'skipping %s, no perspective' % name
            return

        def errback(reason):
            self.pipeline_stop()
            
        cb = self.remote.callRemote(name, *args, **kwargs)
        cb.addErrback(errback)
        
    def pipeline_error_cb(self, object, element, error, arg):
        self.msg('element %s error %s %s' % (element.get_path_string(), str(error), repr(arg)))
        self.callRemote('error', element.get_path_string(), error.message)
            
        self.cleanup()
        self.setup_pipeline()
        
    def pipeline_state_change_cb(self, element, old, state):
        self.msg('pipeline state-changed %s %s ' % (element.get_path_string(),
                                                   gst.element_state_get_name(state)))
        self.callRemote('stateChanged', old, state)

    def set_state_and_iterate(self, state):
        retval = self.pipeline.set_state(state)
        if not retval:
            self.msg('WARNING: Changing state to %s failed' %
                    gst.element_state_get_name(state))
        gobject.idle_add(self.pipeline.iterate)
        
    def pipeline_pause(self):
        self.set_state_and_iterate(gst.STATE_PAUSED)
        
    def pipeline_play(self):
        self.set_state_and_iterate(gst.STATE_PLAYING)

    def pipeline_stop(self):
        self.set_state_and_iterate(gst.STATE_NULL)
        
    def get_sink(self):
        assert self.pipeline, 'Pipeline not created'
        sink = self.pipeline.get_by_name('sink')
        assert sink, 'No sink element in pipeline'
        assert isinstance(sink, gst.Element)
        return sink

    def set_sink_properties(self, **properties):
        sink = self.get_sink()
        for prop_name in properties.keys():
            sink.set_property(prop_name, properties[prop_name])
        sink.set_property('protocol', 'gdp')

    def setup_sources(self, sources):
        # Setup all sources
        for source_name, source_host, source_port in sources:
            self.msg('Going to connect to %s (%s:%d)' % (source_name,
                                                        source_host,
                                                        source_port))
            source = self.pipeline.get_by_name(source_name)
            assert source, 'No source element named %s in pipeline' % source_name
            assert isinstance(source, gst.Element)
            
            source.set_property('host', source_host)
            source.set_property('port', source_port)
            source.set_property('protocol', 'gdp')
            
    def cleanup(self):
        self.msg("cleaning up")
        
        assert self.pipeline != None

        if self.pipeline.get_state() != gst.STATE_NULL:
            self.msg('Pipeline was in state %s, changing to NULL' %
                    gst.element_state_get_name(self.pipeline.get_state()))
            self.pipeline.set_state(gst.STATE_NULL)
                
        # Disconnect signals
        map(self.pipeline.disconnect, self.pipeline_signals)
        self.pipeline = None
        self.pipeline_signals = []
        
    def setup_pipeline(self):
        self.msg('register(): creating pipeline: %s' % self.pipeline_string)
        try:
            self.pipeline = gst.parse_launch(self.pipeline_string)
        except gobject.GError, e:
            raise errors.PipelineParseError, e

        self.pipeline.set_name('pipeline-' + self.component_name)
        sig_id = self.pipeline.connect('error', self.pipeline_error_cb)
        self.pipeline_signals.append(sig_id)
        sig_id = self.pipeline.connect('state-change', self.pipeline_state_change_cb)
        self.pipeline_signals.append(sig_id)
        #sig_id = self.pipeline.connect('deep-notify', gstutils.verbose_deep_notify_cb)
        #self.pipeline_signals.append(sig_id)
        
    def remote_register(self):
        if not self.hasPerspective():
            self.msg('WARNING: We are not ready yet, waiting 250 ms')
            reactor.callLater(0.250, self.remote_register)
            return
        
        return {'ip' : self.getIP(),
                'pid' :  os.getpid(), 
                'sources' : self.getSources() }
    
    def remote_get_free_port(self):
        return gstutils.get_free_port(start=5500)

    def remote_play(self):
        self.pipeline_play()
        
    def remote_stop(self):
        self.pipeline_stop()

    def remote_pause(self):
        self.pipeline_pause()
        
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
    else:
        options.sources = []
        
    return options
