# -*- Mode: Python; test-case-name: flumotion.test.test_manager -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# flumotion/manager/component.py: manager-side objects to handle components
# 
# Flumotion - a streaming media server
# Copyright (C) 2004 Fluendo (www.fluendo.com)

# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
# See "LICENSE.GPL" in the source distribution for more information.

# This program is also licensed under the Flumotion license.
# See "LICENSE.Flumotion" in the source distribution for more information.

"""
Manager-side objects for components.

API Stability: semi-stable

Maintainer: U{Johan Dahlin <johan@fluendo.com>}
"""

__all__ = ['ComponentAvatar', 'ComponentHeaven']

import gst
from twisted.spread import pb

from flumotion.common import errors, interfaces, keycards
from flumotion.utils import gstutils, log

class Options:
    """dummy class for storing manager side options of a component"""
    def __init__(self):
        self.eaters = [] # list of eater names
        self.feeders = [] # list of feeder names

# abstracts the concept of a GStreamer tcpserversink (feeder) producing a feed
class Feeder:
    """
    I am an object used by L{FeederSet}.
    My name is of the form componentName:feedName
    """
    def __init__(self, feederName):
        """
        @type  feederName: string
        @param feederName: the name of the feeder
        """
        # we really do want a full feederName because that's how it's called
        # in the code
        if feederName.find(':') == -1:
            # FIXME: log this more nicely ?
            print "ERROR: cannot create feeder without full name"
            raise
        
        componentName, feedName = feederName.split(':')
        self.feedName = feedName
        self.feederName = feederName
        self.component = None

        self.dependencies = {}
        self.ready = False
        
    def addDependency(self, feederName, func, *args):
        """
        Add a dependency function for this feeder depending on another
        feeder in another component.  The function will be called when the
        other feeder is ready.

        @type  feederName: string
        @param feederName: the name of the feeder (componentName:feedName).
        @param func: a function to run when the feeder is ready
        @param args: arguments to the function
        """
        self.dependencies[feederName] = (func, args)

    def setComponentAvatar(self, componentAvatar):
        """
        Give the feeder the component avatar that contains the feeder.
        
        @type  componentAvatar: L{flumotion.manager.component.ComponentAvatar}
        @param componentAvatar: avatar for the component containing this feeder
        """
        assert not self.component
        self.component = componentAvatar
        self.component.debug('taken control of feeder %s' % self.getName())

    def setReady(self):
        """
        Set the feeder to ready, triggering dependency functions.
        """
        assert not self.ready
        assert self.component
        self.component.debug('Feeder.setReady() on feeder %s' % self.getName())
        self.ready = True

        for eatername in self.dependencies.keys():
            func, args = self.dependencies[eatername]
            self.component.debug('running dependency function %r with args %r for eater from %s' % (func, args, eatername))
            func(*args)
        self.dependencies = {}

    def isReady(self):
        return self.ready

    def hasComponentAvatar(self):
        return self.component is not None
    
    def getFeedName(self):
        return self.feedName

    def getName(self):
        return self.feederName

    def getListenHost(self):
        assert self.component
        return self.component.getListenHost()

    def getListenPort(self):
        assert self.component
        log.log('feeder', 'getListenPort(): asking component %s for port of feedName %s' % (self.component, self.feedName))
        return self.component.getFeedPort(self.feedName)
    
    def __repr__(self):
        return '<Feeder %s on %r ready=%r>' % (self.feederName, self.component or '<unavailable component>', self.ready)
    
