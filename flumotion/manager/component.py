# -*- Mode: Python; test-case-name: flumotion.test.test_manager_manager -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# Flumotion - a streaming media server
# Copyright (C) 2004,2005,2006,2007 Fluendo, S.L. (www.fluendo.com).
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
from twisted.internet import reactor, defer
from twisted.internet import error as terror
from twisted.python.failure import Failure
from zope.interface import implements

from flumotion.configure import configure
# rename to base
from flumotion.manager import base
from flumotion.common import errors, interfaces, keycards, log, config, planet
from flumotion.common import messages, common
from flumotion.twisted import flavors
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

    def __init__(self, heaven, avatarId, remoteIdentity, mind, conf,
                 jobState, clocking):
        # doc in base class
        base.ManagerAvatar.__init__(self, heaven, avatarId,
                                    remoteIdentity, mind)

        self.jobState = jobState
        self.makeComponentState(conf)
        self.clocking = clocking

        self._ports = {}

        self._shutdown_requested = False

        self._happydefers = [] # deferreds to call when mood changes to happy

        self.vishnu.registerComponent(self)
        self.addMoodListener()
        # calllater to allow the component a chance to receive its
        # avatar, so that it has set medium.remote
        reactor.callLater(0, self.heaven.componentAttached, avatarId)

    def makeComponentState(self, conf):
        # the component just logged in with good credentials. we fetched
        # its config and job state. now there are two possibilities:
        #  (1) we were waiting for such a component to start. There was
        #      a ManagerComponentState and an avatarId in the
        #      componentMappers waiting for us.
        #  (2) we don't know anything about this component, but it has a
        #      state and config. We deal with it, creating all the
        #      neccesary internal state.
        def verifyExistingComponentState(conf, state):
            # condition (1)
            state.setJobState(self.jobState)
            self.componentState = state

            self._upgradeConfig(state, conf)
            if state.get('config') != conf:
                diff = config.dictDiff(state.get('config'), conf)
                diffMsg = config.dictDiffMessageString(diff,
                                                   'internal conf',
                                                   'running conf')
                self.addMessage(messages.WARNING, 'stale-config',
                                N_("Component logged in with stale "
                                   "configuration. Consider stopping "
                                   "this component and restarting "
                                   "the manager."),
                                debug=("Updating internal conf from "
                                       "running conf:\n" + diffMsg))
                self.warning('updating internal component state for %r')
                self.debug('changes to conf: %s',
                           config.dictDiffMessageString(diff))
                state.set('config', conf)

        def makeNewComponentState(conf):
            # condition (2)
            state = planet.ManagerComponentState()
            state.setJobState(self.jobState)
            self.componentState = state

            self._upgradeConfig(state, conf)

            flowName, compName = conf['parent'], conf['name']

            state.set('name', compName)
            state.set('type', conf['type'])
            state.set('workerRequested', self.jobState.get('workerName'))
            state.set('config', conf)
            self.vishnu.addComponentToFlow(state, flowName)
            return state

        mState = self.vishnu.getManagerComponentState(self.avatarId)
        if mState:
            verifyExistingComponentState(conf, mState)
            return mState
        else:
            return makeNewComponentState(conf)

    def makeAvatarInitArgs(klass, heaven, avatarId, remoteIdentity,
                           mind):
        def gotStates(result):
            (_s1, conf), (_s2, jobState), (_s3, clocking) = result
            assert _s1 and _s2 and _s3 # fireOnErrback=1
            log.debug('component-avatar', 'got state information')
            return (heaven, avatarId, remoteIdentity, mind,
                    conf, jobState, clocking)
        log.debug('component-avatar', 'calling mind for state information')
        d = defer.DeferredList([mind.callRemote('getConfig'),
                                mind.callRemote('getState'),
                                mind.callRemote('getMasterClockInfo')],
                               fireOnOneErrback=True)
        d.addCallback(gotStates)
        return d
    makeAvatarInitArgs = classmethod(makeAvatarInitArgs)

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
    def _setMood(self, mood):
        if not self.componentState:
            return

        if not self.componentState.get('mood') == mood.value:
            self.debug('Setting mood to %r' % mood)
            self.componentState.setMood(mood.value)

    def _setMoodValue(self, moodValue):
        mood = moods.get(moodValue)
        self._setMood(mood)

    def _getMoodValue(self):
        if not self.componentState:
            return
        return self.componentState.get('mood')

    def addMessage(self, level, id, format, *args, **kwargs):
        """
        Convenience message to construct a message and add it to the
        component state. `format' should be marked as translatable in
        the source with N_, and *args will be stored as format
        arguments. Keyword arguments are passed on to the message
        constructor. See L{flumotion.common.messages.Message} for the
        meanings of the rest of the arguments.

        For example:

          self.addMessage(messages.WARNING, 'foo-warning',
                          N_('The answer is %d'), 42, debug='not really')
        """
        self.addMessageObject(messages.Message(level,
                                               T_(format, *args),
                                               id=id, **kwargs))

    def addMessageObject(self, message):
        """
        Add a message to the planet state.

        @type message: L{flumotion.common.messages.Message}
        """
        self.componentState.append('messages', message)

    def _upgradeConfig(self, state, conf):
        # different from conf['version'], eh...
        version = conf.get('config-version', 0)
        while version < config.CURRENT_VERSION:
            try:
                config.UPGRADERS[version](conf)
                version += 1
                conf['config-version'] = version
            except Exception, e:
                self.addMessage(messages.WARNING,
                                'upgrade-%d' % version,
                                N_("Failed to upgrade config %r "
                                   "from version %d. Please file "
                                   "a bug."), conf, version,
                                debug=log.getExceptionMessage(e))
                return

    def onShutdown(self):
        # doc in base class
        self.vishnu.unregisterComponent(self)

        self.info('component "%s" logged out', self.avatarId)

        if self.clocking:
            ip, port, base_time = self.clocking
            self.vishnu.releasePortsOnWorker(self.getWorkerName(),
                                             [port])
        if self._ports:
            self.vishnu.releasePortsOnWorker(self.getWorkerName(),
                                             self._ports.values())

        self.componentState.clearJobState()

        # If we were sad, leave the mood as it is. Otherwise if shut
        # down due to an explicit manager request, go to sleeping.
        # Otherwise, go to lost, because it got disconnected for an
        # unknown reason (probably network related)
        if self._getMoodValue() != moods.sad.value:
            if self._shutdown_requested:
                self.debug("Shutdown was requested, component now sleeping")
                self._setMood(moods.sleeping)
            else:
                self.debug("Shutdown was NOT requested, component now lost")
                self._setMood(moods.lost)

        # FIXME: why?
        self.componentState.set('moodPending', None)

        # Now we're detached (no longer proxying state from the component)
        # clear all remaining messages
        for m in self.componentState.get('messages'):
            self.debug('Removing message %r', m)
            self.componentState.remove('messages', m)

        # detach componentstate from avatar
        self.componentState = None
        self.jobState = None

        self._ports = {}

        self.jobState = None

        base.ManagerAvatar.onShutdown(self)

    def addMoodListener(self):
        # Handle initial state appropriately.
        if self.jobState.get('mood') == moods.happy.value:
            for d in self._happydefers:
                d.callback(True)
            self._happydefers = []
        self.jobState.addListener(self, set=self.stateSet)

    # IStateListener methods
    def stateSet(self, state, key, value):
        self.log("state set on %r: %s now %r" % (state, key, value))
        if key == 'mood':
            self.info('Mood changed to %s' % moods.get(value).name)

            if value == moods.happy.value:
                # callback any deferreds waiting on this -- what is this
                # for?
                while self._happydefers:
                    self._happydefers.pop(0).callback(True)

    # my methods
    def provideMasterClock(self):
        """
        Tell the component to provide a master clock.

        @rtype: L{twisted.internet.defer.Deferred}
        """
        def success(clocking):
            self.clocking = clocking
            self.heaven.masterClockAvailable(self.avatarId, clocking)

        def error(failure):
            self.addMessage(messages.WARNING, 'provide-master-clock',
                            N_('Failed to provide the master clock'),
                            debug=log.getFailureMessage(failure))
            self.vishnu.releasePortsOnWorker(self.getWorkerName(), [port])

        if self.clocking:
            return defer.succeed(self.clocking)

        (port,) = self.vishnu.reservePortsOnWorker(self.getWorkerName(), 1)
        self.debug('provideMasterClock on port %d', port)

        d = self.mindCallRemote('provideMasterClock', port)
        d.addCallbacks(success, error)
        return d

    def getFeedersForEaters(self):
        """Get the set of feeds that this component is eating from,
        keyed by eater alias.

        @return: a list of (eaterAlias, feedId) tuples
        @rtype:  list of (str, str)
        """
        if not self.componentState:
            self.warning("detached component")
            return []
        concat = lambda lists: reduce(list.__add__, lists, [])
        eaterDict = self.getEaters()
        return concat([[(alias, feedId) for feedId, alias in tups]
                       for tups in eaterDict.values()])

    def getEatersForFeeders(self, otherComponents):
        """Get the set of eaters that this component feeds, keyed by
        feeder name.

        Note that you need to pass a list of other components to this
        function; it has to search them all.

        @param otherComponents: Other components that might eat from
        this component.
        @type  otherComponents: list of ComponentAvatar
        @return: a list of (feederName, feedId) tuples
        @rtype:  list of (str, str)
        """
        if not self.componentState:
            self.warning("detached component")
            return []

        feederNames = self.getFeeders()
        theseFeedIds = [common.feedId(self.getName(), feederName)
                        for feederName in feederNames]

        ret = []
        for comp in otherComponents:
            for eaterAlias, feedId in comp.getFeedersForEaters():
                if feedId in theseFeedIds:
                    remoteFeedId = common.feedId(comp.getName(), eaterAlias)
                    ret.append((feederNames[theseFeedIds.index(feedId)],
                                remoteFeedId))
        return ret

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
        return self.jobState.get('manager-ip')

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

    def getEaters(self):
        """
        Get the set of eaters that this component eats from.

        @rtype: dict of eaterName -> [(feedId, eaterAlias)]
        """
        return self.componentState.get('config').get('eater', {})

    def getFeeders(self):
        """
        Get the list of feeders that this component provides.

        @rtype: list of feederName
        """
        return self.componentState.get('config').get('feed', [])

    def getVirtualFeeds(self):
        """
        Get the set of virtual feeds provided by this component.

        @rtype: dict of feedId -> feederName
        """
        return self.componentState.get('config').get('virtual-feeds', {})

    def stop(self):
        """
        Tell the avatar to stop the component.
        """
        d = self.mindCallRemote('stop')
        # FIXME: real error handling
        d.addErrback(lambda x: None)
        return d

    def setClocking(self, host, port, base_time):
        # setMood on error?
        return self.mindCallRemote('setMasterClock', host, port, base_time)

    def eatFrom(self, eaterAlias, fullFeedId, host, port):
        d = self.mindCallRemote('eatFrom', eaterAlias, fullFeedId, host,
                                port)
        return d

    def feedTo(self, feederName, fullFeedId, host, port):
        d = self.mindCallRemote('feedTo', feederName, fullFeedId, host,
                                port)
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

        return self.mindCallRemote('setElementProperty', element, property, value)

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
        return self.mindCallRemote('getElementProperty', element, property)

    def reloadComponent(self):
        """
        Tell the component to reload itself.

        @rtype: L{twisted.internet.defer.Deferred}
        """
        return self.mindCallRemote('reloadComponent')

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
        return self.mindCallRemote('authenticate', keycard)

    def removeKeycardId(self, keycardId):
        """
        Remove a keycard managed by this bouncer because the requester
        has gone.

        @type  keycardId: str
        """
        self.debug('remotecalling removeKeycardId with id %s' % keycardId)
        return self.mindCallRemote('removeKeycardId', keycardId)

    def expireKeycard(self, keycardId):
        """
        Expire a keycard issued to this component because the bouncer decided
        to.

        @type  keycardId: str
        """
        self.debug('remotecalling expireKeycard with id %s' % keycardId)
        return self.mindCallRemote('expireKeycard', keycardId)

    ### IPerspective methods, called by the worker's component
    def perspective_cleanShutdown(self):
        """
        Called by a component to tell the manager that it's shutting down
        cleanly (and thus should go to sleeping, rather than lost or sad)
        """
        self.debug("shutdown is clean, shouldn't go to lost")
        self._shutdown_requested = True

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

    ### our methods
    def _componentIsLocal(self, componentAvatar):
        # gets what we think is the other side's address
        host = componentAvatar.getClientAddress()

        if host == '127.0.0.1':
            return True
        else:
            return False

    def feedServerAvailable(self, workerName):
        self.debug('feed server %s logged in, we can connect to its port',
                   workerName)
        # can be made more efficient
        for avatar in self.avatars.values():
            if avatar.componentState:
                if avatar.componentState.get('workerRequested') == workerName:
                    self.componentAttached(avatar.avatarId)

    def masterClockAvailable(self, avatarId, clocking):
        self.debug('master clock for %r provided on %r', avatarId,
                   clocking)
        # can be made more efficient
        for avatar in self.avatars.values():
            if avatar.componentState:
                self._setupClocking(avatar)

    def _setupClocking(self, componentAvatar):
        conf = componentAvatar.componentState.get('config')
        master = conf['clock-master'] # avatarId of the clock master
        if master:
            if master == componentAvatar.avatarId:
                self.debug('Need for %r to provide a clock master',
                           master)
                componentAvatar.provideMasterClock()
            else:
                self.debug('Need to synchronize with clock master %r',
                           master)
                # if master in self.avatars would be natural, but it seems
                # that for now due to the getClocking() calls etc we need to
                # check against the componentMapper set. could (and probably
                # should) be fixed in the future.
                m = self.vishnu.getComponentMapper(master)
                if m and m.avatar:
                    clocking = m.avatar.clocking
                    if clocking:
                        host, port, base_time = clocking
                        componentAvatar.setClocking(host, port, base_time)
                    else:
                        self.warning('%r should provide a clock master '
                                     'but is not doing so', master)
                        # should we componentAvatar.provideMasterClock() ?
                else:
                    self.debug('clock master not logged in yet, will '
                               'set clocking later')

    def componentAttached(self, avatarId):
        # No need to wait for any of this, they are not interdependent
        if avatarId in self.avatars:
            avatar = self.avatars[avatarId]
            self._setupClocking(avatar)
            self._connectEaters(avatar)
            self._connectFeeders(avatar)
        else:
            self.debug('avatar %s seems to have logged out rather quickly',
                       avatarId)

    def _connectEaterUpstream(self, componentAvatar, eaterAlias,
                              remoteFeedId):
        self.debug('connecting from eater to feeder')
        # the flow is the same for both components
        flowName = componentAvatar.getParentName()

        # these are remote names
        componentName, feedName = common.parseFeedId(remoteFeedId)
        fullFeedId = common.fullFeedId(flowName, componentName,
                                       feedName)
        componentId = common.componentId(flowName, componentName)

        if not self.hasAvatar(componentId):
            self.debug('feed %s unavailable, assuming it will log '
                       'in later', remoteFeedId)
            return
        feederAvatar = self.getAvatar(componentId)

        # FIXME: get from network map instead
        host = feederAvatar.getClientAddress()
        port = feederAvatar.getFeedServerPort()
        if not port:
            self.debug('feed server not available, will connect feed'
                       ' later')
            return

        # FIXME: until network map is implemented, hack to
        # assume that connections from what appears to us to be
        # the same IP go through localhost instead. Allows
        # connections between components on a worker behind a
        # firewall, but not between components running on
        # different workers, both behind a firewall
        eaterHost = componentAvatar.mind.broker.transport.getPeer().host
        if eaterHost == host:
            host = '127.0.0.1'

        return componentAvatar.eatFrom(eaterAlias, fullFeedId, host, port)

    def _connectEaters(self, componentAvatar):
        # connect the component's eaters
        for eaterAlias, remoteFeedId in componentAvatar.getFeedersForEaters():
            self.debug('connecting eater %s to feed %s', eaterAlias,
                       remoteFeedId)
            # FIXME: all connections are upstream for now
            connection = "upstream"
            if connection == "upstream":
                self._connectEaterUpstream(componentAvatar,
                                           eaterAlias, remoteFeedId)
            else:
                feedCompName, feederName = common.parseFeedId(remoteFeedId)
                flowName = componentAvatar.getParentName()
                feedCompId = common.componentId(flowName, feedCompName)
                feedCompAvatar = self.avatars.get(feedCompId, None)
                feedId = common.feedId(componentAvatar.getName(),
                                       eaterAlias)
                if feedCompAvatar and feedCompAvatar.componentState:
                    self._connectFeederDownstream(feedCompAvatar,
                                                  feederName, feedId)
                else:
                    self.debug('component providing feed %s will '
                               'connect later', remoteFeedId)

    def _connectFeeders(self, componentAvatar):
        flowName = componentAvatar.getParentName()
        otherComponents = [c for c in self.avatars.values()
                           if c.componentState != None and
                               c.getParentName() == flowName]
        for feederName, remoteFeedId \
                in componentAvatar.getEatersForFeeders(otherComponents):
            self.debug('connecting feeder %s to feed %s', feederName,
                       remoteFeedId)
            # FIXME: all connections are upstream for now
            connection = "upstream"
            if connection == "upstream":
                eaterCompName, eaterAlias = common.parseFeedId(remoteFeedId)
                eaterCompId = common.componentId(flowName, eaterCompName)
                eaterCompAvatar = self.avatars.get(eaterCompId, None)
                feedId = common.feedId(componentAvatar.getName(),
                                       feederName)
                if eaterCompAvatar and eaterCompAvatar.componentState:
                    self._connectEaterUpstream(eaterCompAvatar,
                                               eaterAlias, feedId)
                else:
                    self.debug('component with eater %s will '
                               'connect later', remoteFeedId)
            else:
                self._connectFeederDownstream(componentAvatar,
                                              feederName,
                                              remoteFeedId)

    def _connectFeederDownstream(self, componentAvatar, feederName,
                                 remoteFeedId):
        def error(format, *args, **kwargs):
            componentAvatar.addMessage(messages.ERROR,
                                       ("component-start-%s-%s"
                                        % (feederName, remoteFeedId)),
                                       format, *args, **kwargs)
            # FIXME: make setMood public
            componentAvatar._setMood(moods.sad)
            return defer.fail(errors.ComponentStartHandledError())

        self.debug('connecting from feeder to eater')
        # the flow is the same for both components
        flowName = componentAvatar.getParentName()

        # these are remote names
        componentName, eaterAlias = common.parseFeedId(remoteFeedId)
        fullFeedId = common.fullFeedId(flowName, componentName,
                                       eaterAlias)
        componentId = common.componentId(flowName, componentName)

        eaterAvatar = self.getAvatar(componentId)
        if not eaterAvatar:
            return error(N_("Configuration problem."),
                         debug="No component '%s'." % componentId)

        # FIXME: get from network map instead
        host = eaterAvatar.getClientAddress()
        port = eaterAvatar.getFeedServerPort()
        if not port:
            self.debug('feed server not available, will connect feed'
                       ' later')
            return

        def errback(failure):
            failure.trap(terror.ConnectError,
                         terror.ConnectionRefusedError)
            return error(N_("Could not connect component to %s:%d for "
                            "feed %s."), host, port, fullFeedId,
                         debug="No component '%s'." % componentId)

        d = componentAvatar.feedTo(feederName, fullFeedId,
                                   host, port)
        d.addErrback(errback)
        return d

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
