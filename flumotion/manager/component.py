# -*- Mode: Python; test-case-name: flumotion.test.test_manager -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# flumotion/manager/component.py: manager-side objects to handle components
# 
# Flumotion - a streaming media server
# Copyright (C) 2004 Fluendo, S.L. (www.fluendo.com). All rights reserved.

# This file may be distributed and/or modified under the terms of
# the GNU General Public License version 2 as published by
# the Free Software Foundation.
# This file is distributed without any warranty; without even the implied
# warranty of merchantability or fitness for a particular purpose.
# See "LICENSE.GPL" in the source distribution for more information.

# Licensees having purchased or holding a valid Flumotion Advanced
# Streaming Server license may use this file in accordance with the
# Flumotion Advanced Streaming Server Commercial License Agreement.
# See "LICENSE.Flumotion" in the source distribution for more information.

# Headers in this file shall remain intact.

"""
manager-side objects for components

API Stability: semi-stable

Maintainer: U{Johan Dahlin <johan@fluendo.com>}
"""

__all__ = ['ComponentAvatar', 'ComponentHeaven']

import gst
from twisted.spread import pb

from flumotion.manager import common
from flumotion.common import errors, interfaces, keycards, log, config
from flumotion.utils import gstutils

class Options:
    """dummy class for storing manager side options of a component"""
    def __init__(self):
        self.eaters = [] # list of eater names
        self.feeders = [] # list of feeder names
        self.dict = None
        self.worker = None
        self.pid = None

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
        
        self.ready = False
        self.feederName = feederName
        self.dependencies = {}
        self.component = None
        
        if feederName.find(':') == -1:
            # FIXME: log this more nicely ?
            print "ERROR: cannot create feeder without full name"
            raise
        
        self.feedName = feederName.split(':')[1]

        
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

        if not self.dependencies.has_key(feederName):
            self.dependencies[feederName] = []
            
        self.dependencies[feederName].append((func, args))

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

        for eaterName in self.dependencies.keys():
            for func, args in self.dependencies[eaterName]:
                self.component.debug('running dependency function %r with args %r for eater from %s' % (func, args, eaterName))
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
        return self.component.getClientAddress()

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
        return self.feeders[key]
        
    def hasFeeder(self, feederName):
        return self.feeders.has_key(feederName)
    
    def getFeeder(self, feederName):
        return self[feederName]
    
    def addFeeders(self, componentAvatar):
        """
        Add the feeders of the given component to the set.

        @type componentAvatar: L{flumotion.manager.component.ComponentAvatar}
        """

        feeders = componentAvatar.getFeeders()

        for feederName in feeders:
            if not self.hasFeeder(feederName):
                self.debug('adding new Feeder with name %s' % feederName)
                self.feeders[feederName] = Feeder(feederName)
            if not self.feeders[feederName].hasComponentAvatar():
                self.debug('setting component %r' % componentAvatar)
                self.feeders[feederName].setComponentAvatar(componentAvatar)
            
    def removeFeeders(self, componentAvatar):
        """
        Remove the feeders of the given component to the set.

        @type componentAvatar: L{flumotion.manager.component.ComponentAvatar}
        """
        
        feeders = componentAvatar.getFeeders()
        
        for feederName in feeders:
            if self.hasFeeder(feederName):
                del self.feeders[feederName]
            
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

