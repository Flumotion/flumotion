# -*- Mode: Python; test-case-name: flumotion.test.test_manager_manager -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# Flumotion - a streaming media server
# Copyright (C) 2004,2005,2006 Fluendo, S.L. (www.fluendo.com).
# All rights reserved.

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
"""

import time

from twisted.spread import pb
from twisted.internet import reactor, defer, error

from flumotion.configure import configure
# rename to base
from flumotion.manager import base
from flumotion.common import errors, interfaces, keycards, log, config, planet
from flumotion.common import messages, common
from flumotion.twisted import flavors
from flumotion.twisted.defer import defer_generator_method
from flumotion.twisted.compat import implements
from flumotion.common.planet import moods

from flumotion.common.messages import N_
T_ = messages.gettexter('flumotion')

# abstracts the concept of a GStreamer tcpserversink (feeder) producing a feed
class Feeder:
    """
    I am an object used by L{FeederSet}.
    My name is of the form componentName:feedName

    @ivar feedId:    the feed id (componentName:feedName) of the feeder
    @type feedId:    str
    @ivar feedName:  the feed name of the feeder
    @type feedName:  str
    @ivar component: avatar for the component containing this feeder
    @type component: L{flumotion.manager.component.ComponentAvatar}
    """
    def __init__(self, feedId):
        """
        @param feedId: the id (componentName:feedName) of the feeder
        @type  feedId: str
        """
        self._ready = False
        self.feedId = feedId
        self._dependencies = {}
        self.component = None
        
        assert feedId.find(':') != -1, "feedId %s does not contain :" % feedId
        componentName, self.feedName = common.parseFeedId(feedId)
        
    def addDependency(self, feedId, func, *args):
        """
        Add a dependency function for this feeder depending on another
        feeder in another component.  The function will be called when the
        other feeder is ready.

        @param feedId: the name of the feeder (componentName:feedName)
        @type  feedId: str
        @param func:   a function to run when the feeder is ready
        @type  func:   callable
        @param args:   arguments to the function
        """

        if not self._dependencies.has_key(feedId):
            self._dependencies[feedId] = []
            
        self._dependencies[feedId].append((func, args))

    def setComponentAvatar(self, componentAvatar):
        """
        Give the feeder the component avatar that contains the feeder.
        
        @param componentAvatar: avatar for the component containing this feeder
        @type  componentAvatar: L{flumotion.manager.component.ComponentAvatar}
        """
        assert not self.component
        self.component = componentAvatar
        self.component.debug('taken control of feeder %s' % self.getName())

    def setReadiness(self, readiness):
        """
        Set the feeder's readiness, triggering dependency functions.

        @param readiness: bool
        """
        if self._ready == readiness:
            msg = 'readiness already is %r !' % readiness
            self.component.warning(msg)
            raise errors.FlumotionError(msg)

        assert self.component

        self.component.debug('Feeder.setReadiness(%r) on feeder %s' % (
            readiness, self.getName()))
        self._ready = readiness

        for eaterName in self._dependencies.keys():
            for func, args in self._dependencies[eaterName]:
                self.component.debug('running dependency function %r with args %r for eater from %s' % (func, args, eaterName))
                func(readiness, *args)
                
        self._dependencies = {}

    def isReady(self):
        """
        @rtype: bool
        """
        return self._ready

    def hasComponentAvatar(self):
        """
        @rtype: bool
        """
        return self.component != None
    
    def getFeedName(self):
        """
        @rtype: str
        """
        return self.feedName

    def getName(self):
        return self.feedId

    def getListenHost(self):
        # return what we think is the IP address where the component is running
        assert self.component
        return self.component.getClientAddress()

    def getListenPort(self):
        assert self.component
        log.log('feeder',
            'getListenPort(): asking component %s for port of feedName %s' % (
                self.component, self.feedName))
        return self.component.getFeedServerPort()
    
    def __repr__(self):
        return '<Feeder %s on %r ready=%r>' % (self.feedId, self.component or '<unavailable component>', self._ready)
    
class FeederSet(log.Loggable):
    """
    I represent a collection of L{Feeder}s within a flow.
    I know when a feeder is ready and I handle dependencies between feeders.
    """

    logCategory = 'feederset'

    def __init__(self, flowName):
        """
        @ivar flow: name of the flow this feederset manages feeds for
        @type flow: str
        """
        self.flow = flowName
        self.logName = flowName
        self.feeders = {} # feedId -> Feeder

    def __getitem__(self, key):
        return self.feeders[key]
        
    def hasFeeder(self, feedId):
        return self.feeders.has_key(feedId)
    
    def getFeeder(self, feedId):
        return self[feedId]
    
    def addFeeders(self, componentAvatar):
        """
        Add the feeders of the given component to the set.

        @type componentAvatar: L{flumotion.manager.component.ComponentAvatar}
        """

        feedIds = componentAvatar.getFeeders()
        self.debug('addFeeders: feeders %r' % feedIds)

        for feedId in feedIds:
            if not self.hasFeeder(feedId):
                self.debug('adding new Feeder with feedId %s' % feedId)
                self.feeders[feedId] = Feeder(feedId)
            if not self.feeders[feedId].hasComponentAvatar():
                self.debug('setting component %r' % componentAvatar)
                self.feeders[feedId].setComponentAvatar(componentAvatar)
            
    def removeFeeders(self, componentAvatar):
        """
        Remove the feeders of the given component to the set.

        @type componentAvatar: L{flumotion.manager.component.ComponentAvatar}
        """
        
        feedIds = componentAvatar.getFeeders()
        
        for feedId in feedIds:
            if self.hasFeeder(feedId):
                del self.feeders[feedId]
            
    def isFeederReady(self, feedId):
        if not self.hasFeeder(feedId):
            return False

        feeder = self[feedId]

        return feeder.isReady()
    
    def feederSetReadiness(self, feedId, readiness):
        """
        Set the given feeder to the given readiness.
        """
        self.debug('feederSetReadiness: setting feeder %s readiness to %r' % (
            feedId, readiness))

        if not self.feeders.has_key(feedId):
            self.error('FIXME: no feeder called: %s' % feedId)
            return
        
        feeder = self.feeders[feedId]
        feeder.setReadiness(readiness)
            
    def dependComponentOnFeeder(self, componentAvatar, feedId, func):
        """
        Make the given component dependent on the given feeder.
        Register a function and arguments to call when the feeder's readiness
        changes.

        @param componentAvatar: the component to make dependant
        @type  componentAvatar: L{flumotion.manager.component.ComponentAvatar}
        @param feedId:          the feedId of the feeder to depend upon
        @param func:            function to run when feeder changes readiness.
                                function takes (readiness, ComponentAvatar)
        """
        if not self.feeders.has_key(feedId):
            # the component will be set later on
            self.feeders[feedId] = Feeder(feedId)
            
        feeder = self.feeders[feedId]
        
        if not feeder.isReady():
            self.debug('feeder %s is not ready, adding dependency' % feedId)
            feeder.addDependency(feedId, func, componentAvatar)
        else:
            self.debug('feeder %s is ready, executing function %r' % (feedId, func))
            func(True, componentAvatar)

class ComponentAvatar(base.ManagerAvatar):
    """
    Manager-side avatar for a component.
    Each component that logs in to the manager gets an avatar created for it
    in the manager.

    @cvar jobState:       job state of this avatar's component
    @type jobState:       L{flumotion.common.planet.ManagerJobState}
    @cvar componentState: component state of this avatar's component
    @type componentState: L{flumotion.common.planet.ManagerComponentState}
    """

    logCategory = 'comp-avatar'
    implements(flavors.IStateListener)

    def __init__(self, *args, **kwargs):
        # doc in base class
        base.ManagerAvatar.__init__(self, *args, **kwargs)
        
        self.componentState = None # set by the vishnu by componentAttached
        self.jobState = None # retrieved after mind attached

        self._starting = False
        self._ports = {}

        self._shutdown_requested = False
        
    # make sure we don't have stray pendingTimedCalls
    def __del__(self):
        self.cleanup()
        
    ### python methods
    def __repr__(self):
        if self.componentState:
            mood = moods.get(self.componentState.get('mood')).name
        else:
            mood = '(unknown)'
        return '<%s %s (mood %s)>' % (self.__class__.__name__,
                                      self.avatarId, mood)

    ### ComponentAvatar methods
    def cleanup(self):
        """
        Clean up when detaching.
        """
        if self._ports:
            self.vishnu.releasePortsOnWorker(self.getWorkerName(),
                                             self._ports.values())
            
        self._ports = {}

        self.jobState = None

        # At this point, change our mood:
        # if we're sad, we remain sad, always. Otherwise, if we shut down due
        # to an explicit manager request, go to sleeping. Otherwise, go to
        # lost, because it got disconnected for an unknown reason (probably
        # network related)
        if not self._getMoodValue() == moods.sad.value:
            if self._shutdown_requested:
                self.debug("Shutdown was requested, component now sleeping")
                self._setMood(moods.sleeping)
            else:
                self.debug("Shutdown was NOT requested, component now lost")
                self._setMood(moods.lost)

    def _setMood(self, mood):
        if not self.componentState:
            return

        if not self.componentState.get('mood') == mood.value:
            self.debug('Setting mood to %r' % mood)
            self.componentState.set('mood', mood.value)

    def _setMoodValue(self, moodValue):
        mood = moods.get(moodValue)
        self._setMood(mood)

    def _getMoodValue(self):
        if not self.componentState:
            return
        return self.componentState.get('mood')

    def _addMessage(self, message):
        if not self.componentState:
            return

        self.componentState.append('messages', message)

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
        # doc in base class
        self.info('component "%s" logged in' % self.avatarId)
        base.ManagerAvatar.attached(self, mind) # sets self.mind
        
        self.vishnu.componentAttached(self)

        self.debug('mind %r attached, calling remote _getState()' % self.mind)
        self._getState()

    def _getState(self):
        d = self.mindCallRemote('getState')
        d.addCallback(self._mindGetStateCallback)
        d.addErrback(self._mindPipelineErrback)
        #d.addErrback(self._mindErrback)

        # FIXME: return d to serialize ?

    def _mindGetStateCallback(self, state): 
        # called after the mind has attached.
        # state: L{flumotion.common.planet.ManagerJobState}
        if not state:
            # how in god's name is this possible?
            self.warning('no state received yet, rescheduling')
            reactor.callLater(1, self._getState)
            return None
            
        assert isinstance(state, planet.ManagerJobState)
        self.debug('received state: %r' % state)
        self.jobState = state
        # make the component avatar a listener to state changes
        state.addListener(self)
        # make heaven register component
        self.heaven.registerComponent(self)
        self.vishnu.registerComponent(self)

    def detached(self, mind):
        # doc in base class
        self.vishnu.unregisterComponent(self)
        self.heaven.unregisterComponent(self)

        self.info('component "%s" logged out' % self.avatarId)

        self.vishnu.componentDetached(self)
        base.ManagerAvatar.detached(self, mind)

        self.cleanup() # callback and state done at end
 
    # IStateListener methods
    def stateSet(self, state, key, value):
        self.log("state set on %r: %s now %r" % (state, key, value))
        if key == 'mood':
            self.info('Mood changed to %s' % moods.get(value).name)

    def stateAppend(self, state, key, value):
        pass

    def stateRemove(self, state, key, value):
        pass
                
    # my methods
    def _mindPipelineErrback(self, failure):
        failure.trap(errors.PipelineParseError)
        self.error('Invalid pipeline for component')
        self.mindCallRemote('stop')
        return None
        
    # FIXME: rename to something like getEaterFeeders()
    def getEaters(self):
        """
        Get a list of feedId's for feeds this component wants to eat from.

        @return: a list of feedId's, or the empty list
        @rtype:  list of str
        """
        if not self.jobState.hasKey('eaterNames'):
            return []

        # this gets created and added by feedcomponent.py
        return self.jobState.get('eaterNames', [])
    
    def getFeeders(self):
        """
        Get a list of feedId's (componentName:feedName) in this component.
        Obviously, the componentName will be the same for all of them, since
        it's the name of this component, but we return the feedId to be
        similar to getEaters.

        @return: a list of feedId's, or the empty list
        @rtype:  list of str
        """
        # non-feed components don't have these keys
        # FIXME: feederNames need to be renamed, either feedIds or feedNames
        if not self.jobState.hasKey('feederNames'):
            self.warning('no feederNames key, so no feeders')
            return []

        return self.jobState.get('feederNames', [])

    def getFeedServerPort(self):
        """
        Returns the port on which a feed server for this component is
        listening on.

        @rtype: int
        """
        return self.vishnu.getWorkerFeedServerPort(self.getWorkerName())
 
    def getRemoteManagerIP(self):
        """
        Get the IP address of the manager as seen by the component.

        @rtype: str
        """
        return self.jobState.get('ip')

    def getWorkerName(self):
        """
        Return the name of the worker.

        @rtype: str
        """
        return self.jobState.get('workerName')

    def getPid(self):
        """
        Return the PID of the component.

        @rtype: int
        """
        return self.jobState.get('pid')

    def getName(self):
        """
        Get the name of the component.

        @rtype: str
        """
        return self.componentState.get('name')

    def getParentName(self):
        """
        Get the name of the component's parent.

        @rtype: str
        """
        return self.componentState.get('parent').get('name')

    def getType(self):
        """
        Get the component type name of the component.

        @rtype: str
        """
        return self.componentState.get('type')

    def stop(self):
        """
        Tell the avatar to stop the component.
        """
        d = self.mindCallRemote('stop')
        # FIXME: real error handling
        d.addErrback(lambda x: None)
        return d
            
    def setup(self, config):
        """
        Set up the component with the given config.
        Proxies to
        L{flumotion.component.component.BaseComponentMedium.remote_setup}

        @type  config: dict
        """
        def _setupErrback(failure, self):
            self._setMood(moods.sad)
            return failure

        self.debug('remote call setup(config=%r)' % config)
        d = self.mindCallRemote('setup', config)
        d.addErrback(_setupErrback, self)
        return d

    # This function tells the component to start
    # feedcomponents will:
    # - get their eaters connected to the feeders
    # - start up their feeders
    def start(self, eatersData):
        """
        Tell the component to start, possibly linking to other components.

        @param eatersData:  tuple of (fullFeedId, host, port) tuples
                            of elements feeding our eaters
        @type  eatersData:  tuple of (str, str, int) tuples
        """
        self.debug('ComponentAvatar.start(eatersData=%r)' % eatersData)

        config = self.componentState.get('config')
        master = config['clock-master'] # avatarId of the clock master comp
        clocking = None
        if master:
            self.debug('Need to synchronize with clock master %r' % master)
            d = self.heaven.getMasterClockInfo(master, self.avatarId)
            yield d
            try:
                clocking = d.value()
                self.debug('Got master clock info %r' % (clocking, ))
                host, port, base_time = clocking
                # FIXME: the host we get is as seen from the component, so lo
                # mangle it here
                # if the clock master is local (which is what we assume for now)
                # and the slave is not, then we need to tell the slave our
                # IP
                if (not self.heaven._componentIsLocal(self)
                    and host == '127.0.0.1'):
                    host = self.getRemoteManagerIP()
                    self.debug('Overriding clock master host to %s' % host)
                    clocking = (host, port, base_time)

                if master == self.avatarId:
                    self.debug('we are the master, so reset to None')
                    # we needed to wait for the set_master to complete,
                    # but we don't slave the clock to itself...
                    clocking = None
            except Exception, e:
                self.error("Could not make component start, reason %s"
                           % log.getExceptionMessage(e))

        self.debug('calling remote_start on component %r' % self)
        d = self.mindCallRemote('start', clocking)
        yield d
        try:
            d.value()
        except errors.ComponentStartHandledError, e:
            self.debug('already handled error while starting: %s' %
                log.getExceptionMessage(e))
        except Exception, e:
            m = messages.Error(T_(N_("Could not start component.")),
                debug = log.getExceptionMessage(e),
                id = "component-start")
            self._addMessage(m)
            self.warning("Could not make component start, reason %s"
                       % log.getExceptionMessage(e))
            self._setMood(moods.sad)
            raise e
    start = defer_generator_method(start)

    def eatFrom(self, fullFeedId, host, port):
        self.debug('COMPONENTAVATAR --> componentmedium: '
            'callRemote(eatFrom, %s, %s, %d)' % (fullFeedId, host, port))
        d = self.mindCallRemote('eatFrom', fullFeedId, host, port)

        def callback(result):
            self.debug('COMPONENTAVATAR <-- componentmedium: '
                'callRemote(eatFrom, %s, %s, %d): %r' % (
                fullFeedId, host, port, result))
            return result

        def errback(failure):
            self.debug('COMPONENTAVATAR <-- componentmedium: '
                'callRemote(eatFrom, %s, %s, %d): Failure %r' % (
                fullFeedId, host, port, failure))
            return failure
        d.addCallback(callback)
        d.addErrback(errback)
        return d

    def feedTo(self, componentId, feedId, host, port):
        self.debug('COMPONENTAVATAR --> componentmedium: '
            'callRemote(feedTo, %s, %s, %s, %d)' % (
                componentId, feedId, host, port))
        d = self.mindCallRemote('feedTo', componentId, feedId, host, port)

        def callback(result):
            self.debug('COMPONENTAVATAR <-- componentmedium: '
                'callRemote(feedTo, %s, %s, %s, %d): %r' % (
                    componentId, feedId, host, port, result))
            return result

        def errback(failure):
            self.debug('COMPONENTAVATAR <-- componentmedium: '
                'callRemote(feedTo, %s, %s, %s, %d): %r' % (
                    componentId, feedId, host, port, failure))
            return failure
        d.addCallback(callback)
        d.addErrback(errback)
        return d
  
    def setElementProperty(self, element, property, value):
        """
        Set a property on an element.

        @param element:  the element to set the property on
        @type  element:  str
        @param property: the property to set
        @type  property: str
        @param value:    the value to set the property to
        @type  value:    mixed
        """
        if not element:
            msg = "%s: no element specified" % self.avatarId
            self.warning(msg)
            raise errors.PropertyError(msg)
        if not element in self.jobState.get('elements'):
            msg = "%s: element '%s' does not exist" % (self.avatarId, element)
            self.warning(msg)
            raise errors.PropertyError(msg)
        if not property:
            msg = "%s: no property specified" % self.avatarId
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

        @param element:  the element to get the property of
        @type  element:  str
        @param property: the property to get
        @type  property: str
        """
        if not element:
            msg = "%s: no element specified" % self.avatarId
            self.warning(msg)
            raise errors.PropertyError(msg)
        # FIXME: this is wrong, since it's not dynamic.  Elements can be
        # renamed
        # this will work automatically though if the component updates its
        # state
        if not element in self.jobState.get('elements'):
            msg = "%s: element '%s' does not exist" % (self.avatarId, element)
            self.warning(msg)
            raise errors.PropertyError(msg)
        if not property:
            msg = "%s: no property specified" % self.avatarId
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
        def _reloadComponentErrback(failure, self):
            failure.trap(errors.ReloadSyntaxError)
            self.warning(failure.getErrorMessage())
            print "Ignore the following Traceback line, issue in Twisted"
            return failure

        d = self.mindCallRemote('reloadComponent')
        d.addErrback(_reloadComponentErrback, self)
        d.addErrback(self._mindErrback, errors.ReloadSyntaxError)
        return d

    # FIXME: maybe make a BouncerComponentAvatar subclass ?
    def authenticate(self, keycard):
        """
        Authenticate the given keycard.
        Gets proxied to L{flumotion.component.bouncers.bouncer.""" \
        """BouncerMedium.remote_authenticate}
        The component should be a subclass of
        L{flumotion.component.bouncers.bouncer.Bouncer}

        @type  keycard: L{flumotion.common.keycards.Keycard}
        """
        d = self.mindCallRemote('authenticate', keycard)
        d.addErrback(self._mindErrback)
        return d

    def removeKeycardId(self, keycardId):
        """
        Remove a keycard managed by this bouncer because the requester
        has gone.

        @type  keycardId: str
        """
        self.debug('remotecalling removeKeycardId with id %s' % keycardId)
        d = self.mindCallRemote('removeKeycardId', keycardId)
        d.addErrback(self._mindErrback)
        return d

    def expireKeycard(self, keycardId):
        """
        Expire a keycard issued to this component because the bouncer decided
        to.

        @type  keycardId: str
        """
        self.debug('remotecalling expireKeycard with id %s' % keycardId)
        d = self.mindCallRemote('expireKeycard', keycardId)
        d.addErrback(self._mindErrback)
        return d

    ### IPerspective methods, called by the worker's component
    def perspective_feedReady(self, feedName, isReady):
        """
        Called by the component to tell the manager that a given feed is
        ready or not. Will notify other components depending on this
        feeder, starting them if all of their dependencies are ready.

        @param feedName: name of the feeder, e.g. "default".
        @type  feedName: str
        @param isReady:  True if the feed is now ready, False otherwise.
        @type  isReady:  bool
        """
        assert isinstance(feedName, str)
        self.heaven.setFeederReadiness(self, feedName, isReady)

    def perspective_cleanShutdown(self):
        """
        Called by a component to tell the manager that it's shutting down
        cleanly (and thus should go to sleeping, rather than lost or sad)
        """
        self.debug("shutdown is clean, shouldn't go to lost")
        self._shutdown_requested = True

    def perspective_error(self, element, error):
        self.error('error element=%s string=%s' % (element, error))
        self.heaven.removeComponent(self)

    def perspective_removeKeycardId(self, bouncerName, keycardId):
        """
        Remove a keycard on the given bouncer on behalf of a component's medium.

        This is requested by a component that created the keycard.

        @type  bouncerName: str
        @param keycardId:   id of keycard to remove
        @type  keycardId:   str
        """
        self.debug('asked to remove keycard %s on bouncer %s' % (
            keycardId, bouncerName))
        avatarId = '/atmosphere/%s' % bouncerName
        if not self.heaven.hasAvatar(avatarId):
            self.warning('No bouncer with id %s registered' % avatarId)
            raise errors.UnknownComponentError(avatarId)

        bouncerAvatar = self.heaven.getAvatar(avatarId)
        return bouncerAvatar.removeKeycardId(keycardId)

    def perspective_expireKeycard(self, requesterId, keycardId):
        """
        Expire a keycard (and thus the requester's connection)
        issued to the given requester.

        This is called by the bouncer component that authenticated the keycard.

        
        @param requesterId: name (avatarId) of the component that originally
                              requested authentication for the given keycardId
        @type  requesterId: str
        @param keycardId:     id of keycard to expire
        @type  keycardId:     str
        """
        # FIXME: we should also be able to expire manager bouncer keycards
        if not self.heaven.hasAvatar(requesterId):
            self.warning('asked to expire keycard %s for requester %s, ' % (
                keycardId, requesterId) +
                'but no such component registered')
            raise errors.UnknownComponentError(requesterId)

        componentAvatar = self.heaven.getAvatar(requesterId)
        return componentAvatar.expireKeycard(keycardId)

    def perspective_reservePortsOnWorker(self, workerName, numberOfPorts):
        """
        Request reservation a number of ports on a particular worker.
        This can be called from a job if it needs some ports itself.

        @param workerName:    name of the worker to reserve ports on
        @type  workerName:    str
        @param numberOfPorts: the number of ports to reserve
        @type  numberOfPorts: int
        """
        ports = self.heaven.vishnu.reservePortsOnWorker(workerName, 
            numberOfPorts)
        return ports

