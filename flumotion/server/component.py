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
# Foundation, Inc., 59 Temple Street #330, Boston, MA 02111-1307, USA.

import os
import socket

import gst
import gobject
from twisted.internet import reactor
from twisted.spread import pb

from flumotion.server import interfaces
from flumotion.twisted import errors, pbutil
from flumotion.utils import log, gstutils

class ComponentFactory(pbutil.ReconnectingPBClientFactory):
    __super_init = pbutil.ReconnectingPBClientFactory.__init__
    __super_login = pbutil.ReconnectingPBClientFactory.startLogin
    def __init__(self, component):
        self.__super_init()
        self.interfaces = getattr(component, '__remote_interfaces__', ())
        self.view = ComponentView(component)
        
    def login(self, username):
        self.__super_login(pbutil.Username(username),
                           self.view,
                           pb.IPerspective,
                           *self.interfaces)
        
    def gotPerspective(self, perspective):
        self.view.cb_gotPerspective(perspective)

class ComponentView(pb.Referenceable, log.Loggable):
    'Implements a view on a local component'
    logCategory = 'componentview'

    def __init__(self, component):
        self.comp = component
        self.comp.connect('state-changed', self.component_state_changed_cb)
        self.comp.connect('error', self.component_error_cb)
        self.comp.connect('log', self.component_log_cb)
        
        self.remote = None # the perspective we have on the other side (?)
        
    ### Loggable methods
    def logFunction(self, arg):
        return self.comp.get_name() + ':' + arg

    # call function on remote perspective in controller (?)
    def callRemote(self, name, *args, **kwargs):
        if not self.hasPerspective():
            self.debug('skipping %s, no perspective' % name)
            return

        def errback(reason):
            self.warning('stopping pipeline because of %s' % reason)
            self.comp.pipeline_stop()
            
        cb = self.remote.callRemote(name, *args, **kwargs)
        cb.addErrback(errback)

    def cb_gotPerspective(self, perspective):
        self.remote = perspective
        
    def hasPerspective(self):
        return self.remote != None

    def getIP(self):
        assert self.remote
        peer = self.remote.broker.transport.getPeer()
        return socket.gethostbyname(peer[1])

    def component_log_cb(self, component, args):
        self.callRemote('log', *args)
        
    def component_error_cb(self, component, element_path, message):
        self.callRemote('error', element_path, message)
        
    def component_state_changed_cb(self, component, feed, state):
        self.callRemote('stateChanged', feed, state)

    ### Referenceable remote methods which can be called from controller
    def remote_link(self, sources, feeds):
        self.comp.link(sources, feeds)

    def remote_getElementProperty(self, element_name, property):
        return self.comp.get_element_property(element_name, property)
        
    def remote_setElementProperty(self, element_name, property, value):
        self.comp.set_element_property(element_name, property, value)

    def remote_getUIEntry(self):
        return self.comp.getUIEntry()
    
    def remote_play(self):
        self.comp.play()
        
    def remote_stop(self):
        self.comp.stop()
        self.remote.broker.transport.loseConnection()
        reactor.stop()
        
    def remote_pause(self):
        self.comp.pause()

    def remote_register(self):
        if not self.hasPerspective():
            self.warning('We are not ready yet, waiting 250 ms')
            reactor.callLater(0.250, self.remote_register)
            return

        return {'ip' : self.getIP(),
                'pid' :  os.getpid(), 
                'sources' : self.comp.get_sources(),
                'feeds' : self.comp.get_feeds(),
                'elements': self.comp.get_element_names() }
    
    def remote_getFreePorts(self, feeds):
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

    def remote_reloadComponent(self):
        """Reload modules in the component."""
        import sys
        from twisted.python.rebuild import rebuild
        # reload ourselves first
        rebuild(sys.modules[__name__])

        # now rebuild relevant modules
        import flumotion.utils
        rebuild(sys.modules['flumotion.utils'])
        try:
            flumotion.utils.reload()
        except SyntaxError, msg:
            raise flumotion.twisted.errors.ReloadSyntaxError(msg)
        self._reloaded()

    # separate method so it runs the newly reloaded one :)
    def _reloaded(self):
        self.info('reloaded module code for %s' % __name__)


class IFlumotionComponent:
    pass

class DirectoryProvider:
    def __init__(self):
        self.files = []
        
    def setFiles(self, files):
        self.files = files

    def getFiles(self, filename):
        return self.files[filename]

    def getUIEntry(self):
        for filename, file in self.files.items():
            if file.isType('GUI'):
                break
        else:
            return

        data = open(filename).read()

        return data