class FeederSet(log.Loggable):
    """
    I represent a collection of L{Feeder}s.
    I know when a feeder is ready and I handle dependencies between feeders.
    """
    logCategory = 'feederset'
    def __init__(self):
        self.feeders = {} # feederName -> Feeder

    def __getitem__(self, key):
        # FIXME: feeders are now fully named, so remove this hack
        #if key.find(':') == -1:
        #    key += ':default'
        return self.feeders[key]
        
    def hasFeeder(self, feederName):
        # FIXME: remove this hack and enforce
        #if feederName.find(':') == -1:
        #    feederName += ':default'

        return self.feeders.has_key(feederName)
    
    def getFeeder(self, feederName):
        return self[feederName]
    
    def addFeeders(self, componentAvatar):
        """
        Add the feeders of the given component to the set.

        @type componentAvatar: L{flumotion.manager.component.ComponentAvatar}
        """
        name = componentAvatar.getName()
        feeders = componentAvatar.getFeeders()

        for feederName in feeders:
            if not self.hasFeeder(feederName):
                self.debug('adding new Feeder with name %s' % feederName)
                self.feeders[feederName] = Feeder(feederName)
            if not self.feeders[feederName].hasComponentAvatar():
                self.debug('setting component %r' % componentAvatar)
                self.feeders[feederName].setComponentAvatar(componentAvatar)
            
    def isFeederReady(self, feederName):
        if not self.hasFeeder(feederName):
            return False

        feeder = self[feederName]

        return feeder.isReady()
    
    def feederSetReady(self, feederName): 
        """
        Set the given feeder to ready.
        """
        self.debug('feederSetReady: setting feeder %s ready' % (feederName))

        if not self.feeders.has_key(feederName):
            self.error('FIXME: no feeder called: %s' % feederName)
            return
        
        feeder = self.feeders[feederName]
        feeder.setReady()
        self.debug('feederSetReady: done')
            
    def dependComponentOnFeeder(self, componentAvatar, feederName, func):
        """
        Make the given component dependent on the given feeder.
        Register a function and arguments to call when the feeder is ready.

        @type  componentAvatar: L{flumotion.manager.component.ComponentAvatar}
        @param componentAvatar: the component to make dependant
        @param feederName: the name of the feeder to depend upon
        @param func: a function to run when the feeder is ready, taking the ComponentAvatar as its first argument.
        """

        if not self.feeders.has_key(feederName):
            # the component will be set later on
            self.feeders[feederName] = Feeder(feederName)
            
        feeder = self.feeders[feederName]
        
        if not feeder.isReady():
            self.debug('feeder %s is not ready, adding dependency' % feederName)
            feeder.addDependency(feederName, func, componentAvatar)
        else:
            self.debug('feeder %s is ready, executing function %r' % (feederName, func))
            func(componentAvatar)

