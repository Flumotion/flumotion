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

import gst

from twisted.cred import portal
from twisted.internet import reactor
from twisted.spread import pb

from flumotion.server import admin
from flumotion.twisted import errors, pbutil
from flumotion.utils import gstutils, log

class Dispatcher:
    __implements__ = portal.IRealm
    def __init__(self, controller, admin):
        self.controller = controller
        self.admin = admin
        
    def requestAvatar(self, avatarID, mind, *interfaces):
        p = None
        if avatarID == 'admin':
            p = self.admin.getPerspective()
        else:
            component_type, avatarID = avatarID.split('_', 1)
            if self.controller.hasComponent(avatarID):
                raise TypeError, "client %s already connected" % avatarID
        
            p = self.controller.getPerspective(component_type, avatarID)

        #msg("returning Avatar(%s): %s" % (avatarID, p))
        if not p:
            raise ValueError, "no perspective for '%s'" % avatarID

        # schedule a perspective attached
        reactor.callLater(0, p.attached, mind)
        
        # return a deferred with interface, aspect, and logout function 
        return (pb.IPerspective, p,
                lambda p=p,mind=mind: p.detached(mind))

class Options:
    """dummy class for storing controller side options of a component"""

class ComponentPerspective(pbutil.NewCredPerspective):
    """Perspective all components will have on the controller side"""
    def __init__(self, controller, username):
        self.controller = controller
        self.username = username
        self.state = gst.STATE_NULL
        self.options = Options()
        self.listen_ports = {}
        self.started = False
        self.starting = False
        
    def __repr__(self):
        return '<%s %s in state %s>' % (self.__class__.__name__,
                                        self.getName(),
                                        gst.element_state_get_name(self.state))

    msg = lambda s, *a: log.msg('controller', *(s.getName(),) + a)
    warn = lambda s, *a: log.warn('controller', *(s.getName(),) + a)
    error = lambda s, *a: log.error('controller', *(s.getName(),) + a)

    def getTransportPeer(self):
        return self.mind.broker.transport.getPeer()

    def getSources(self):
        return self.options.sources
    
    def getFeeds(self, longname=False):
        if longname:
            return map(lambda feed:
                       self.getName() + ':' + feed, self.options.feeds)
        else:
            return self.options.feeds

    def getRemoteControllerIP(self):
        return self.options.ip

    def getName(self):
        return self.username

    def getListenHost(self):
        return self.getTransportPeer()[1]

    # This method should ask the component if the port is free
    def getListenPort(self, feed):
        if feed.find(':') != -1:
            feed = feed.split(':')[1]

        assert self.listen_ports.has_key(feed), self.listen_ports
        assert self.listen_ports[feed] != -1, self.listen_ports
        return self.listen_ports[feed]

    def callRemote(self, name, *args, **kwargs):
        self.msg('Calling remote method %s%r' % (name, args))
        try:
            return self.mind.callRemote(name, *args, **kwargs)
        except pb.DeadReferenceError :
            self.mind = None
            self.detached()
            return

    def cb_register(self, options, cb):
        for key, value in options.items():
            setattr(self.options, key, value)
        self.options.dict = options
        
        self.controller.componentRegistered(self)

    def cb_checkAll(self, failure):
        self.error(str(failure))
        self.callRemote('stop')
        return None
                
    def cb_checkPipelineError(self, failure):
        failure.trap(errors.PipelineParseError)
        self.error('Invalid pipeline for component')
        self.callRemote('stop')
        return None

    def attached(self, mind):
        #msg('%s attached, calling register()' % self.getName())
        self.mind = mind
        
        cb = self.callRemote('register')
        cb.addCallback(self.cb_register, cb)
        cb.addErrback(self.cb_checkPipelineError)
        cb.addErrback(self.cb_checkAll)
        
    def detached(self, mind=None):
        self.msg('detached')
        name = self.getName()
        if self.controller.hasComponent(name):
            self.controller.removeComponent(self)

    def setState(self, element, property, value):
        if not element in self.options.elements:
            raise TypeError, 'not such an element: %s' % element
        
        # XXX: Check property name
        # XXX: Check propery value
        return self.callRemote('set_element_property', element, property, value)
        
    def getState(self, element, property):
        # XXX: Check element name
        # XXX: Check property name
        return self.callRemote('get_element_property', element, property)

    def perspective_log(self, *msg):
        self.msg(*msg)
        
    def perspective_stateChanged(self, feed, state):
        self.msg('stateChanged :%s %s' % (feed,
                                          gst.element_state_get_name(state)))
        
        self.state = state
        if self.state == gst.STATE_PLAYING:
            self.msg('%s is now playing' % feed)

        if self.getFeeds():
            self.controller.startPendingComponents(self, feed)
            
    def perspective_error(self, element, error):
        self.error('error element=%s string=%s' % (element, error))
        
        self.controller.removeComponent(self)

