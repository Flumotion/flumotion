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

from flumotion.twisted import errors, pbutil
from flumotion.utils import log, gstutils

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
        self.component.gotPerspective(perspective)

class BaseComponent(pb.Referenceable):
    def __init__(self, name, sources, feeds):
        self.component_name = name
        self.sources = sources
        self.feeds = feeds
        self.remote = None # the perspective we have on the other side (?)
        self.pipeline = None
        self.pipeline_signals = []

        # Prefix our login name with the name of the component
        self.username = '%s_%s' % (self.getKind(), name)
        self.factory = ClientFactory(self)
        self.factory.login(self.username)

    def msg(self, *args):
        log.msg(self.component_name, *args)

    def warn(self, *args):
        log.warning(self.component_name, *args)

    def gotPerspective(self, perspective):
        self.remote = perspective
        
    def hasPerspective(self):
        return self.remote != None

    def getKind(self):
        assert hasattr(self, 'kind')
        return self.kind

    def getSources(self):
        return self.sources
    
    def getFeeds(self):
        return self.feeds

    def getIP(self):
        assert self.remote
        peer = self.remote.broker.transport.getPeer()
        return socket.gethostbyname(peer[1])

    def callRemote(self, name, *args, **kwargs):
        if not self.hasPerspective():
            self.msg('skipping %s, no perspective' % name)
            return

        def errback(reason):
            self.warn('stopping pipeline because of %s' % reason)
            self.pipeline_stop()
            
        cb = self.remote.callRemote(name, *args, **kwargs)
        cb.addErrback(errback)

    def restart(self):
        self.msg('restarting')
        self.cleanup()
        self.setup_pipeline()
        
    def pipeline_error_cb(self, object, element, error, arg):
        self.msg('element %s error %s %s' % (element.get_path_string(), str(error), repr(arg)))
        self.callRemote('error', element.get_path_string(), error.message)

        #self.restart()
        
    def feed_state_change_cb(self, element, old, state, feed):
        self.msg('state-changed %s %s' % (element.get_path_string(),
                                          gst.element_state_get_name(state)))
        self.callRemote('stateChanged', feed, old, state)

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
        
        sig_id = self.pipeline.connect('deep-notify',
                                       gstutils.verbose_deep_notify_cb, self)
        self.pipeline_signals.append(sig_id)

    def pipeline_pause(self):
        self.set_state_and_iterate(gst.STATE_PAUSED)
        
    def pipeline_play(self):
        self.set_state_and_iterate(gst.STATE_PLAYING)

    def pipeline_stop(self):
        if not self.pipeline:
            return
        
        self.set_state_and_iterate(gst.STATE_NULL)
        
    def setup_feeds(self, feeds):
        if not self.pipeline:
            raise errors.NotReadyError('No pipeline')
        
        # Setup all feeds sources
        for name, host, port in feeds:
            self.msg('Going to listen on %s (%s:%d)' % (name, host, port))
            feed = self.pipeline.get_by_name(name)
            feed.connect('state-change', self.feed_state_change_cb, name)
            
            assert feed, 'No feed element named %s in pipeline' % name
            assert isinstance(feed, gst.Element)
            
            feed.set_property('host', host)
            feed.set_property('port', port)
            feed.set_property('protocol', 'gdp')

    def setup_sources(self, sources):
        if not self.pipeline:
            raise NotReadyError('No pipeline')
        
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
        
        self.setup_pipeline()
        
        return {'ip' : self.getIP(),
                'pid' :  os.getpid(), 
                'sources' : self.getSources(),
                'feeds' : self.getFeeds() }
    
    def remote_get_free_ports(self, feeds):
        retval = []
        ports = {}
        free_port = gstutils.get_free_port(start=5500)
        for name, host, port in feeds:
            if port == None:
                port = free_port
                free_port += 1
            ports[name] = port
            retval.append((name, host, port))
            
        return retval, ports

    def remote_play(self):
        self.msg('Playing')
        self.pipeline_play()
        
    def remote_stop(self):
        self.msg('Stopping')
        self.pipeline_stop()
        self.remote.broker.transport.loseConnection()
        reactor.stop()
        
    def remote_pause(self):
        self.pipeline_pause()

class ParseLaunchComponent(BaseComponent):
    def __init__(self, name, sources, feeds, pipeline_string=''):
        self.pipeline_string = pipeline_string
        BaseComponent.__init__(self, name, sources, feeds)
        
    def setup_pipeline(self):
        self.create_pipeline()
        BaseComponent.setup_pipeline(self)

    def do_sources(self, sources, pipeline):
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
        return pipeline

    def do_feeds(self, feeds, pipeline):
        element = 'tcpserversink'
        sign = ':'
        
        if len(feeds) == 1:
            feed_name = feeds[0]
            if pipeline.find(feed_name) != -1:
                pipeline = pipeline.replace(sign + feed_name, '%s name=%s' % (element, feed_name))
            else:
                pipeline = '%s ! %s name=%s' % (pipeline, element, feed_name)
        else:
            for feed in self.feeds:
                if ' ' in feed:
                    raise TypeError, "spaces not allowed in sources"
            
                feed_name = sign + feed
                if pipeline.find(feed_name) == -1:
                    raise TypeError, "%s needs to be specified in the pipeline" % feed_name
            
                pipeline = pipeline.replace(feed_name, '%s name=%s' % (element, feed))
        return pipeline
        
    def create_pipeline(self):
        pipeline = self.pipeline_string
        self.msg('Creating pipeline, template is %s' % pipeline)
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
            
        feeds = self.getFeeds()

        self.msg('sources=%s, feeds=%s' % (sources, feeds))
        pipeline = self.do_sources(sources, pipeline)
        pipeline = self.do_feeds(feeds, pipeline)

        self.msg('pipeline for %s is %s' % (self.component_name, pipeline))
        
        try:
            self.pipeline = gst.parse_launch(pipeline)
        except gobject.GError, e:
            raise errors.PipelineParseError('foo') #str(e))