# FIXME: maybe add type to constructor ? or subclass ?
class ComponentAvatar(pb.Avatar, log.Loggable):
    """
    Manager-side avatar for a component.
    Each component that logs in to the manager gets an avatar created for it
    in the manager.
    """

    logCategory = 'comp-avatar'

    def __init__(self, heaven, username):
        self.heaven = heaven
        self.vishnu = heaven.vishnu
        self.username = username
        self.state = gst.STATE_NULL
        self.options = Options()
        self.ports = {} # feedName -> port
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
        # called after the mind has attached.  options is a dict passed in from
        # flumotion.component.component's remote_register
        for key, value in options.items():
            setattr(self.options, key, value)
        self.options.dict = options
        
        self.heaven.registerComponent(self)
                
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
        @param mind: a remote reference into the component
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

    # functions
    def getTransportPeer(self):
        """
        Get the IPv4 address of the machine the component runs on.
        """
        return self.mind.broker.transport.getPeer()

    # FIXME: rename to something like getEaterFeeders()
    def getEaters(self):
        """
        Get a list of feeder names feeding this component.
        """
        # FIXME: rename this when flumotion.component.component renames it
        return self.options.eaters
    
    def getFeeders(self):
        """
        Get a list of feeder names (componentName:feedName) in this component.
        """
        ### FIXME: rename self.options.feeders to e.g. feederConfig
        #if longName:
        #    return map(lambda feeder:
        #               self.getName() + ':' + feeder, self.options.feeders)
        #else:
        return self.options.feeders

    def getFeedPort(self, feedName):
        """
        Returns the port this feed is being fed on.
        """
        return self.ports[feedName]
 
    def getRemoteManagerIP(self):
        return self.options.ip

    def getName(self):
        return self.username

    def getListenHost(self):
        peer = self.getTransportPeer()
        try:
            return peer.host
        except AttributeError:
            return peer[1]
        return self.getTransportPeer()
   
    def stop(self):
        """
        Tell the avatar to stop the component.
        """
        d = self._mindCallRemote('stop')
        d.addErrback(lambda x: None)
            
    # FIXME: rename, since it's not GStreamer linking.
    # This function tells the component to start consuming feeds and start
    # its feeders
    def link(self, eatersData, feedersData):
        """
        Tell the component to link itself to other components.

        @type eatersData: tuple of (feedername, host, port) tuples of elements feeding our eaters.
        @type feedersData: tuple of (name, host) tuples of our feeding elements.
        """
        def linkCallback(feedData):
            for feedName, host, port in feedData:
                self.debug('feed %s (%s:%d) is ready' % (feedName, host, port))
                self.host = host
                self.ports[feedName] = port
                
                self.checkFeedReady(feedName)
                self.debug('linkCallback: done linking')

        def linkErrback(reason):
            self.error("Could not make component link, reason %s" % reason)
                
        d = self._mindCallRemote('link', eatersData, feedersData)
        d.addCallback(linkCallback)
        d.addErrback(linkErrback)
    
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

    def getUIZip(self, domain, style):
        """
        Request the zip for the component's UI in the given domain and style.

        The deferred returned will receive the code to run the UI.

        @type  domain: string
        @param domain: the UI domain to get
        @type  style:  string
        @param style:  the UI style to get

        @rtype: L{twisted.internet.defer.Deferred}
        """
        self.debug('calling remote getUIZip(%s, %s)' % (domain, style))
        d = self._mindCallRemote('getUIZip', domain, style)
        d.addErrback(self._mindErrback)
        return d

    def getUIMD5Sum(self, domain, style):
        """
        Request the md5sum for the component's UI in the given domain and style.

        The deferred returned will receive the md5sum of the UI zip.

        @type  domain: string
        @param domain: the UI domain to get
        @type  style:  string
        @param style:  the UI style to get

        @rtype: L{twisted.internet.defer.Deferred}
        """
        self.debug('calling remote getUIMD5Sum(%s, %s)' % (domain, style))
        cb = self._mindCallRemote('getUIMD5Sum', domain, style)
        cb.addErrback(self._mindErrback)
        return cb
    
    def checkFeedReady(self, feedName):
        # check if the given feed is ready to start, and start it if it is
        self.info('checkFeedReady: feedName %s' % feedName)
        if not self.ports.has_key(feedName):
            self.info('checkFeedReady: no port yet')
            return
        
        if not self.getFeeders():
            self.info('checkFeedReady: no remote options yet')
            return

        if self.state != gst.STATE_PLAYING:
            self.info('checkFeedReady: not playing yet (%s)' %
                      gst.element_state_get_name(self.state))
            return

        self.info('checkFeedReady: setting to ready')
        self.heaven.setFeederReady(self, feedName)
        self.log('checkFeedReady: set to ready')

    # FIXME: maybe make a BouncerComponentAvatar subclass ?
    def authenticate(self, keycard):
        d = self._mindCallRemote('authenticate', keycard)
        d.addErrback(self._mindErrback)
        return d

    def removeKeycard(self, keycardId):
        d = self._mindCallRemote('removeKeycard', keycardId)
        d.addErrback(self._mindErrback)
        return d

    ### IPerspective methods, called by the worker's component
    def perspective_log(self, *msg):
        log.debug(self.getName(), *msg)
        
    def perspective_stateChanged(self, feed_name, state):
        self.debug('stateChanged: feed name %s, state %s' % (
            feed_name, gst.element_state_get_name(state)))
        
        self.state = state
        if self.state == gst.STATE_PLAYING:
            self.info('%r is now playing' % self)

            self.checkFeedReady(feed_name)
            
    def perspective_error(self, element, error):
        self.error('error element=%s string=%s' % (element, error))
        self.heaven.removeComponent(self)

    def perspective_uiStateChanged(self, componentName, state):
        self.vishnu.adminheaven.uiStateChanged(componentName, state)

    def perspective_notifyFeedPorts(self, feedPorts):
        self.debug('received feed ports from component: %s' % feedPorts)

    def perspective_authenticate(self, bouncerName, keycard):
        self.debug('asked to authenticate keycard %r using bouncer %s' % (keycard, bouncerName))
        if not self.heaven.hasComponent(bouncerName):
            # FIXME: return failure object ?
            return False

        bouncerAvatar = self.heaven.getComponent(bouncerName)
        return bouncerAvatar.authenticate(keycard)

    def perspective_removeKeycard(self, bouncerName, keycardId):
        self.debug('asked to remove keycard %s on bouncer %s' % (bouncerName, keycardId))
        if not self.heaven.hasComponent(bouncerName):
            # FIXME: return failure object ?
            return False

        bouncerAvatar = self.heaven.getComponent(bouncerName)
        return bouncerAvatar.removeKeycard(keycardId)