class ProducerPerspective(ComponentPerspective):
    """Perspective for producer components"""
    kind = 'producer'
    def cb_getFreePorts(self, (feeds, ports)):
        self.listen_ports = ports
        cb = self.callRemote('listen', feeds)
        cb.addErrback(self.cb_checkAll)
        
    def listen(self, feeds):
        """starts the remote methods listen"""

        cb = self.callRemote('get_free_ports', feeds)
        cb.addCallbacks(self.cb_getFreePorts, self.cb_checkAll)

class ConverterPerspective(ComponentPerspective):
    """Perspective for converter components"""
    kind = 'converter'

    def start(self, sources, feeds):
        def cb_getFreePorts((feeds, ports)):
            self.listen_ports = ports
            cb = self.callRemote('start', sources, feeds)
            cb.addErrback(self.cb_checkAll)
            
        """starts the remote methods start"""
        cb = self.callRemote('get_free_ports', feeds)
        cb.addCallbacks(cb_getFreePorts, self.cb_checkAll)
        
class StreamerPerspective(ComponentPerspective):
    """Perspective for streamer components"""
    kind = 'streamer'
            
    def getListenHost(self):
        "Should never be called, a Streamer does not accept incoming components"
        raise AssertionError
    
    def getListenPort(self):
        "Should never be called, a Streamer does not accept incoming components"
        raise AssertionError

    def connect(self, sources):
        """starts the remote methods connect"""
        self.msg('Calling remote method connect(%s)' % sources)
        cb = self.mind.callRemote('connect', sources)
        cb.addErrback(self.cb_checkAll)
        
STATE_NULL     = 0
STATE_STARTING = 1
STATE_READY    = 2

class Feed:
    def __init__(self, name):
        self.name = name
        self.dependencies = []
        self.state = STATE_NULL
        self.component = None

    def setComponent(self, component):
        self.component = component
        
    def addDependency(self, func, *args):
        self.dependencies.append((func, args))

    def setReady(self):
        self.state = STATE_READY
        for func, args in self.dependencies:
            func(*args)
        self.dependencies = []

    def getName(self):
        return self.name

    def getListenHost(self):
        return self.component.getListenHost()

    def getListenPort(self):
        return self.component.getListenPort(self.name)
    
    def __repr__(self):
        return '<Feed %s state=%d>' % (self.name, self.state)
    
class FeedManager:
    def __init__(self):
        self.feeds = {}

    def hasFeed(self, feedname):
        if feedname.find(':') == -1:
            feedname += ':default'

        return self.feeds.has_key(feedname)
    
    def __getitem__(self, key):
        if key.find(':') == -1:
            key += ':default'

        return self.feeds[key]
        
    def getFeed(self, feedname):
        return self[feedname]
    
    def addFeeds(self, component):
        name = component.getName()
        feeds = component.getFeeds(True)
        for feedname in feeds:
            longname = name + ':' + feedname
            if not self.feeds.has_key(feedname):
                self.feeds[feedname] = Feed(feedname)
            self.feeds[feedname].setComponent(component)
            
    def isFeedReady(self, feedname):
        if not self.hasFeed(feedname):
            return False

        feed = self[feedname]

        return feed.state == STATE_READY
    
    def feedReady(self, feedname): 
        # If we don't specify the feed
        log.msg('controller', 'feed %s ready' % (feedname))

        if not self.feeds.has_key(feedname):
            self.warn('FIXME: no feed called: %s' % feedname)
            return
        
        feed = self.feeds[feedname]
        feed.setReady()
            
    def dependOnFeed(self, feedname, func, *args):
        # If we don't specify the feed
        if feedname.find(':') == -1:
            feedname += ':default'

        if not self.feeds.has_key(feedname):
            self.feeds[feedname] = Feed(feedname)
            
        feed = self.feeds[feedname]
        if feed.state != STATE_READY:
            feed.addDependency(func, *args)
        else:
            func(*args)