class ComponentHeaven(base.ManagerHeaven):
    """
    I handle all registered components and provide avatars for them.
    """

    implements(interfaces.IHeaven)
    avatarClass = ComponentAvatar

    logCategory = 'comp-heaven'
    
    def __init__(self, vishnu):
        # doc in base class
        base.ManagerHeaven.__init__(self, vishnu)
        self._feederSets = {} # flowName -> FeederSet

        # hash of clock master avatarId ->
        # list of (deferreds, avatarId) created by getMasterClockInfo
        self._clockMasterWaiters = {}
        self._masterClockInfo = {}
        
    ### our methods
    def _componentIsLocal(self, componentAvatar):
        # gets what we think is the other side's address
        host = componentAvatar.getClientAddress()

        if host == '127.0.0.1':
            return True
        else:
            return False

    def _getFeederSet(self, componentAvatar):
        # get the feederset this component is part of, creating a new one
        # if needed
        parent = componentAvatar.getParentName()
        if not parent in self._feederSets.keys():
            self.debug('creating feederset for parent %s' % parent)
            self._feederSets[parent] = FeederSet(parent)

        r = self._feederSets[parent]
        return r

    def removeComponent(self, componentAvatar):
        """
        Remove a component avatar from the heaven.

        @param componentAvatar: the component to remove
        @type  componentAvatar: L{flumotion.manager.component.ComponentAvatar}
        """
        self.removeAvatar(componentAvatar.avatarId)
        
    def _getComponentEatersData(self, componentAvatar):
        """
        Retrieve the information about the feeders this component's eaters
        are eating from.

        @param componentAvatar: the component
        @type  componentAvatar: L{flumotion.manager.component.ComponentAvatar}

        @returns: tuple of fullFeedId, host name and port, or None
        @rtype:   tuple of (str, str, int)
        """
        eaterFeedIds = componentAvatar.getEaters()
        self.debug('feeds we eat: %r' % eaterFeedIds)

        retval = []
        set = self._getFeederSet(componentAvatar)
        for feedId in eaterFeedIds:
            feeder = set.getFeeder(feedId)
            (componentName, feedName) = common.parseFeedId(feedId)
            flowName = set.flow
            fullFeedId = common.fullFeedId(flowName, componentName, feedName)

            # what host do we need to connect to, as seen from manager ?
            # FIXME: this needs to work across every host, not just from
            # manager
            host = feeder.getListenHost()

            # if the feeder is local, and the eater isn't, then we need to
            # tell the eater to connect to the manager's host
            if (not self._componentIsLocal(componentAvatar)
                and host == '127.0.0.1'):
                host = componentAvatar.getRemoteManagerIP()

            port = feeder.getListenPort()
            self.debug('EatersData(): feeder %r, host %s, port %d' % (
                feeder, host, port))
            retval.append((fullFeedId, host, port))
        return retval

    def _getComponentFeedersData(self, component):
        """
        Retrieves the data of feeders (feed producer elements) for a component.

        @param component: the component
        @type  component: L{flumotion.manager.component.ComponentAvatar}

        @returns: tuple of (feedId, host, port) for each feeder
        @rtype:   tuple of (str, str, int) tuple
        """
        # FIXME: host and port are constant for all the feedIds, so
        # maybe we should return host, port, list-of-feeders

        # get what we think is the IP address where the component is running
        host = component.getClientAddress()
        port = component.getFeedServerPort()
        feedIds = component.getFeeders()
        self.debug('returning data for feeders: %r' % (feedIds, ))
        return map(lambda f: (f, host, port), feedIds)

    def _startComponent(self, componentAvatar):
        state = componentAvatar.componentState
        config = state.get('config')
    
        # provide master clock if needed
        if config['clock-master'] == componentAvatar.avatarId:
            # houston, we have a master clock
            self.debug('telling component %s to be the clock master' %
                componentAvatar.avatarId)
            yield self.provideMasterClock(componentAvatar)

        # connect the component's eaters
        eatersData = self._getComponentEatersData(componentAvatar)
        for (fullFeedId, h, p) in eatersData:
            self.debug('connecting eater of feed %s' % fullFeedId)
            # FIXME: ideally we would get this from the config
            # downstream makes more sense since it's more likely
            # for a producer to be behind NAT
            connection = "downstream"

            if connection == "upstream":
                self.debug('connecting from eater to feeder')
                # find avatar that feeds this feed
                (flowName, componentName, feedName) = common.parseFullFeedId(
                    fullFeedId)
                avatarId = common.componentId(flowName, componentName)
                feederAvatar = self.getAvatar(avatarId)
                # FIXME: get from network map instead
                host = feederAvatar.getClientAddress()
                port = feederAvatar.getFeedServerPort()

                d = componentAvatar.eatFrom(fullFeedId, host, port)
                yield d
                try:
                    d.value()
                except error.ConnectionRefusedError, e:
                    m = messages.Error(T_(
                        N_("Could not connect component to %s:%d for feed %s."),
                            host, port, fullFeedId),
                        debug=log.getExceptionMessage(e),
                        id="component-start-%s" % fullFeedId)
                    # FIXME: make addMessage and setMood public
                    componentAvatar._addMessage(m)
                    componentAvatar._setMood(moods.sad)
                    raise errors.ComponentStartHandledError(e)
            elif connection == "downstream":
                self.debug('connecting from feeder to eater')
                # find avatar that feeds this feed
                (flowName, componentName, feedName) = common.parseFullFeedId(
                    fullFeedId)
                feederAvatarId = common.componentId(flowName, componentName)
                feederAvatar = self.getAvatar(feederAvatarId)
                # FIXME: get from network map instead
                host = componentAvatar.getClientAddress()
                port = componentAvatar.getFeedServerPort()
                d = feederAvatar.feedTo(componentAvatar.avatarId,
                    common.feedId(componentName, feedName), host, port)
                yield d
                try:
                    d.value()
                except error.ConnectionRefusedError, e:
                    m = messages.Error(T_(
                        N_("Could not connect to %s:%d for feed %s."),
                            host, port, fullFeedId),
                        debug=log.getExceptionMessage(e),
                        id="component-start-%s" % fullFeedId)
                    self._addMessage(m)
                    self._setMood(moods.sad)
                    raise errors.ComponentStartHandledError


        componentAvatar.debug(
            'starting component with eatersData %r' % eatersData)
        try:
            componentAvatar.start(eatersData)
        except errors.ComponentStartHandledError, e:
            pass
    _startComponent = defer_generator_method(_startComponent)

    # FIXME: better name startComponentIfReady
    def checkComponentStart(self, readiness, componentAvatar):
        """
        Check if the component can start up, and start it if it can.
        This depends on whether the components and feeders it depends on have
        started.

        @param componentAvatar: the component to check
        @type  componentAvatar: L{flumotion.manager.component.ComponentAvatar}
        """
        componentAvatar.debug('checkComponentStart')
        
        set = self._getFeederSet(componentAvatar)
        for eaterFeeder in componentAvatar.getEaters():
            if not set.isFeederReady(eaterFeeder):
                componentAvatar.debug('feeder %s is not ready' % (eaterFeeder))
                return

        # FIXME: change this to mood
        if componentAvatar._starting:
            return
        
        componentAvatar._starting = True
        self._startComponent(componentAvatar)
        
    def registerComponent(self, componentAvatar):
        """
        This function registers a component in the heaven.
        It is triggered when the mind is attached.

        @param componentAvatar: the component to register
        @type  componentAvatar: L{flumotion.manager.component.ComponentAvatar}

        @rtype: L{twisted.internet.defer.Deferred}
        """
        self.debug('heaven registering component %r' % componentAvatar)

        # ensure it has a parent -- the parent will be null if this is
        # an already-running worker connects to a freshly restarted
        # manager
        state = componentAvatar.componentState
        if not state:
            self.warning('Implement manager connection sniffing')
            return

        if not state.get('parent'):
            # parent is normally set by the manager when creating a flow
            # from an xml file. in this case we get a state, and
            # reconstruct the parent. unfortunately we have to do it by
            # parsing the avatar id, but hey, life isn't perfect.
            flowName = componentAvatar.avatarId.split('/')[1]
            flows = self.vishnu.state.get('flows')
            try:
                flow = dict([(x.get('name'),x) for x in flows])[flowName]
            except KeyError:
                # FIXME: this is just copied from manager.py
                self.info('Creating flow "%s"' % flowName)
                flow = planet.ManagerFlowState()
                flow.set('name', flowName)
                flow.set('parent', self.vishnu.state)
                self.vishnu.state.append('flows', flow)
            state.set('parent', flow)
            flow.append('components', state)

        # set up the component so we have feeders and eaters
        state = componentAvatar.componentState
        config = state.get('config')

        self.debug('setting up componentAvatar %r' % componentAvatar)
        d = componentAvatar.setup(config)
        yield d

        try:
            d.value()
        except errors.ComponentSetupError, e:
            self.warning('Failed to setup component')
            # FIXME: we cannot start it - is there any reason to go on ?
            return
        except Exception, e:
            self.warning('setup failed:%s' % log.getExceptionMessage(e))
            raise errors.FlumotionError('Could not set up component')

        # tell the feeder set
        set = self._getFeederSet(componentAvatar)
        set.addFeeders(componentAvatar)

        # check if we eat feeds from other feeders
        self.debug('checking if %r eats feeds' % componentAvatar)
        eaterFeeders = componentAvatar.getEaters()
        if not eaterFeeders:
            componentAvatar.debug(
                'component does not eat feeds, so starting it right away')
            self._startComponent(componentAvatar)
            self.debug('heaven registered component %r' % componentAvatar)
            return

        # we do, so we need to make our eaters depend on other feeders
        componentAvatar.debug('need to wait for %s' % eaterFeeders)
        set = self._getFeederSet(componentAvatar)

        for feeder in eaterFeeders:
            set.dependComponentOnFeeder(componentAvatar, feeder,
                self.checkComponentStart)

        self.debug('heaven registered component %r' % componentAvatar)
    registerComponent = defer_generator_method(registerComponent)

    def unregisterComponent(self, componentAvatar):
        """
        This function unregisters a component in the heaven.
        It is triggered when the mind is detached.

        @param componentAvatar: the component to unregister
        @type  componentAvatar: L{flumotion.manager.component.ComponentAvatar}
        """
        componentAvatar.debug('unregistering component')

        # tell the feeder set
        set = self._getFeederSet(componentAvatar)
        set.removeFeeders(componentAvatar)

        config = componentAvatar.componentState.get('config')
        if config['clock-master'] == componentAvatar.avatarId:
            # houston, we have a master clock
            self.removeMasterClock(componentAvatar)

        # clean up component
        componentAvatar.cleanup()

    def setFeederReadiness(self, componentAvatar, feedName, readiness):
        """
        Tell the feeder set that the given feed on the given component is
        ready.
        
        @param componentAvatar: the component containing the feed
        @type  componentAvatar: str
        @param feedName:        the feed set to ready
        @type  feedName:        str
        @param readiness:       whether this feed has become ready or not
        @type  readiness:       boolean
        """

        feedId = common.feedId(componentAvatar.getName(), feedName)
        componentAvatar.debug(
            'setting feeder %s readiness to %s in feederset' % (
                feedId, readiness))
        set = self._getFeederSet(componentAvatar)
        set.feederSetReadiness(feedId, readiness)

    def provideMasterClock(self, componentAvatar):
        """
        Tell the given component to provide a master clock.
        Trigger all deferreds waiting on this componentAvatar to provide
        a master clock.
        
        @type componentAvatar: L{ComponentAvatar}
        
        @rtype: L{twisted.internet.defer.Deferred}
        """
        avatarId = componentAvatar.avatarId
        self.debug('provideMasterClock on component %s' % avatarId)

        def setMasterClockInfo(result):
            # we get host, port, base_time
            # FIXME: host is the default from NetClock, so the local IP,
            # always.  A little inconvenient.
            self._masterClockInfo[avatarId] = result
            return result

        def wakeClockMasterWaiters(result):
            self.info('Received master clock info from clock master %s' %
                avatarId)
            self.debug('got master clock info: %r' % (result, ))

            # wake all components waiting on the clock master info
            if avatarId in self._clockMasterWaiters:
                waiters = self._clockMasterWaiters[avatarId]
                del self._clockMasterWaiters[avatarId]
                for d, waiterId in waiters:
                    self.debug(
                        'giving master clock info to waiting component %s' %
                        waiterId)
                    d.callback(result)

        workerName = componentAvatar.getWorkerName()
        port = self.vishnu.reservePortsOnWorker(workerName, 1)[0]

        if avatarId in self._masterClockInfo:
            self.warning('component %s already has master clock info: %r'
                         % (avatarId, self._masterClockInfo[avatarId]))
            del self._masterClockInfo[avatarId]
        d = componentAvatar.mindCallRemote('provideMasterClock', port)
        d.addCallback(setMasterClockInfo)
        d.addCallback(wakeClockMasterWaiters)
        return d

    def removeMasterClock(self, componentAvatar):
        """
        Tell the given component to stop providing a master clock.
        
        @type componentAvatar: L{ComponentAvatar}
        """
 
        avatarId = componentAvatar.avatarId
        workerName = componentAvatar.getWorkerName()

        # if any components were waiting on master clock info from this
        # clock master, errback them
        if avatarId in self._clockMasterWaiters:
            waiters = self._clockMasterWaiters[avatarId]
            del self._clockMasterWaiters[avatarId]
            for d, waiterId in waiters:
                self.debug('telling waiting component %s that '
                    'the clock master %s is gone' % (waiterId, avatarId))
                d.errback(errors.ComponentStartError(
                    'clock master component start cancelled'))

        # release our clock port
        if avatarId in self._masterClockInfo:
            info = self._masterClockInfo[avatarId]
            if info:
                port = info[1]
                self.vishnu.releasePortsOnWorker(workerName, [port])
            else:
                self.debug('avatarId %r has None masterClockInfo' % avatarId)
            del self._masterClockInfo[avatarId]
        else:
            self.warning('component %s has no master clock info'
                         % (avatarId,))

    def getMasterClockInfo(self, avatarId, waiterId=None):
        """
        Get the master clock information from the given clock master component.

        @param avatarId: the id of the clock master
        @type  avatarId: str
        @param waiterId: the id of the requesting component
        @type  waiterId: str

        @returns: a deferred firing an (ip, port, base_time) triple.
        @rtype:   L{twisted.internet.defer.Deferred}
        """
        self.debug('getting master clock info for component %s' % avatarId)

        # if we already have it, return it immediately
        if avatarId in self._masterClockInfo:
            return defer.succeed(self._masterClockInfo[avatarId])

        if not avatarId in self._clockMasterWaiters:
            self._clockMasterWaiters[avatarId] = []

        # otherwise, add a deferred and our own avatarId
        ret = defer.Deferred()
        self._clockMasterWaiters[avatarId].append((ret, waiterId))
        return ret