class BaseComponent(gobject.GObject, log.Loggable, DirectoryProvider):
    """I am the base class for all Flumotion components."""
    __gsignals__ = {
        'state-changed': (gobject.SIGNAL_RUN_FIRST, None, (str, object)),
        'error':         (gobject.SIGNAL_RUN_FIRST, None, (str, str)),
        'log':         (gobject.SIGNAL_RUN_FIRST, None, (object,)),
        }
    logCategory = 'basecomponent'
    __remote_interfaces__ = interfaces.IBaseComponent,
    
    def __init__(self, name, sources, feeds):
        self.__gobject_init__()
        DirectoryProvider.__init__(self)
        
        self.component_name = name
        self.sources = sources
        self.feeds = feeds
        self.pipeline = None
        self.pipeline_signals = []
        self.files = []
        
        self.setup_pipeline()

    ### Loggable methods
    def logFunction(self, arg):
        return self.get_name() + ' ' + arg

    ### GObject methods
    def emit(self, name, *args):
        if 'uninitialized' in str(self):
            self.warning('Uninitialized object!')
            #self.__gobject_init__()
        else:
            gobject.GObject.emit(self, name, *args)
        
    ### BaseComponent methods
    def get_name(self):
        return self.component_name
    
    def get_sources(self):
        return self.sources
    
    def get_feeds(self):
        return self.feeds

    def restart(self):
        self.debug('restarting')
        self.cleanup()
        self.setup_pipeline()
       
    def set_state_and_iterate(self, state):
        retval = self.pipeline.set_state(state)
        if not retval:
            self.warning('Changing state to %s failed' %
                    gst.element_state_get_name(state))
        gobject.idle_add(self.pipeline.iterate)

    def get_pipeline(self):
        return self.pipeline

    def create_pipeline(self):
        raise NotImplementedError, "subclass must implement create_pipeline"
        
    def _pipeline_error_cb(self, object, element, error, arg):
        self.debug('element %s error %s %s' % (element.get_path_string(), str(error), repr(arg)))
        self.emit('error', element.get_path_string(), error.message)
        #self.restart()
     
    def setup_pipeline(self):
        self.pipeline.set_name('pipeline-' + self.get_name())
        sig_id = self.pipeline.connect('error', self._pipeline_error_cb)
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
        
        retval = self.pipeline.set_state(gst.STATE_NULL)
        if not retval:
            self.warning('Setting pipeline to NULL failed')
        
    def setup_sources(self, sources):
        if not self.pipeline:
            raise NotReadyError('No pipeline')
        
        # Setup all sources
        for source_name, source_host, source_port in sources:
            self.debug('Going to connect to %s (%s:%d)' % (source_name, source_host, source_port))
            source = self.pipeline.get_by_name(source_name)
            assert source, 'No source element named %s in pipeline' % source_name
            assert isinstance(source, gst.Element)
            
            source.set_property('host', source_host)
            source.set_property('port', source_port)
            source.set_property('protocol', 'gdp')
            
    def feed_state_change_cb(self, element, old, state, feed):
        # also called by subclasses
        self.debug('state-changed %s %s' % (element.get_path_string(),
                                            gst.element_state_get_name(state)))
        self.emit('state-changed', feed, state)

    def setup_feeds(self, feeds):
        if not self.pipeline:
            raise errors.NotReadyError('No pipeline')
        
        # Setup all feeds
        for name, host, port in feeds:
            self.debug('Going to listen on %s (%s:%d)' % (name, host, port))
            feed = self.pipeline.get_by_name(name)
            feed.connect('state-change', self.feed_state_change_cb, name)
            
            assert feed, 'No feed element named %s in pipeline' % name
            assert isinstance(feed, gst.Element)
            
            feed.set_property('host', host)
            feed.set_property('port', port)
            feed.set_property('protocol', 'gdp')

    def cleanup(self):
        self.debug("cleaning up")
        
        assert self.pipeline != None

        if self.pipeline.get_state() != gst.STATE_NULL:
            self.debug('Pipeline was in state %s, changing to NULL' %
                     gst.element_state_get_name(self.pipeline.get_state()))
            self.pipeline.set_state(gst.STATE_NULL)
                
        # Disconnect signals
        map(self.pipeline.disconnect, self.pipeline_signals)
        self.pipeline = None
        self.pipeline_signals = []

    def play(self):
        self.debug('Playing')
        self.pipeline_play()

    def stop(self):
        self.debug('Stopping')
        self.pipeline_stop()

    def pause(self):
        self.debug('Pausing')
        self.pipeline_pause()
                
    def link(self, sources, feeds):
        self.setup_sources(sources)
        self.setup_feeds(feeds)
        
        func = getattr(self, 'link_setup', None)
        if func:
            func(sources, feeds)
            
        self.pipeline_play()

    def get_element_names(self):
        'Return the names of all elements in the GStreamer pipeline.'
        pipeline = self.get_pipeline()
        return [element.get_name() for element in pipeline.get_list()]
        
    def get_element_property(self, element_name, property):
        'Gets a property of an element in the GStreamer pipeline.'
        self.debug("%s: getting property %s of element %s" % (self.get_name(), property, element_name))
        element = self.pipeline.get_by_name(element_name)
        if not element:
            msg = "Element '%s' does not exist" % element_name
            self.warning(msg)
            raise errors.PropertyError(msg)
        
        self.debug('getting property %s on element %s' % (property, element_name))
        try:
            value = element.get_property(property)
        except (ValueError, TypeError):
            msg = "Property '%s' on element '%s' does not exist" % (property, element_name)
            self.warning(msg)
            raise errors.PropertyError(msg)

        return value

    def set_element_property(self, element_name, property, value):
        'Sets a property on an element in the GStreamer pipeline.'
        self.debug("%s: setting property %s of element %s to %s" % (self.get_name(), property, element_name, value))
        element = self.pipeline.get_by_name(element_name)
        if not element:
            msg = "Element '%s' does not exist" % element_name
            self.warning(msg)
            raise errors.PropertyError(msg)

        self.debug('setting property %s on element %r to %s' %
                   (property, element_name, value))
        gstutils.gobject_set_property(element, property, value)