class ComponentHeaven(pb.Root, log.Loggable):
    """
    I handle all registered components and provide avatars for them.
    """

    __implements__ = interfaces.IHeaven
    logCategory = 'comp-heaven'
    
    def __init__(self, vishnu):
        """
        @type vishnu:  L{flumotion.manager.manager.Vishnu}
        @param vishnu: the Vishnu object this heaven belongs to
        """
        self.avatars = {} # componentName -> componentAvatar
        self._feederSet = FeederSet()
        self.vishnu = vishnu
        
    ### IHeaven methods
    def createAvatar(self, avatarId):
        """
        Creates a new avatar for a component.
        Raises an AlreadyConnectedError if the component is already found
        in the cache.
        
        @type avatarId:  string

        @rtype:          L{flumotion.manager.component.ComponentAvatar}
        @returns:        the avatar for the component
        """

        if self.hasComponent(avatarId):
            raise errors.AlreadyConnectedError(avatarId)

        avatar = ComponentAvatar(self, avatarId)
        self._addComponentAvatar(avatar)
        return avatar

    def removeAvatar(self, avatarId):
        if not self.hasComponent(avatarId):
            raise KeyError, avatarId

        avatar = self.avatars[avatarId]
        del self.avatars[avatarId]
       
        self.vishnu.adminheaven.componentRemoved(avatar)
    
    ### our methods
    def _componentIsLocal(self, componentAvatar):
        peer = componentAvatar.getTransportPeer()
        try:
            host = peer.host
        except AttributeError:
            host = peer[1]

        if host == '127.0.0.1':
            return True
        else:
            return False

    def getComponent(self, name):
        """
        Look up a ComponentAvatar by name.

        @type name:  string
        @param name: name of the component

        @rtype:      L{flumotion.manager.component.ComponentAvatar}
        @returns:    the component avatar
        """

        if not self.hasComponent(name):
            raise KeyError, name
        
        return self.avatars[name]
    
    def hasComponent(self, name):
        """
        Check if a component with that name is registered.

        @type name:  string
        @param name: name of the component

        @rtype:      boolean
        @returns:    True if a component with that name is registered
        """
        
        return self.avatars.has_key(name)
    
    def _addComponentAvatar(self, componentAvatar):
        """
        Adds a component avatar.

        @type componentAvatar: L{flumotion.manager.component.ComponentAvatar}
        @param componentAvatar: the component avatar
        """

        componentName = componentAvatar.getName()
        if self.hasComponent(componentName):
            raise KeyError, componentName
            
        self.avatars[componentName] = componentAvatar
        
    def removeComponent(self, componentAvatar):
        """
        Remove a component from the heaven.

        @type componentAvatar: L{flumotion.manager.component.ComponentAvatar}
        @param componentAvatar: the component
        """

        componentName = componentAvatar.getName()
        self.removeAvatar(componentName)
        
    def _getComponentEatersData(self, componentAvatar):
        """
        Retrieve the information about the feeders this component's eaters
        are eating from.

        @type  componentAvatar: L{flumotion.manager.component.ComponentAvatar}
        @param componentAvatar: the component

        @rtype:           tuple with 3 items
        @returns:         tuple of feeder name, host name and port, or None
        """

        eaterFeederNames = componentAvatar.getEaters()
        #feederName is componentName:feedName on the feeding component
        retval = []
        for feederName in eaterFeederNames:
            feeder = self._feederSet.getFeeder(feederName)
            self.debug('EatersData(): feeder %r' % feeder)

            host = feeder.getListenHost()
            if (not self._componentIsLocal(componentAvatar)
                and host == '127.0.0.1'):
                host = componentAvatar.getRemoteManagerIP()

            retval.append((feederName, host, feeder.getListenPort()))
        return retval

    def _getComponentFeedersData(self, componentAvatar):
        """
        Retrieves the data of feeders (feed producer elements) for a component.

        @type  componentAvatar: L{flumotion.manager.component.ComponentAvatar}
        @param componentAvatar: the component
        @rtype:           tuple of with 2 items
        @returns:         name and host
        """

        host = componentAvatar.getListenHost()
        feeders = componentAvatar.getFeeders()
        retval = []
        for feeder in feeders:
            retval.append((feeder, host))
        return retval

    def _startComponent(self, componentAvatar):
        componentAvatar.debug('Starting, asking component to link')
        eatersData = self._getComponentEatersData(componentAvatar)
        feedersData = self._getComponentFeedersData(componentAvatar)

        componentAvatar.debug('Starting, asking component to link with eatersData %s and feedersData %s' % (eatersData, feedersData))
        componentAvatar.link(eatersData, feedersData)

    def checkComponentStart(self, componentAvatar):
        """
        Check if the component can start up, and start it if it can.
        This depends on whether the components and feeders it depends on have
        started.
        """
        componentAvatar.debug('checkComponentStart')
        
        for eaterFeeder in componentAvatar.getEaters():
            if not self._feederSet.isFeederReady(eaterFeeder):
                componentAvatar.debug('feeder %s is not ready' % (eaterFeeder))
                return

        # FIXME: change this to mood
        if componentAvatar.starting:
            return
        
        componentAvatar.starting = True
        self._startComponent(componentAvatar)
        
    def registerComponent(self, componentAvatar):
        """
        This function registers a component in the heaven.
        It is triggered when the mind is attached.

        @type  componentAvatar: L{flumotion.manager.component.ComponentAvatar}
        """
        componentAvatar.debug('registering component')

        # tell the admin client
        self.vishnu.adminheaven.componentAdded(componentAvatar)

        # tell the feeder set
        self._feederSet.addFeeders(componentAvatar)

        # check if we eat feeds from other feeders
        eaterFeeders = componentAvatar.getEaters()
        if not eaterFeeders:
            componentAvatar.debug('component does not take feeds, starting')
            self._startComponent(componentAvatar)
            return

        # we do, so we need to make our eaters depend on other feeders
        componentAvatar.debug('need to wait for %s' % eaterFeeders)
        for feeder in eaterFeeders:
            self._feederSet.dependComponentOnFeeder(componentAvatar, feeder,
                self.checkComponentStart)
                
    def setFeederReady(self, componentAvatar, feedName):
        """
        Tell the feeder set that the given feed on the given component is
        ready.
        
        @type  componentAvatar: string
        @param componentAvatar: the component containing the feed
        @type  feedName:        string
        @param feedName:        the feed set to ready
        """

        feederName = componentAvatar.getName() + ':' + feedName
        componentAvatar.debug('setting feeder %s to ready in feaderset' % feederName)
        self._feederSet.feederSetReady(feederName)
        componentAvatar.log('setFeederReady done')

    def shutdown(self):
        """
        Shut down the heaven, stopping all components.
        """
        for name in self.avatars.keys():
            self.avatars[name].stop()
