# -*- Mode: Python -*-
# vi:si:et:sw=4:sts=4:ts=4

# Flumotion - a video streaming server
# Copyright (C) 2004 Fluendo
#
# manager/manager.py: manager functionality
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

"""Manager implementation and related classes

API Stability: semi-stable

Maintainer: U{Johan Dahlin <johan@fluendo.com>}
"""

__all__ = ['Manager', 'ManagerServerFactory']

import gst

from twisted.internet import reactor
from twisted.python import components
from twisted.spread import pb

from flumotion.manager import admin, component
from flumotion.common import interfaces, errors
from flumotion.twisted import pbutil, portal
from flumotion.utils import gstutils, log

# an internal class
class Dispatcher(log.Loggable):
    """
    I implement L{portal.IRealm}.
    I make sure that when a L{pb.Avatar} is requested through me, the
    Avatar being returned knows about the mind (client) requesting
    the Avatar.
    """
    
    __implements__ = portal.IRealm

    logCategory = 'dispatcher'

    def __init__(self, manager, adminheaven):
        """
        @type manager: L{manager.manager.Manager}
        @type adminheaven:      L{manager.admin.AdminHeaven}
        """
        self.manager = manager
        self.adminheaven = adminheaven

    # requestAvatar gets called through ClientFactory.login()
    # An optional second argument can be passed to login, which should be
    # a L{twisted.spread.flavours.Referenceable}
    # A L{twisted.spread.pb.RemoteReference} to it is passed to
    # requestAvatar as mind.
    # So in short, the mind is a reference to the client passed in login()
    # on the peer, allowing any object that has the mind to call back
    # to the piece that called login(),
    # which in our case is a component or an admin client.
    def requestAvatar(self, avatarID, mind, *ifaces):

        if not pb.IPerspective in ifaces:
            raise errors.NoPerspectiveError(avatarID)

        avatar = None
        if interfaces.IBaseComponent in ifaces:
            avatar = self.manager.getAvatar(avatarID)
        elif interfaces.IAdminComponent in ifaces:
            avatar = self.adminheaven.getAvatar()

        if not avatar:
            raise errors.NoPerspectiveError(avatarID)

        self.debug("returning Avatar: id %s, avatar %s" % (avatarID, avatar))
        
        # schedule a perspective attached for after this function
        reactor.callLater(0, avatar.attached, mind)
        
        # return a tuple of interface, aspect, and logout function 
        return (pb.IPerspective, avatar,
                lambda avatar=avatar,mind=mind: avatar.detached(mind))

class Manager(pb.Root):
    """
    Manager, handles all registered components and provides avatars
    for them.
    The main function of this class is to handle components, tell them
    to start register and start up pending components.
    """
    def __init__(self):
        self.components = {} # dict of component avatars
        self.feeder_set = FeederSet()
        self.adminheaven = None
        
        self.last_free_port = 5500

    def setAdminHeaven(self, adminheaven):
        self.adminheaven = adminheaven
        
    def getAvatar(self, avatarID):
        """
        Creates a new avatar for a component, raises
        an AlreadyConnectedError if the component is already found in the cache
        
        @type avatarID:  string

        @rtype:          L{flumotion.manager.component.ComponentAvatar}
        @returns:        the avatar for the component
        """

        if self.hasComponent(avatarID):
            raise errors.AlreadyConnectedError(avatarID)

        avatar = component.ComponentAvatar(self, avatarID)
        self.addComponent(avatar)
        return avatar

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
        """
        adds a component

        @type component: L{flumotion.manager.component.ComponentAvatar}
        @param component: the component
        """

        component_name = component.getName()
        if self.hasComponent(component_name):
            raise KeyError, component_name
            
        self.components[component_name] = component
        
    def removeComponent(self, component):
        """
        removes a component

        @type component: L{flumotion.manager.component.ComponentAvatar}
        @param component: the component
        """

        component_name = component.getName()
        if not self.hasComponent(component_name):
            raise KeyError, component_name

        del self.components[component_name]
        if self.adminheaven:
            self.adminheaven.componentRemoved(component)

    def getComponentEaters(self, component):
        """
        Retrieves the eaters (feed consumer elements) of a component.

        @type component:  component
        @param component: the component
        @rtype:           tuple with 3 items
        @returns:         name, hostname and port
        """

        peernames = component.getEaters()
        retval = []
        for peername in peernames:
            feeder = self.feeder_set.getFeeder(peername)
            feedername = feeder.getName()
            if feedername.endswith(':default'):
                feedername = feedername[:-8]

            host = feeder.getListenHost()
            if (not self.isLocalComponent(component) and host == '127.0.0.1'):
                host = component.getRemoteManagerIP()

            retval.append((feedername, host,feeder.getListenPort()))
        return retval

    def getComponentFeeders(self, component):
        """
        Retrieves the feeders (feed producer elements) for a component.

        @type component:  component
        @param component: the component
        @rtype:           tuple of with 3 items
        @returns:         name, host and port
        """

        host = component.getListenHost()
        feedernames = component.getFeeders()
        retval = []
        for feedername in feedernames:
            if self.isLocalComponent(component):
                port = gstutils.get_free_port(self.last_free_port)
                self.last_free_port = port + 1
            else:
                port = None

            retval.append((feedername, host, port))
        return retval

    def componentStart(self, component):
        component.debug('Starting')
        #assert isinstance(component, ComponentPerspective)
        #assert component != ComponentPerspective

        eaters = self.getComponentEaters(component)
        feeders = self.getComponentFeeders(component)
        component.link(eaters, feeders)

    def maybeComponentStart(self, component):
        component.debug('maybeComponentStart')
        
        for eater in component.getEaters():
            # eater and feeder elements are named with the feed name
            # on the GObject level
            if not self.feeder_set.isFeederReady(eater):
                component.debug('feeder %s is not ready' % (eater))
                return

        if component.starting:
            return
        
        component.starting = True
        self.componentStart(component)
        
    def componentRegistered(self, component):
        component.debug('registering component')
        if self.adminheaven:
            self.adminheaven.componentAdded(component)
        self.feeder_set.addFeeders(component)

        eaters = component.getEaters()
        if not eaters:
            component.debug('component does not take feeds, starting')
            self.componentStart(component)
            return
        else:
            for eater in eaters:
                self.feeder_set.dependOnFeeder(eater,
                                               self.maybeComponentStart,
                                               component)
                
    def startPendingComponents(self, component, feeder):
        feedername = component.getName() + ':' + feeder
        self.feeder_set.feederReady(feedername)

    def stopComponent(self, name):
        """
        Stops a component.
        
        @type name:  string
        @param name: name of the component
        """

        component = self.components[name]
        component.stop()
        
    def shutdown(self):
        map(self.stopComponent, self.components)
        
