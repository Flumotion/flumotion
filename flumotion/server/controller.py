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

"""Controller implementation and related classes

API Stability: semi-stable

Maintainer: U{Johan Dahlin <johan@fluendo.com>}
"""

__all__ = ['ComponentPerspective', 'Controller', 'ControllerServerFactory']

import gst

from twisted.internet import reactor
from twisted.python import components
from twisted.spread import pb

from flumotion.server import admin, interfaces
from flumotion.twisted import errors, pbutil, portal
from flumotion.utils import gstutils, log

# an internal class
class Dispatcher(log.Loggable):
    """
    I implement L{portal.IRealm}.
    I make sure that when a L{pb.Avatar} is requested through me, the
    Avatar/perspective being returned knows about the mind (client) requesting
    the Avatar.
    """
    
    __implements__ = portal.IRealm

    logCategory = 'dispatcher'

    def __init__(self, controller, admin):
        """
        @type controller: L{server.controller.Controller}
        @type admin:      L{server.admin.Admin}
        """
        self.controller = controller
        self.admin = admin

    # requestAvatar gets called through ClientFactory.login()
    # An optional second argument can be passed to login, which should be
    # a L{twisted.spread.flavours.Referenceable}
    # A L{twisted.spread.pb.RemoteReference} to it is passed to
    # requestAvatar as mind.
    # So in short, the mind is a reference to the client passed in login()
    # on the peer, allowing any object that has the mind to call back
    # to the piece that called login(),
    # which in our case is a component or an admin.
    def requestAvatar(self, avatarID, mind, *ifaces):

        if not pb.IPerspective in ifaces:
            raise errors.NoPerspectiveError(avatarID)

        p = None
        if interfaces.IBaseComponent in ifaces:
            p = self.controller.getPerspective(avatarID)
        elif interfaces.IAdminComponent in ifaces:
            p = self.admin.getPerspective()

        if not p:
            raise errors.NoPerspectiveError(avatarID)

        self.debug("returning Avatar: id %s, perspective %s" % (avatarID, p))
        
        # schedule a perspective attached for after this function
        reactor.callLater(0, p.attached, mind)
        
        # return a tuple of interface, aspect, and logout function 
        return (pb.IPerspective, p,
                lambda p=p,mind=mind: p.detached(mind))

class Options:
    """dummy class for storing controller side options of a component"""

class ComponentPerspective(pb.Avatar, log.Loggable):
    """Controller side perspective of components"""

    logCategory = 'controller'

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

    def logFunction(self, arg):
        return self.getName() + ': ' + arg

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

    #FIXME: this is not a referenceable so rename callRemote
    def callRemote(self, name, *args, **kwargs):
        self.debug('Calling remote method %s%r' % (name, args))
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
        try:
            self.error(str(failure))
        except errors.SystemError, e:
            print 'ERROR:', e

        self.callRemote('stop')
        return None
                
    def cb_checkPipelineError(self, failure):
        failure.trap(errors.PipelineParseError)
        self.error('Invalid pipeline for component')
        self.callRemote('stop')
        return None

    def attached(self, mind):
        #debug('%s attached, calling register()' % self.getName())
        self.mind = mind
        
        cb = self.callRemote('register')
        cb.addCallback(self.cb_register, cb)
        cb.addErrback(self.cb_checkPipelineError)
        cb.addErrback(self.cb_checkAll)
        
    def detached(self, mind=None):
        self.debug('detached')
        name = self.getName()
        if self.controller.hasComponent(name):
            self.controller.removeComponent(self)

    def stop(self):
        cb = self.callRemote('stop')
        cb.addErrback(lambda x: None)
        
    def setState(self, element, property, value):
        if not element in self.options.elements:
            raise errors.PropertyError('not such an element: %s' % element)
        return self.callRemote('setElementProperty', element, property, value)
        
    def getState(self, element, property):
        return self.callRemote('getElementProperty', element, property)

    def perspective_log(self, *msg):
        log.debug(self.getName(), *msg)
        
    def perspective_stateChanged(self, feed, state):
        self.debug('stateChanged: %s %s' % (feed, gst.element_state_get_name(state)))
        
        self.state = state
        if self.state == gst.STATE_PLAYING:
            self.info('is now playing')

        if self.getFeeds():
            self.controller.startPendingComponents(self, feed)
            
    def perspective_error(self, element, error):
        self.error('error element=%s string=%s' % (element, error))
        
        self.controller.removeComponent(self)

    def link(self, sources, feeds):
        def cb_getFreePorts((feeds, ports)):
            self.listen_ports = ports
            cb = self.callRemote('link', sources, feeds)
            cb.addErrback(self.cb_checkAll)

        if feeds:
            cb = self.callRemote('getFreePorts', feeds)
            cb.addCallbacks(cb_getFreePorts, self.cb_checkAll)
        else:
            cb = self.callRemote('link', sources, [])
            cb.addErrback(self.cb_checkAll)

