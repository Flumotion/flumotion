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
from twisted.python.failure import Failure

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

class ComponentAvatar(base.ManagerAvatar):
    """
    I am a Manager-side avatar for a component.
    I live in the L{ComponentHeaven}.

    Each component that logs in to the manager gets an avatar created for it
    in the manager.

    @cvar avatarId:       the L{componentId<common.componentId>}
    @type avatarId:       str
    @cvar jobState:       job state of this avatar's component
    @type jobState:       L{flumotion.common.planet.ManagerJobState}
    @cvar componentState: component state of this avatar's component
    @type componentState: L{flumotion.common.planet.ManagerComponentState}
    """

    logCategory = 'comp-avatar'

    def __init__(self, *args, **kwargs):
        # doc in base class
        base.ManagerAvatar.__init__(self, *args, **kwargs)
        
        self.componentState = None # set by the vishnu by componentAttached
        self.jobState = None # set by the vishnu by componentAttached

        # these flags say when this component is in the middle of doing stuff
        # starting, setup and providing master clock respectively
        self._starting = False
        self._beingSetup = False
        self._providingClock = False

        self._ports = {}

        self._shutdown_requested = False

        self._happydefers = [] # deferreds to call when mood changes to happy
        self.feeder_names = []
        self.eater_names = []
        
    ### python methods
    def __repr__(self):
        mood = '(unknown)'
        if self.componentState:
            moodValue = self.componentState.get('mood')
            if moodValue is not None:
                mood = moods.get(moodValue).name
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
        self.warning("Unhandled remote call error: %s" %
            failure.getErrorMessage())
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
        
        d = self.vishnu.componentAttached(self)
        # listen to the mood so we can tell the depgraph
        d.addCallback(lambda _: self.jobState.addListener(self,
                                                          set=self.stateSet))
        # make heaven register component
        d.addCallback(lambda _: self.heaven.registerComponent(self))
        d.addCallback(lambda _: self.vishnu.registerComponent(self))
        return d

    def detached(self, mind):
        # doc in base class
        self.vishnu.unregisterComponent(self)
        self.heaven.unregisterComponent(self)

        self.info('component "%s" logged out' % self.avatarId)

        # Now, we're detached: set our state to sleeping (or lost). 
        # Do this before vishnu.componentDetached() severs our association 
        # with our componentState. Also, don't ever remove 'sad' here.
        # If we shut down due to an explicit manager request, go to sleeping. 
        # Otherwise, go to lost, because it got disconnected for an unknown 
        # reason (probably network related)
        if not self._getMoodValue() == moods.sad.value:
            if self._shutdown_requested:
                self.debug("Shutdown was requested, component now sleeping")
                self._setMood(moods.sleeping)
            else:
                self.debug("Shutdown was NOT requested, component now lost")
                self._setMood(moods.lost)

        self.vishnu.componentDetached(self)
        base.ManagerAvatar.detached(self, mind)

        self.cleanup() # callback done at end
 
    # IStateListener methods
    def stateSet(self, state, key, value):
        self.log("state set on %r: %s now %r" % (state, key, value))
        if key == 'mood':
            self.info('Mood changed to %s' % moods.get(value).name)

            if value == moods.happy.value:
                self.vishnu._depgraph.setComponentStarted(self.componentState)
                # component not starting anymore
                self._starting = False
                # callback any deferreds waiting on this
                for d in self._happydefers:
                    d.callback(True)
                self._happydefers = []

    # my methods
    def parseEaterConfig(self, eater_config):
        # the source feeder names come from the config
        # they are specified under <component> as <source> elements in XML
        # so if they don't specify a feed name, use "default" as the feed name
        eater_names = []
        for block in eater_config:
            eater_name = block
            if block.find(':') == -1:
                eater_name = block + ':default'
            eater_names.append(eater_name)
        self.debug('parsed eater config, eaters %r' % eater_names)
        self.eater_names = eater_names

    def parseFeederConfig(self, feeder_config):
        # for pipeline components, in the case there is only one
        # feeder, <feed></feed> still needs to be listed explicitly

        # the feed names come from the config
        # they are specified under <component> as <feed> elements in XML
        feed_names = feeder_config
        #self.debug("parseFeederConfig: feed_names: %r" % self.feed_names)
        name = self.componentState.get('name')
        # we create feeder names this component contains based on feed names
        self.feeder_names = map(lambda n: name + ':' + n, feed_names)
        self.debug('parsed feeder config, feeders %r' % self.feeder_names)

    # FIXME: rename to something like getEaterFeeders()
    def getEaters(self):
        """
        Get a list of L{feedId<flumotion.common.common.feedId>}s
        for feeds this component wants to eat from.

        @return: a list of feedId's, or the empty list
        @rtype:  list of str
        """
        if not self.eater_names:
            return []

        # this gets created and added by feedcomponent.py
        return self.eater_names
    
    def getFeeders(self):
        """
        Get a list of L{feedId<flumotion.common.common.feedId>}s that this
        component has feeders for.

        Obviously, the componentName part will be the same for all of them,
        since it's the name of this component, but we return the feedId to be
        similar to getEaters.

        @return: a list of feedId's, or the empty list
        @rtype:  list of str
        """
        # non-feed components don't have these keys
        # FIXME: feederNames need to be renamed, either feedIds or feedNames
        if not self.feeder_names:
            self.warning('no feederNames key, so no feeders')
            return []

        return self.feeder_names

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
            
    def setup(self, conf):
        """
        Set up the component with the given config.
        Proxies to
        L{flumotion.component.component.BaseComponentMedium.remote_setup}

        @type  conf: dict
        """
        def _setupErrback(failure):
            self._setMood(moods.sad)
            return failure

        d = self.mindCallRemote('setup', conf)
        d.addErrback(_setupErrback)
        return d

    # This function tells the component to start
    # feedcomponents will:
    # - get their eaters connected to the feeders
    # - start up their feeders
    def start(self):
        """
        Tell the component to start, possibly linking to other components.
        """
        self.debug('start')
        conf = self.componentState.get('config')
        master = conf['clock-master'] # avatarId of the clock master comp
        clocking = None
        if master != self.avatarId and master != None:
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
                id="component-start")
            self._addMessage(m)
            self.warning("Could not make component start, reason %s"
                       % log.getExceptionMessage(e))
            self._setMood(moods.sad)
            raise
    start = defer_generator_method(start)

    def eatFrom(self, fullFeedId, host, port):
        d = self.mindCallRemote('eatFrom', fullFeedId, host, port)
        return d

    def feedTo(self, componentId, feedId, host, port):
        d = self.mindCallRemote('feedTo', componentId, feedId, host, port)
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
        @deprecated      Don't call this!
        """
        assert isinstance(feedName, str)

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
    I handle all registered components and provide L{ComponentAvatar}s
    for them.
    """

    implements(interfaces.IHeaven)
    avatarClass = ComponentAvatar

    logCategory = 'comp-heaven'
    
    def __init__(self, vishnu):
        # doc in base class
        base.ManagerHeaven.__init__(self, vishnu)

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

        @returns: list of fullFeedIds
        """
        componentId = componentAvatar.avatarId
        eaterFeedIds = componentAvatar.getEaters()
        self.debug('feeds we eat: %r' % eaterFeedIds)

        retval = []
        for feedId in eaterFeedIds:
            (componentName, feedName) = common.parseFeedId(feedId)
            flowName = common.parseComponentId(componentId)[0]
            fullFeedId = common.fullFeedId(flowName, componentName, feedName)

            retval.append(fullFeedId)

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
        self.debug('returning data for feeders: %r', feedIds)
        return map(lambda f: (f, host, port), feedIds)

    def _startComponent(self, componentAvatar):
        state = componentAvatar.componentState
        conf = state.get('config')
    
        # connect the component's eaters
        eatersData = self._getComponentEatersData(componentAvatar)
        for fullFeedId in eatersData:
            self.debug('connecting eater of feed %s' % fullFeedId)
            # FIXME: ideally we would get this from the config
            # downstream makes more sense since it's more likely
            # for a producer to be behind NAT
            connection = "upstream"

            if connection == "upstream":
                self.debug('connecting from eater to feeder')
                # find avatar that feeds this feed
                (flowName, componentName, feedName) = common.parseFullFeedId(
                    fullFeedId)
                avatarId = common.componentId(flowName, componentName)
                feederAvatar = self.getAvatar(avatarId)
                if not feederAvatar:
                    m = messages.Error(T_(
                        N_("Configuration problem.")),
                        debug="No component '%s'." % avatarId,
                        id="component-start-%s" % fullFeedId)
                    # FIXME: make addMessage and setMood public
                    componentAvatar._addMessage(m)
                    componentAvatar._setMood(moods.sad)
 
                # FIXME: get from network map instead
                host = feederAvatar.getClientAddress()
                port = feederAvatar.getFeedServerPort()

                # FIXME: until network map is implemented, hack to
                # assume that connections from what appears to us to be
                # the same IP go through localhost instead. Allows
                # connections between components on a worker behind a
                # firewall, but not between components running on
                # different workers, both behind a firewall
                eaterHost = componentAvatar.mind.broker.transport.getPeer().host
                if eaterHost == host:
                    host = '127.0.0.1'

                d = componentAvatar.eatFrom(fullFeedId, host, port)
                yield d
                try:
                    d.value()
                except (error.ConnectError, error.ConnectionRefusedError), e:
                    m = messages.Error(T_(
                        N_("Could not connect component to %s:%d for feed %s."),
                            host, port, fullFeedId),
                        debug=log.getExceptionMessage(e, filename='component'),
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

        componentAvatar.debug('starting component')
        try:
            componentAvatar.start()
        except errors.ComponentStartHandledError, e:
            pass
    _startComponent = defer_generator_method(_startComponent)

    def _tryWhatCanBeStarted(self, result=True):
        """
        I try to start nodes in the depgraph if they should be started.  I am
        a recursive method, because the depgraph's list of what should be
        started may change when nodes start/stop.
        
        @param result: only needed because this method is added as a callback
        """
        
        # Generic failure handler for 
        # synchronous and asynchronous errors
        def handleFailure(failure, avatar, message, id_template):
            log.warningFailure(failure, swallow=False)
            if failure.check(errors.HandledException):
                self.debug('failure %r already handled' % failure)
                return                                        
            self.debug('showing error message for failure %r' % failure)            
            m = messages.Error(message, 
               id=id_template % componentAvatar.avatarId,
               debug=log.getFailureMessage(failure))
            avatar._addMessage(m)
            avatar._setMood(moods.sad)

        self.debug("tryWhatCanBeStarted")
        deplist = self.vishnu._depgraph.whatShouldBeStarted()
        self.debug("Listing deplist")

        if not deplist:
            self.debug("Nothing needs to be setup or started!")
            return
        for dep in deplist:
            self.debug("Deplist: %r,%r" % (dep[0], dep[1]))

        # we handle all direct dependencies;
        # an error for one of them shouldn't stop handling the others
        for dep, deptype in deplist:
            if dep:
                if deptype == "COMPONENTSETUP":
                    self.debug("Component %s to be setup" % dep.get("name"))
                    componentAvatar = self.getComponentAvatarForState(dep)
                    if componentAvatar:
                        if not componentAvatar._beingSetup:
                            componentAvatar._beingSetup = True
                            # specific setup failure handler
                            def componentSetupFailed(failure):
                                componentAvatar._beingSetup = False                            
                                handleFailure(failure, componentAvatar,
                                         T_(N_("Could not setup component.")),
                                         "component-setup-%s")
                            try:
                                d = self.setupComponent(componentAvatar)
                            except:
                                # give feedback of synchronous failures 
                                # to the componentAvatar, and resume the loop
                                componentSetupFailed(Failure())
                                continue
                            # add callback because nodes that can be
                            # started as a result of this component being
                            # setup may not be in the current list, and
                            # add errback to be able to give feedback
                            # of asynchronous failures to the componentAvatar.
                            def setupErrback(failure):
                                componentSetupFailed(failure)
                                raise errors.ComponentSetupHandledError(failure)                            
                            d.addCallbacks(self._tryWhatCanBeStarted, 
                                setupErrback)
                        else:
                            self.debug(
                                "Component %s already on way to being setup",
                                dep.get("name"))
                    else:
                        self.debug(
                            "Component %s to be setup but has no avatar yet",
                                dep.get("name"))
                elif deptype == "COMPONENTSTART":
                    self.debug("Component %s to be started" % dep.get("name"))
                    componentAvatar = self.getComponentAvatarForState(dep)
                    if not componentAvatar._starting:
                        componentAvatar._starting = True
                        happyd = defer.Deferred()
                        # since we've reached happy, we should clear the pending
                        # mood - it is done transitioning
                        happyd.addCallback(lambda r, s: s.set(
                            'moodPending', None), 
                            componentAvatar.componentState)
                        # add callback because nodes that can be
                        # started as a result of this component being
                        # happy may not be in the current list.
                        happyd.addCallback(self._tryWhatCanBeStarted)
                        componentAvatar._happydefers.append(happyd)

                        # specific startup failure handler
                        def componentStartupFailed(failure):
                            componentAvatar._starting = False
                            handleFailure(failure, componentAvatar,
                                         T_(N_("Could not start component.")),
                                         "component-start-%s")
                        try:
                            d = self._startComponent(componentAvatar)
                        except:
                            # give feedback of synchronous failures 
                            # to the componentAvatar, and resume the loop
                            componentStartupFailed(Failure())
                            continue                        
                        # add errback to be able to give feedback
                        # of asynchronous failures to the componentAvatar.
                        def startErrback(failure):
                            componentStartupFailed(failure)
                            raise errors.ComponentStartHandledError(failure)
                        d.addErrback(startErrback)
                    else:
                        self.log("Component is already starting")
                elif deptype == "CLOCKMASTER":
                    self.debug("Component %s to be clock master!",
                        dep.get("name"))
                    componentAvatar = self.getComponentAvatarForState(dep)
                    if componentAvatar:
                        if not componentAvatar._providingClock:
                            componentAvatar._providingClock = True
                            # specific master clock failure handler
                            def componentMasterClockFailed(failure):
                                componentAvatar._providingClock = False
                                handleFailure(failure, componentAvatar,
                                      T_(N_("Could not setup component's master clock.")),
                                      "component-clock-%s")
                            try:
                                d = self.provideMasterClock(componentAvatar)
                            except:
                                # give feedback of synchronous failures 
                                # to the componentAvatar and resume the loop
                                componentMasterClockFailed(Failure())
                                continue                                
                            # add callback because nodes that can be
                            # started as a result of this component providing
                            # master clock may not be in the current list, and
                            # add errback to be able to give feedback
                            # of asynchronous failures to the componentAvatar.
                            def clockMasterErrback(failure):
                                componentMasterClockFailed(failure)
                                raise errors.ComponentStartHandledError(failure)                            
                            d.addCallbacks(self._tryWhatCanBeStarted, 
                                clockMasterErrback)
                        else:
                            self.debug(
                                "Component %s already on way to clock master", 
                                dep.get("name"))
                else:
                    self.debug("Unknown dependency type")

    def _setupComponent(self, componentAvatar):
        # set up the component
        state = componentAvatar.componentState
        conf = state.get('config')
        eater_config = conf.get('source', [])
        feeder_config = conf.get('feed', [])
        componentAvatar.parseEaterConfig(eater_config)
        componentAvatar.parseFeederConfig(feeder_config)

        self.debug('setting up componentAvatar %r' % componentAvatar)
        d = componentAvatar.setup(conf)
        yield d

        try:
            d.value()
            self.debug("componentAvatar %r now setup" % componentAvatar)
            self.vishnu._depgraph.setComponentSetup(state)
            # now not being setup
            componentAvatar._beingSetup = False
        except errors.HandledException, e:
            self.warning('setup failed, already handled: %s' % 
                log.getExceptionMessage(e))
            raise e
        except Exception, e:
            self.warning('setup failed: %s' % log.getExceptionMessage(e))
            m = messages.Error(T_(
                N_("Could not setup component.")),
                debug=log.getExceptionMessage(e),
                id="component-setup-%s" % componentAvatar.avatarId)
            componentAvatar._addMessage(m)
            componentAvatar._setMood(moods.sad)
            raise errors.FlumotionError('Could not set up component')
 
    setupComponent = defer_generator_method(_setupComponent)
        
    def registerComponent(self, componentAvatar):
        """
        This function registers a component in the heaven.
        It is triggered when the mind is attached.

        @param componentAvatar: the component to register
        @type  componentAvatar: L{flumotion.manager.component.ComponentAvatar}
        """
        self.debug('heaven registering component %r' % componentAvatar)
        # nothing to do

    def unregisterComponent(self, componentAvatar):
        """
        This function unregisters a component in the heaven.
        It is triggered when the mind is detached.

        @param componentAvatar: the component to unregister
        @type  componentAvatar: L{flumotion.manager.component.ComponentAvatar}
        """
        componentAvatar.debug('unregistering component')

        conf = componentAvatar.componentState.get('config')
        if conf['clock-master'] == componentAvatar.avatarId:
            # houston, we have a master clock
            self.removeMasterClock(componentAvatar)

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
            self.vishnu._depgraph.setClockMasterStarted(
                componentAvatar.componentState)
            # not in process of providing anymore
            componentAvatar._providingClock = False
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

    def getComponentAvatarForState(self, state):
        """
        Return a component avatar for the given state.

        @type state: L{flumotion.common.planet.ManagerComponentState}

        @rtype: L{ComponentAvatar}
        """
        if state in self.vishnu._componentMappers:
            return self.vishnu._componentMappers[state].avatar
        else:
            return None