class ManagerServerFactory(pb.PBServerFactory):
    """A Server Factory with a Dispatcher and a Portal"""
    def __init__(self):
        self.manager = Manager()
        
        self.adminheaven = admin.AdminHeaven(self.manager)
        self.manager.setAdminHeaven(self.adminheaven)
        
        # create a Dispatcher which will hand out avatars to clients
        # connecting to me
        self.dispatcher = Dispatcher(self.manager, self.adminheaven)

        # create a portal so that I can be connected to, through our dispatcher
        # implementing the IRealm and a checker that allows anonymous access
        checker = pbutil.ReallyAllowAnonymousAccess()
        self.portal = portal.FlumotionPortal(self.dispatcher, [checker])
        # call the parent constructor with this portal for access
        pb.PBServerFactory.__init__(self, self.portal)
        #self.unsafeTracebacks = 1 # for debugging tracebacks to clients

    def __repr__(self):
        return '<ManagerServerFactory>'


# abstracts the concept of a GStreamer tcpserversink producing a feeder
class Feeder:
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
        return '<Feeder %s ready=%r>' % (self.name, self.ready)
    
class FeederSet:
    def __init__(self):
        self.feeders = {}

    def __getitem__(self, key):
        if key.find(':') == -1:
            key += ':default'
        return self.feeders[key]
        
    def hasFeeder(self, name):
        if name.find(':') == -1:
            name += ':default'

        return self.feeders.has_key(name)
    
    def getFeeder(self, name):
        return self[name]
    
    def addFeeders(self, component):
        # add the component's feeders
        name = component.getName()
        feeders = component.getFeeders(True)
        for feedername in feeders:
            longname = name + ':' + feedername
            if not self.feeders.has_key(feedername):
                self.feeders[feedername] = Feeder(feedername)
            self.feeders[feedername].setComponent(component)
            
    def isFeederReady(self, feedername):
        if not self.hasFeeder(feedername):
            return False

        feeder = self[feedername]

        return feeder.isReady()
    
    def feederReady(self, feedername): 
        # set the feeder to ready
        # If we don't specify the feeder
        log.debug('manager', 'feeder %s ready' % (feedername))

        if not self.feeders.has_key(feedername):
            self.warning('FIXME: no feeder called: %s' % feedername)
            return
        
        feeder = self.feeders[feedername]
        feeder.setReady()
            
    def dependOnFeeder(self, feedername, func, *args):
        # make this feeder depend on another feeder
        # If we don't specify the feeder
        if feedername.find(':') == -1:
            feedername += ':default'

        if not self.feeders.has_key(feedername):
            self.feeders[feedername] = Feeder(feedername)
            
        feeder = self.feeders[feedername]
        if not feeder.isReady():
            feeder.addDependency(func, *args)
        else:
            func(*args)