class Feed:
    def __init__(self, name):
        self.name = name
        self.dependencies = []
        self.ready = False
        self.component = None

    def setComponent(self, component):
        self.component = component
        
    def addDependency(self, func, *args):
        self.dependencies.append((func, args))

    def setReady(self):
        self.ready = True
        for func, args in self.dependencies:
            func(*args)
        self.dependencies = []

    def isReady(self):
        return self.ready
    
    def getName(self):
        return self.name

    def getListenHost(self):
        return self.component.getListenHost()

    def getListenPort(self):
        return self.component.getListenPort(self.name)
    
    def __repr__(self):
        return '<Feed %s ready=%r>' % (self.name, self.ready)
    
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

        return feed.isReady()
    
    def feedReady(self, feedname): 
        # If we don't specify the feed
        log.debug('controller', 'feed %s ready' % (feedname))

        if not self.feeds.has_key(feedname):
            self.warning('FIXME: no feed called: %s' % feedname)
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
        if not feed.isReady():
            feed.addDependency(func, *args)
        else:
            func(*args)

class Controller(pb.Root):
    """Controller, handles all registered components and provides perspectives
for them

The main function of this class is to handle components, tell the to start
register and start up pending components."""
    def __init__(self):
        self.components = {} # dict of component perspectives
        self.feed_manager = FeedManager()
        self.admin = None
        
        self.last_free_port = 5500

    def setAdmin(self, admin):
        self.admin = admin
        
    def getPerspective(self, avatarID):
        """
        Creates a new perspective for a component, raises
        an AlreadyConnectedError if the component is already found in the cache
        @type avatarID:  string
        @rtype:          L{server.controller.ComponentPerspective}
        @returns:        the perspective for the component"""

        if self.hasComponent(avatarID):
            raise errors.AlreadyConnectedError(avatarID)

        componentp = ComponentPerspective(self, avatarID)
        self.addComponent(componentp)
        return componentp

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
        """checks if a component with that name is registered.
        @type name:  string
        @param name: name of the component
        @rtype:      boolean
        @returns:    True if a component with that name is registered, otherwise False"""
        
        return self.components.has_key(name)
    
    def addComponent(self, component):
        """adds a component
        @type component: L{server.controller.ComponentPerspective}
        @param component: the component"""

        component_name = component.getName()
        if self.hasComponent(component_name):
            raise KeyError, component_name
            
        self.components[component_name] = component
        
    def removeComponent(self, component):
        """removes a component
        @type component: L{server.controller.ComponentPerspective}
        @param component: the component"""

        component_name = component.getName()
        if not self.hasComponent(component_name):
            raise KeyError, component_name

        del self.components[component_name]
        if self.admin:
            self.admin.componentRemoved(component)

    def getSourceComponents(self, component):
        """Retrives the sources for a component

        @type component:  component
        @param component: the component
        @rtype:           tuple with 3 items
        @returns:         name, hostname and port"""

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
        """Retrives the feeds for a component

        @type component:  component
        @param component: the component
        @rtype:           tuple of with 3 items
        @returns:         name, hostname and port"""

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

    def componentStart(self, component):
        component.debug('Starting')
        #assert isinstance(component, ComponentPerspective)
        #assert component != ComponentPerspective

        sources = self.getSourceComponents(component)
        feeds = self.getFeedsForComponent(component)
        component.link(sources, feeds)

    def maybeComponentStart(self, component):
        component.debug('maybeComponentStart')
        
        for source in component.getSources():
            if not self.feed_manager.isFeedReady(source):
                component.debug('source %s is not ready' % (source))
                return

        if component.starting:
            return
        
        component.starting = True
        self.componentStart(component)
        
    def componentRegistered(self, component):
        component.debug('registering component')
        if self.admin:
            self.admin.componentAdded(component)
        self.feed_manager.addFeeds(component)

        sources = component.getSources()
        if not sources:
            component.debug('component has no sources, starting')
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

    def stopComponent(self, name):
        """stops a component
        @type name:  string
        @param name: name of the component"""

        component = self.components[name]
        component.stop()
        
    def shutdown(self):
        map(self.stopComponent, self.components)
        
class ControllerServerFactory(pb.PBServerFactory):
    """A Server Factory with a Dispatcher and a Portal"""
    def __init__(self):
        self.controller = Controller()
        
        # create an admin object for the controller
        # FIXME: find a better name for admin
        self.admin = admin.Admin(self.controller)
        self.controller.setAdmin(self.admin)
        
        # create a Dispatcher which will hand out avatars to clients
        # connecting to me
        self.dispatcher = Dispatcher(self.controller, self.admin)

        # create a portal so that I can be connected to, through our dispatcher
        # implementing the IRealm and a checker that allows anonymous access
        checker = pbutil.ReallyAllowAnonymousAccess()
        self.portal = portal.FlumotionPortal(self.dispatcher, [checker])
        # call the parent constructor with this portal for access
        pb.PBServerFactory.__init__(self, self.portal)

    def __repr__(self):
        return '<ControllerServerFactory>'