class ComponentAvatar(common.ManagerAvatar):
    """
    Manager-side avatar for a component.
    Each component that logs in to the manager gets an avatar created for it
    in the manager.
    """

    logCategory = 'comp-avatar'

    def __init__(self, heaven, avatarId):
        common.ManagerAvatar.__init__(self, heaven, avatarId)
        
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

    # general fallback for unhandled errors so we detect them
    # FIXME: we can't use this since we want a PropertyError to fall through
    # after going through the PropertyErrback.
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

    def attached(self, mind):
        common.ManagerAvatar.attached(self, mind)
        self.debug('mind %r attached, calling remote register()' % mind)
        
        d = self.mindCallRemote('register')
        d.addCallback(self._mindRegisterCallback)
        d.addErrback(self._mindPipelineErrback)
        d.addErrback(self._mindErrback)

    def _mindRegisterCallback(self, options): 
        # called after the mind has attached.  options is a dict passed in from
        # flumotion.component.component's remote_register
        assert options
        for key, value in options.items():
            setattr(self.options, key, value)
        self.options.dict = options
        
        self.heaven.registerComponent(self)
                
    def _mindPipelineErrback(self, failure):
        failure.trap(errors.PipelineParseError)
        self.error('Invalid pipeline for component')
        self.mindCallRemote('stop')
        return None
        
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
        return self.avatarId

    def getType(self):
        # use the config to check the type
        if not self.avatarId in self.heaven._componentEntries.keys():
            self.debug('component %s not found in entries' % self.avatarId)
            return None
        return self.heaven._componentEntries[self.avatarId].type

    def getWorkerName(self):
        """
        Return the name of the worker.
        """
        return self.options.worker

    def getPid(self):
        return self.options.pid

    def stop(self):
        """
        Tell the avatar to stop the component.
        """
        d = self.mindCallRemote('stop')
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
                
        d = self.mindCallRemote('link', eatersData, feedersData)
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
        
        d = self.mindCallRemote('setElementProperty', element, property, value)
        d.addErrback(self._mindPropertyErrback)
        d.addErrback(self._mindErrback, errors.PropertyError)
        return d
        
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
        # FIXME: this is wrong, since it's not dynamic.  Elements can be
        # renamed
        if not element in self.options.elements:
            msg = "%s: element '%s' does not exist" % (self.getName(), element)
            self.warning(msg)
            raise errors.PropertyError(msg)
        if not property:
            msg = "%s: no property specified" % self.getName()
            self.warning(msg)
            raise errors.PropertyError(msg)
        self.debug("getting property %s on element %s" % (element, property))
        d = self.mindCallRemote('getElementProperty', element, property)
        d.addErrback(self._mindPropertyErrback)
        d.addErrback(self._mindErrback, errors.PropertyError)
        return d

    def reloadComponent(self):
        """
        Tell the component to reload itself.

        @rtype: L{twisted.internet.defer.Deferred}
        """
        def _reloadComponentErrback(self, failure):
            failure.trap(errors.ReloadSyntaxError)
            self.warning(failure.getErrorMessage())
            print "Ignore the following Traceback line, issue in Twisted"
            return failure

        d = self.mindCallRemote('reloadComponent')
        d.addErrback(_reloadComponentErrback)
        d.addErrback(self._mindErrback, errors.ReloadSyntaxError)
        return d

    # FIXME rename to something that reflects an action, like startFeedIfReady
    def checkFeedReady(self, feedName):
        # check if the given feed is ready to start, and start it if it is
        self.info('checkFeedReady: feedName %s' % feedName)
        if not self.ports.has_key(feedName):
            self.debug('checkFeedReady: no port yet')
            return
        
        if not self.getFeeders():
            self.debug('checkFeedReady: no remote options yet')
            return

        if self.state != gst.STATE_PLAYING:
            self.debug('checkFeedReady: not playing yet (%s)' %
                      gst.element_state_get_name(self.state))
            return

        self.debug('checkFeedReady: setting to ready')
        self.heaven.setFeederReady(self, feedName)
        self.debug('checkFeedReady: set to ready')

    # FIXME: maybe make a BouncerComponentAvatar subclass ?
    def authenticate(self, keycard):
        d = self.mindCallRemote('authenticate', keycard)
        d.addErrback(self._mindErrback)
        return d

    def removeKeycard(self, keycardId):
        """
        Remove a keycard managed by this bouncer because the requester
        has gone.
        """
        self.debug('remotecalling removeKeycard with id %s' % keycardId)
        d = self.mindCallRemote('removeKeycard', keycardId)
        d.addErrback(self._mindErrback)
        return d

    def expireKeycard(self, keycardId):
        """
        Expire a keycard issued to this component because the bouncer decided
        to.
        """
        self.debug('remotecalling expireKeycard with id %s' % keycardId)
        d = self.mindCallRemote('expireKeycard', keycardId)
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
            self.vishnu.adminHeaven.componentStateChanged(self, state)
            self.checkFeedReady(feed_name)
            
    def perspective_error(self, element, error):
        self.error('error element=%s string=%s' % (element, error))
        self.heaven.removeComponent(self)

    def perspective_adminCallRemote(self, methodName, *args, **kwargs):
        # proxies admin remote call from component's medium to admin heaven
        componentName = self.avatarId
        self.vishnu.adminHeaven.avatarsCallRemote("componentCall",
            componentName, methodName, *args, **kwargs)

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
        """
        Remove a keycard on the given bouncer on behalf of a component's medium.
        """
        self.debug('asked to remove keycard %s on bouncer %s' % (
            keycardId, bouncerName))
        if not self.heaven.hasComponent(bouncerName):
            self.warning('asked to remove keycard %s on bouncer %s' % (
                (keycardId, bouncerName)) + \
                'but no such component registered')
            # FIXME: return failure object ?
            return False

        bouncerAvatar = self.heaven.getComponent(bouncerName)
        return bouncerAvatar.removeKeycard(keycardId)

    def perspective_expireKeycard(self, requesterName, keycardId):
        """
        Expire a keycard (and thus the requester's connection)
        issued to the given requester.
        """
        # FIXME: we should also be able to expire manager bouncer keycards
        if not self.heaven.hasComponent(requesterName):
            self.warning('asked to expire keycard %s for requester %s, ' % (
                keycardId, requesterName) +
                'but no such component registered')
            raise errors.UnknownComponentError(requesterName)

        componentAvatar = self.heaven.getComponent(requesterName)
        return componentAvatar.expireKeycard(keycardId)

