# -*- Mode: Python -*-
# vi:si:et:sw=4:sts=4:ts=4

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

import os
import socket

import gst
import gobject
from twisted.internet import reactor
from twisted.spread import pb

from flumotion.twisted import pbutil
from flumotion.utils import log, gstutils
from flumotion import errors

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
    def __init__(self, name, sources):
        self.component_name = name
        self.sources = sources
        self.remote = None
        self.pipeline = None
        self.pipeline_signals = []

        # Prefix our login name with the name of the component
        self.username = '%s_%s' % (self.getKind(), name)
        self.factory = ClientFactory(self)
        self.factory.login(self.username)

        self.setup_pipeline()

    def msg(self, *args):
        log.msg(self.kind, *args)

    def warn(self, *args):
        log.warning(self.kind, *args)
        
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

    def restart(self):
        self.cleanup()
        self.setup_pipeline()
        
    def pipeline_error_cb(self, object, element, error, arg):
        self.msg('element %s error %s %s' % (element.get_path_string(), str(error), repr(arg)))
        self.callRemote('error', element.get_path_string(), error.message)

        #self.restart()
        
    def pipeline_state_change_cb(self, element, old, state):
        self.msg('pipeline state-changed %s %s ' % (element.get_path_string(),
                                                   gst.element_state_get_name(state)))
        self.callRemote('stateChanged', old, state)

    def set_state_and_iterate(self, state):
        retval = self.pipeline.set_state(state)
        if not retval:
            self.warn('Changing state to %s failed' %
                    gst.element_state_get_name(state))
        gobject.idle_add(self.pipeline.iterate)

    def create_pipeline(self):
        raise NotImplementedError
    
    def setup_pipeline(self):
        self.pipeline.set_name('pipeline-' + self.component_name)
        sig_id = self.pipeline.connect('error', self.pipeline_error_cb)
        self.pipeline_signals.append(sig_id)
        sig_id = self.pipeline.connect('state-change', self.pipeline_state_change_cb)
        self.pipeline_signals.append(sig_id)
        #sig_id = self.pipeline.connect('deep-notify', gstutils.verbose_deep_notify_cb)
        #self.pipeline_signals.append(sig_id)

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
            self.msg('property %s set to %r' %
                     (prop_name, properties[prop_name]))
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
        
    def remote_register(self):
        if not self.hasPerspective():
            self.warn('We are not ready yet, waiting 250 ms')
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

class ParseLaunchComponent(BaseComponent):
    def __init__(self, name, sources, pipeline_string=''):
        self.pipeline_string = pipeline_string
        BaseComponent.__init__(self, name, sources)
        
    def setup_pipeline(self):
        self.create_pipeline()
        BaseComponent.setup_pipeline(self)
        
    def create_pipeline(self):
        pipeline = self.pipeline_string
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

        self.msg('pipeline for %s is %s' % (self.component_name, pipeline))
        
        try:
            self.pipeline = gst.parse_launch(pipeline)
        except gobject.GError, e:
            raise errors.PipelineParseError, e