gobject.type_register(BaseComponent)
    
class ParseLaunchComponent(BaseComponent):
    'A component using gst-launch syntax'
    SOURCE_TMPL = 'tcpclientsrc'
    FEED_TMPL = 'tcpserversink buffers-max=500 buffers-soft-max=450 recover-policy=1'
    def __init__(self, name, sources, feeds, pipeline_string=''):
        self.pipeline_string = pipeline_string
        BaseComponent.__init__(self, name, sources, feeds)

    ### BaseComponent methods
    def setup_pipeline(self):
        pipeline = self.parse_pipeline(self.pipeline_string)
        try:
            self.pipeline = gst.parse_launch(pipeline)
        except gobject.GError, e:
            raise errors.PipelineParseError(pipeline)

        BaseComponent.setup_pipeline(self)

    ### ParseLaunchComponent methods
    def parse_tmpl(self, pipeline, parts, template, sign, format):
        assert pipeline != ''
        if len(parts) == 1:
            part_name = parts[0]
            if pipeline.find(part_name) != -1:
                pipeline = pipeline.replace(sign + part_name, '%s name=%s' % (template, part_name))
            else:
                pipeline = format % {'tmpl': template, 'name': part_name, 'pipeline': pipeline}
        else:
            for part in parts:
                if ' ' in part:
                    raise TypeError, "spaces not allowed in parts"
            
                part_name = sign + part
                if pipeline.find(part_name) == -1:
                    raise TypeError, "%s needs to be specified in the pipeline" % part_name
            
                pipeline = pipeline.replace(part_name, '%s name=%s' % (template, part))
        return pipeline
        
    def parse_pipeline(self, pipeline):
        self.debug('Creating pipeline, template is %s' % pipeline)
        
        sources = self.get_sources()
        if pipeline == '' and not sources:
            raise TypeError, "Need a pipeline or a source"

        need_sink = True
        if pipeline == '':
            assert sources
            pipeline = 'fakesink signal-handoffs=1 silent=1 name=sink'
            need_sink = False
        elif pipeline.find('name=sink') != -1:
            need_sink = False
            
        feeds = self.get_feeds()

        self.debug('sources=%s, feeds=%s' % (sources, feeds))
        pipeline = self.parse_tmpl(pipeline, sources, self.SOURCE_TMPL, '@',
                                 '%(tmpl)s name=%(name)s ! %(pipeline)s') 
        pipeline = self.parse_tmpl(pipeline, feeds, self.FEED_TMPL, ':',
                                 '%(pipeline)s ! %(tmpl)s name=%(name)s') 
        
        self.debug('pipeline for %s is %s' % (self.get_name(), pipeline))
        
        return pipeline