class Controller(pb.Root):
    def __init__(self):
        self.components = {}
        self.feed_manager = FeedManager()
        self.admin = None
        
        self.last_free_port = 5500

    def setAdmin(self, admin):
        self.admin = admin
        
    def getPerspective(self, type, *args):
        """Creates a new perspective for a component
        @type type:      string
        @param type:     type of the component, one of: producer, converter and streamer
        @type args:      tuple
        @param username: extra arguments sent to the perspective class
        @rtype:          ComponentPerspective
        @returns:        the perspective for the component"""

        if type == 'producer':
            klass = ProducerPerspective
        elif type == 'converter':
            klass = ConverterPerspective
        elif type == 'streamer':
            klass = StreamerPerspective
        else:
            raise AssertionError

        component = klass(self, *args)
        self.addComponent(component)
        return component

    def isLocalComponent(self, component):
        # TODO: This could be a lot smarter
        host = component.getTransportPeer()[1]
        if host == '127.0.0.1':
            return True
        else:
            return False

    def isComponentStarted(self, component_name):
        if not self.hasComponent(component_name):
            return False

        component = self.components[component_name]

        return component.started == True
    
    def getComponent(self, name):
        """retrieves a new component
        @type name:  string
        @param name: name of the component
        @rtype:      component
        @returns:    the component"""

        if not self.hasComponent(name):
            raise KeyError, name
        
        return self.components[name]
    
    def hasComponent(self, name):
        """adds a new component
        @type name:  string
        @param name: name of the component
        @rtype:      boolean
        @returns:    True if a component with that name is registered, otherwise False"""
        
        return self.components.has_key(name)
    
    def addComponent(self, component):
        """adds a component
        @type component: component
        @param component: the component"""

        component_name = component.getName()
        if self.hasComponent(component_name):
            raise KeyError, component_name
            
        self.components[component_name] = component
        
    def removeComponent(self, component):
        """removes a component
        @type component: component
        @param component: the component"""

        component_name = component.getName()
        if not self.hasComponent(component_name):
            raise KeyError, component_name

        del self.components[component_name]
        if self.admin:
            self.admin.componentRemoved(component)

    def getSourceComponents(self, component):
        """Retrives the source components for component

        @type component:  component
        @param component: the component
        @rtype:           tuple of with 3 items
        @returns:         name, hostname and port"""

        assert not isinstance(component, ProducerPerspective)

        peernames = component.getSources()
        retval = []
        for peername in peernames:
            feed = self.feed_manager.getFeed(peername)
            feedname = feed.getName()
            if feedname.endswith(':default'):
                feedname = feedname[:-8]

            host = feed.getListenHost()
            if (not self.isLocalComponent(component) and host == '127.0.0.1'):
                host = component.getRemoteControllerIP()

            retval.append((feedname, host,feed.getListenPort()))
        return retval

    def getFeedsForComponent(self, component):
        """Retrives the source components for component

        @type component:  component
        @param component: the component
        @rtype:           tuple of with 3 items
        @returns:         name, hostname and port"""

        assert isinstance(component, ComponentPerspective), component

        host = component.getListenHost()
        feednames = component.getFeeds()
        retval = []
        for feedname in feednames:
            if self.isLocalComponent(component):
                port = gstutils.get_free_port(self.last_free_port)
                self.last_free_port = port + 1
            else:
                port = None

            retval.append((feedname, host, port))
        return retval

    def producerStart(self, producer):
        assert isinstance(producer, ProducerPerspective)

        feeds = self.getFeedsForComponent(producer)
        producer.listen(feeds)

    def converterStart(self, converter):
        assert isinstance(converter, ConverterPerspective)
        
        sources = self.getSourceComponents(converter)
        feeds = self.getFeedsForComponent(converter)
        converter.start(sources, feeds)
            
    def streamerStart(self, streamer):
        assert isinstance(streamer, StreamerPerspective)
        
        sources = self.getSourceComponents(streamer)
        streamer.connect(sources)
        
    def componentStart(self, component):
        component.msg('Starting')
        assert isinstance(component, ComponentPerspective)
        assert component != ComponentPerspective

        if isinstance(component, ProducerPerspective):
            self.producerStart(component)
        elif isinstance(component, ConverterPerspective):
            self.converterStart(component)
        elif isinstance(component, StreamerPerspective):
            self.streamerStart(component)

    def maybeComponentStart(self, component):
        component.msg('maybeComponentStart')
        
        for source in component.getSources():
            if not self.feed_manager.isFeedReady(source):
                component.msg('source %s is not ready' % (source))
                return

        if component.starting:
            return
        
        component.starting = True
        self.componentStart(component)
        
    def componentRegistered(self, component):
        component.msg('in componentRegistered')
        if self.admin:
            self.admin.componentAdded(component)
        self.feed_manager.addFeeds(component)

        sources = component.getSources()
        if not sources:
            component.msg('no sources, starting immediatelly')
            self.componentStart(component)
            return
        else:
            for source in sources:
                self.feed_manager.dependOnFeed(source,
                                               self.maybeComponentStart,
                                               component)
                
    def startPendingComponents(self, component, feed):
        feedname = component.getName() + ':' + feed
        self.feed_manager.feedReady(feedname)

class ControllerServerFactory(pb.PBServerFactory):
    """A Server Factory with a Dispatcher and a Portal"""
    def __init__(self):
        self.controller = Controller()
        self.admin = admin.Admin(self.controller)
        self.controller.setAdmin(self.admin)
        
        self.dispatcher = Dispatcher(self.controller, self.admin)
        checker = pbutil.ReallyAllowAnonymousAccess()
        
        self.portal = portal.Portal(self.dispatcher, [checker])
        pb.PBServerFactory.__init__(self, self.portal)

    
    def __repr__(self):
        return '<ControllerServerFactory>'