class ComponentHeaven(common.ManagerHeaven):
    """
    I handle all registered components and provide avatars for them.
    """

    __implements__ = interfaces.IHeaven
    avatarClass = ComponentAvatar

    logCategory = 'comp-heaven'
    
    def __init__(self, vishnu):
        """
        @type vishnu:  L{flumotion.manager.manager.Vishnu}
        @param vishnu: the Vishnu object this heaven belongs to
        """
        common.ManagerHeaven.__init__(self, vishnu)
        self._feederSet = FeederSet()
        self._componentEntries = {} # configuration entries
        
    ### IHeaven methods
    def removeAvatar(self, avatarId):
        avatar = self.avatars[avatarId]
        self._feederSet.removeFeeders(avatar)
        self.vishnu.adminHeaven.componentRemoved(avatar)
        
        common.ManagerHeaven.removeAvatar(self, avatarId)
    
    ### our methods
    def _componentIsLocal(self, componentAvatar):
        host = componentAvatar.getClientAddress()
        if host == '127.0.0.1':
            return True
        else:
            return False

    # FIXME: move to base class ?
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
    
    def removeComponent(self, componentAvatar):
        """
        Remove a component from the heaven.

        @type componentAvatar: L{flumotion.manager.component.ComponentAvatar}
        @param componentAvatar: the component
        """

        componentName = componentAvatar.getName()
        self.removeAvatar(componentName)
        
    def loadConfiguration(self, filename, string=None):
        conf = config.FlumotionConfigXML(filename, string)
        
        # get atmosphere and flow entries
        entries = conf.getComponentEntries()
        self.debug('got entries %r from conf %r' % (entries, conf))
        self._componentEntries.update(entries)
        self.debug("added entries for components %r" %
            self._componentEntries.keys())
            
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

        host = componentAvatar.getClientAddress()
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

    # FIXME: better name startComponentIfReady
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
        self.vishnu.adminHeaven.componentAdded(componentAvatar)
        #componentName = componentAvatar.getName()
        #self.vishnu.adminHeaven.uiStateChanged(componentName, state)

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
        for avatar in self.avatars.values():
            avatar.stop()
            
