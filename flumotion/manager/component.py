# -*- Mode: Python -*-
# vi:si:et:sw=4:sts=4:ts=4

# Flumotion - a video streaming server
# Copyright (C) 2004 Fluendo
#
# manager/component.py: manager-side objects to handle components
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

"""
Manager-side objects for components.

API Stability: semi-stable

Maintainer: U{Johan Dahlin <johan@fluendo.com>}
"""

__all__ = ['ComponentAvatar', 'ComponentHeaven']

import gst
from twisted.spread import pb

from flumotion.common import errors, interfaces
from flumotion.utils import gstutils, log

class Options:
    """dummy class for storing manager side options of a component"""

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

class ComponentAvatar(pb.Avatar, log.Loggable):
    """
    Manager-side avatar for a component.
    Each component that logs in to the manager gets an avatar created for it
    in the manager.
    """

    logCategory = 'comp-avatar'

    def __init__(self, manager, username):
        self.manager = manager
        self.username = username
        self.state = gst.STATE_NULL
        self.options = Options()
        self.listen_ports = {}
        self.started = False
        self.starting = False
        
    ### python methods
    def __repr__(self):
        return '<%s %s in state %s>' % (self.__class__.__name__,
                                        self.getName(),
                                        gst.element_state_get_name(self.state))

    ### log.Loggable methods
    def logFunction(self, arg):
        return self.getName() + ': ' + arg

    ### ComponentAvatar methods

    # mind functions
    def _mindCallRemote(self, name, *args, **kwargs):
        self.debug('calling remote method %s%r' % (name, args))
        try:
            return self.mind.callRemote(name, *args, **kwargs)
        except pb.DeadReferenceError:
            self.mind = None
            self.detached()
            return

    # general fallback for unhandled errors so we detect them
    # FIXME: we can't use this since we want a PropertyError to fall through
    # afger going through the PropertyErrback.
    def _mindErrback(self, failure, *ignores):
        if ignores:
            if failure.check(*ignores):
               return failure
        self.warning("Unhandled remote call error: %s" % failure.getErrorMessage())
        self.warning("raising '%s'" % str(failure.type))
        return failure

    # we create this errback just so we can interject a message inbetween
    # to make it clear the Traceback line is fine.
    # When this is fixed in Twisted we can just remove the errback and
    # the error will still get sent back correctly to admin.
    def _mindPropertyErrback(self, failure):
        failure.trap(errors.PropertyError)
        print "Ignore the following Traceback line, issue in Twisted"
        return failure

    def _mindRegisterCallback(self, options):
        for key, value in options.items():
            setattr(self.options, key, value)
        self.options.dict = options
        
        self.manager.componentRegistered(self)
                
    def _mindPipelineErrback(self, failure):
        failure.trap(errors.PipelineParseError)
        self.error('Invalid pipeline for component')
        self._mindCallRemote('stop')
        return None

    def attached(self, mind):
        """
        Tell the avatar that the given mind has been attached.
        This gives the avatar a way to call remotely to the client that
        requested this avatar.
        This is scheduled by the portal after the client has logged in.

        @type mind: L{twisted.spread.pb.RemoteReference}
        """
        self.debug('mind attached, calling remote register()')
        self.mind = mind
        
        d = self._mindCallRemote('register')
        d.addCallback(self._mindRegisterCallback)
        d.addErrback(self._mindPipelineErrback)
        d.addErrback(self._mindErrback)
        
    def detached(self, mind=None):
        """
        Tell the avatar that the given mind has been detached.

        @type mind: L{twisted.spread.pb.RemoteReference}
        """
        self.debug('detached')
        name = self.getName()
        if self.manager.hasComponent(name):
            self.manager.removeComponent(self)

    # functions
    def getTransportPeer(self):
        """
        Get the IPv4 address of the machine the component runs on.
        """
        return self.mind.broker.transport.getPeer()

    def getEaters(self):
        """
        Returns a list of names of feeded elements.
        """
        return self.options.eaters
    
    def getFeeders(self, longname=False):
        """
        Returns a list of names of feeding elements.
        """
        if longname:
            return map(lambda feeder:
                       self.getName() + ':' + feeder, self.options.feeders)
        else:
            return self.options.feeders

    def getRemoteManagerIP(self):
        return self.options.ip

    def getName(self):
        return self.username

    def getListenHost(self):
        return self.getTransportPeer()[1]

    # This method should ask the component if the port is free
    def getListenPort(self, feeder):
        if feeder.find(':') != -1:
            feeder = feeder.split(':')[1]

        assert self.listen_ports.has_key(feeder), self.listen_ports
        assert self.listen_ports[feeder] != -1, self.listen_ports
        return self.listen_ports[feeder]

    def stop(self):
        """
        Tell the avatar to stop the component.
        """
        d = self._mindCallRemote('stop')
        d.addErrback(lambda x: None)
            
    def link(self, eaters, feeders):
        """
        Tell the component to link itself to other components.

        @type eaters: tuple of (name, host, port) tuples of feeded elements.
        @type feeders: tuple of (name, host, port) tuples of feeding elements.
        """
        def _getFreePortsCallback((feeders, ports)):
            self.listen_ports = ports
            d = self._mindCallRemote('link', eaters, feeders)
            d.addErrback(self._mindErrback)

        if feeders:
            d = self._mindCallRemote('getFreePorts', feeders)
            d.addCallbacks(_getFreePortsCallback, self._mindErrback)
        else:
            d = self._mindCallRemote('link', eaters, [])
            d.addErrback(self._mindErrback)
    
    def setElementProperty(self, element, property, value):
        """
        Set a property on an element.

        @type element: string
        @param element: the element to set the property on
        @type property: string
        @param property: the property to set
        @type value: mixed
        @param value: the value to set the property to
        """
        if not element:
            msg = "%s: no element specified" % self.getName()
            self.warning(msg)
            raise errors.PropertyError(msg)
        if not element in self.options.elements:
            msg = "%s: element '%s' does not exist" % (self.getName(), element)
            self.warning(msg)
            raise errors.PropertyError(msg)
        if not property:
            msg = "%s: no property specified" % self.getName()
            self.warning(msg)
            raise errors.PropertyError(msg)
        self.debug("setting property '%s' on element '%s'" % (property, element))
        
        cb = self._mindCallRemote('setElementProperty', element, property, value)
        cb.addErrback(self._mindPropertyErrback)
        cb.addErrback(self._mindErrback, errors.PropertyError)
        return cb
        
    def getElementProperty(self, element, property):
        """
        Get a property of an element.

        @type element: string
        @param element: the element to get the property of
        @type property: string
        @param property: the property to get
        """
        if not element:
            msg = "%s: no element specified" % self.getName()
            self.warning(msg)
            raise errors.PropertyError(msg)
        if not element in self.options.elements:
            msg = "%s: element '%s' does not exist" % (self.getName(), element)
            self.warning(msg)
            raise errors.PropertyError(msg)
        if not property:
            msg = "%s: no property specified" % self.getName()
            self.warning(msg)
            raise errors.PropertyError(msg)
        self.debug("getting property %s on element %s" % (element, property))
        cb = self._mindCallRemote('getElementProperty', element, property)
        cb.addErrback(self._mindPropertyErrback)
        cb.addErrback(self._mindErrback, errors.PropertyError)
        return cb

    def callComponentRemote(self, method, *args, **kwargs):
        """
        Call a remote method on the component.
        This is used so that admin clients can call methods from the interface
        to the component.

        @type method: string
        @param method: the method to call.  On the component, this calls
         component_(method)
        @type args: mixed
        @type kwargs: mixed
        """
        self.debug("calling component method %s" % method)
        cb = self._mindCallRemote('callMethod', method, *args, **kwargs)
        cb.addErrback(self._mindErrback, Exception)
        return cb
        
    def _reloadComponentErrback(self, failure):
        import exceptions
        failure.trap(errors.ReloadSyntaxError)
        self.warning(failure.getErrorMessage())
        print "Ignore the following Traceback line, issue in Twisted"
        return failure

    def reloadComponent(self):
        """
        Tell the component to reload itself.

        @rtype: L{twisted.internet.defer.Deferred}
        """
        cb = self._mindCallRemote('reloadComponent')
        cb.addErrback(self._reloadComponentErrback)
        cb.addErrback(self._mindErrback, errors.ReloadSyntaxError)
        return cb

    def getUIEntry(self):
        """
        Request the UI entry for the component's UI.
        The deferred returned will receive the code to run the UI.

        @rtype: L{twisted.internet.defer.Deferred}
        """
        self.debug('calling remote getUIEntry')
        cb = self._mindCallRemote('getUIEntry')
        cb.addErrback(self._mindErrback)
        return cb
    
    ### IPerspective methods
    def perspective_log(self, *msg):
        log.debug(self.getName(), *msg)
        
    def perspective_stateChanged(self, feeder, state):
        self.debug('stateChanged: %s %s' % (feeder, gst.element_state_get_name(state)))
        
        self.state = state
        if self.state == gst.STATE_PLAYING:
            self.info('is now playing')

        if self.getFeeders():
            self.manager.startPendingComponents(self, feeder)
            
    def perspective_error(self, element, error):
        self.error('error element=%s string=%s' % (element, error))
        self.manager.removeComponent(self)

    def perspective_uiStateChanged(self, component_name, state):
        self.manager.adminheaven.uiStateChanged(component_name, state)

class ComponentHeaven(pb.Root, log.Loggable):
    """
    Manager, handles all registered components and provides avatars
    for them.
    The main function of this class is to handle components, tell them
    to start register and start up pending components.
    """

    __implements__ = interfaces.IHeaven
    logCategory = 'comp-heaven'
    
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

        avatar = ComponentAvatar(self, avatarID)
        self.addComponent(avatar)
        return avatar

    def removeAvatar(self, avatarID):
        self.removeComponentByName(avatarID)
    
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
        self.removeComponentByName(component_name)
        
    def removeComponentByName(self, component_name):
        if not self.hasComponent(component_name):
            raise KeyError, component_name

        component = self.components[component_name]
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
        


