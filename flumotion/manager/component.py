# -*- Mode: Python; test-case-name: flumotion.test.test_manager_component -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# Flumotion - a streaming media server
# Copyright (C) 2004,2005,2006,2007,2008 Fluendo, S.L. (www.fluendo.com).
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

from twisted.internet import reactor, defer
from twisted.python.failure import Failure
from zope.interface import implements

from flumotion.manager import base, config
from flumotion.common import errors, interfaces, log, planet
from flumotion.common import messages, common

# registers serializable
from flumotion.common import keycards

from flumotion.common.i18n import N_, gettexter
from flumotion.common.planet import moods

__version__ = "$Rev$"
T_ = gettexter()


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

        self._shutdown_requested = False
        self._shutdownDeferred = None

        self.vishnu.registerComponent(self)
        # calllater to allow the component a chance to receive its
        # avatar, so that it has set medium.remote
        reactor.callLater(0, self.heaven.componentAttached, self)

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

    def onShutdown(self):
        # doc in base class
        self.info('component "%s" logged out', self.avatarId)

        self.vishnu.unregisterComponent(self)

        if self.clocking:
            ip, port, base_time = self.clocking
            self.vishnu.releasePortsOnWorker(self.getWorkerName(),
                                             [port])

        self.componentState.clearJobState(self._shutdown_requested)

        # FIXME: why?
        self.componentState.set('moodPending', None)

        self.componentState = None
        self.jobState = None

        self.heaven.componentDetached(self)

        if self._shutdownDeferred:
            reactor.callLater(0, self._shutdownDeferred.callback, True)
            self._shutdownDeferred = None

        base.ManagerAvatar.onShutdown(self)

    # my methods

    def addMessage(self, level, mid, format, *args, **kwargs):
        """
        Convenience message to construct a message and add it to the
        component state. `format' should be marked as translatable in
        the source with N_, and *args will be stored as format
        arguments. Keyword arguments are passed on to the message
        constructor. See L{flumotion.common.messages.Message} for the
        meanings of the rest of the arguments.

        For example::

          self.addMessage(messages.WARNING, 'foo-warning',
                          N_('The answer is %d'), 42, debug='not really')
        """
        self.addMessageObject(messages.Message(level,
                                               T_(format, *args),
                                               mid=mid, **kwargs))

    def addMessageObject(self, message):
        """
        Add a message to the planet state.

        @type message: L{flumotion.common.messages.Message}
        """
        self.componentState.append('messages', message)

    def upgradeConfig(self, state, conf):
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

            self.upgradeConfig(state, conf)
            if state.get('config') != conf:
                diff = config.dictDiff(state.get('config'), conf)
                diffMsg = config.dictDiffMessageString(diff,
                                                   'internal conf',
                                                   'running conf')
                self.addMessage(messages.WARNING, 'stale-config',
                                N_("Component logged in with stale "
                                   "configuration. To fix this, stop "
                                   "this component and then restart "
                                   "the manager."),
                                debug=("Updating internal conf from "
                                       "running conf:\n" + diffMsg))
                self.warning('updating internal component state for %r',
                             state)
                self.debug('changes to conf: %s',
                           config.dictDiffMessageString(diff))
                state.set('config', conf)

        def makeNewComponentState(conf):
            # condition (2)
            state = planet.ManagerComponentState()
            state.setJobState(self.jobState)
            self.componentState = state

            self.upgradeConfig(state, conf)

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
        else:
            makeNewComponentState(conf)

    def provideMasterClock(self):
        """
        Tell the component to provide a master clock.

        @rtype: L{twisted.internet.defer.Deferred}
        """

        def success(clocking):
            self.clocking = clocking
            self.heaven.masterClockAvailable(self)

        def error(failure):
            self.addMessage(messages.WARNING, 'provide-master-clock',
                            N_('Failed to provide the master clock'),
                            debug=log.getFailureMessage(failure))
            self.vishnu.releasePortsOnWorker(self.getWorkerName(), [port])

        if self.clocking:
            self.heaven.masterClockAvailable(self)
        else:
            (port, ) = self.vishnu.reservePortsOnWorker(
                self.getWorkerName(), 1)
            self.debug('provideMasterClock on port %d', port)

            d = self.mindCallRemote('provideMasterClock', port)
            d.addCallbacks(success, error)

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

    def getFeedId(self, feedName):
        """
        Get the feedId of a feed provided or consumed by this component.

        @param feedName: The name of the feed (i.e., eater alias or
                         feeder name)
        @rtype: L{flumotion.common.common.feedId}
        """
        return common.feedId(self.getName(), feedName)

    def getFullFeedId(self, feedName):
        """
        Get the full feedId of a feed provided or consumed by this
        component.

        @param feedName: The name of the feed (i.e., eater alias or
                         feeder name)
        @rtype: L{flumotion.common.common.fullFeedId}
        """
        return common.fullFeedId(self.getParentName(),
                                 self.getName(), feedName)

    def getVirtualFeeds(self):
        """
        Get the set of virtual feeds provided by this component.

        @rtype: dict of fullFeedId -> (ComponentAvatar, feederName)
        """
        conf = self.componentState.get('config')
        ret = {}
        for feedId, feederName in conf.get('virtual-feeds', {}).items():
            vComp, vFeed = common.parseFeedId(feedId)
            ffid = common.fullFeedId(self.getParentName(), vComp, vFeed)
            ret[ffid] = (self, feederName)
        return ret

    def getWorker(self):
        """
        Get the worker that this component should run on.

        @rtype: str
        """
        return self.componentState.get('workerRequested')

    def getClockMaster(self):
        """
        Get this component's clock master, if any.

        @rtype: avatarId or None
        """
        return self.componentState.get('config')['clock-master']

    def stop(self):
        """
        Tell the remote component to shut down.
        """
        self._shutdownDeferred = defer.Deferred()

        self.mindCallRemote('stop')

        return self._shutdownDeferred

    def setClocking(self, host, port, base_time):
        # setMood on error?
        return self.mindCallRemote('setMasterClock', host, port, base_time)

    def eatFrom(self, eaterAlias, fullFeedId, host, port):
        self.debug('connecting eater %s to feed %s', eaterAlias, fullFeedId)
        return self.mindCallRemote('eatFrom', eaterAlias, fullFeedId,
                                   host, port)

    def feedTo(self, feederName, fullFeedId, host, port):
        self.debug('connecting feeder %s to feed %s', feederName, fullFeedId)
        return self.mindCallRemote('feedTo', feederName, fullFeedId,
                                   host, port)

    def modifyProperty(self, property_name, value):
        """
        Tell the remote component to modify a property with a new value.

        @param property_name: The name of the property to change
        @param value: The new value of the property
        @rtype: L{twisted.internet.defer.Deferred}
        """
        return self.mindCallRemote('modifyProperty', property_name, value)

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
        return self.mindCallRemote('removeKeycardId', keycardId)

    def expireKeycard(self, keycardId):
        """
        Expire a keycard issued to this component because the bouncer decided
        to.

        @type  keycardId: str
        """
        return self.mindCallRemote('expireKeycard', keycardId)

    def expireKeycards(self, keycardIds):
        """
        Expire keycards issued to this component because the bouncer
        decided to.

        @type  keycardIds: sequence of str
        """
        return self.mindCallRemote('expireKeycards', keycardIds)

    def keepAlive(self, issuerName, ttl):
        """
        Resets the expiry timeout for keycards issued by issuerName.

        @param issuerName: the issuer for which keycards should be kept
                           alive; that is to say, keycards with the
                           attribute 'issuerName' set to this value will
                           have their ttl values reset.
        @type  issuerName: str
        @param ttl: the new expiry timeout
        @type  ttl: number
        """
        return self.mindCallRemote('keepAlive', issuerName, ttl)

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
        Remove a keycard on the given bouncer on behalf of a
        component's medium.

        This is requested by a component that created the keycard.

        @type  bouncerName: str
        @param keycardId:   id of keycard to remove
        @type  keycardId:   str
        """
        avatarId = common.componentId('atmosphere', bouncerName)
        if not self.heaven.hasAvatar(avatarId):
            self.warning('No bouncer with id %s registered', avatarId)
            raise errors.UnknownComponentError(avatarId)

        return self.heaven.getAvatar(avatarId).removeKeycardId(keycardId)

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
            self.warning('asked to expire keycard %s for requester %s, '
                         'but no such component registered',
                         keycardId, requesterId)
            raise errors.UnknownComponentError(requesterId)

        return self.heaven.getAvatar(requesterId).expireKeycard(keycardId)

    def perspective_expireKeycards(self, requesterId, keycardIds):
        """
        Expire multiple keycards (and thus the requester's connections)
        issued to the given requester.

        This is called by the bouncer component that authenticated
        the keycards.

        @param requesterId: name (avatarId) of the component that originally
                            requested authentication for the given keycardId
        @type  requesterId: str
        @param keycardIds:  sequence of id of keycards to expire
        @type  keycardIds:  sequence of str
        """
        if not self.heaven.hasAvatar(requesterId):
            self.warning('asked to expire %d keycards for requester %s, '
                         'but no such component registered',
                         len(keycardIds), requesterId)
            raise errors.UnknownComponentError(requesterId)

        return self.heaven.getAvatar(requesterId).expireKeycards(keycardIds)


class dictlist(dict):

    def add(self, key, value):
        if key not in self:
            self[key] = []
        self[key].append(value)

    def remove(self, key, value):
        self[key].remove(value)
        if not self[key]:
            del self[key]


class FeedMap(object, log.Loggable):
    logName = 'feed-map'

    def __init__(self):
        #FIXME: Use twisted.python.util.OrderedDict instead
        self.avatars = {}
        self._ordered_avatars = []
        self._dirty = True
        self._recalc()

    def componentAttached(self, avatar):
        assert avatar.avatarId not in self.avatars
        self.avatars[avatar.avatarId] = avatar
        self._ordered_avatars.append(avatar)
        self._dirty = True

    def componentDetached(self, avatar):
        # returns the a list of other components that will need to be
        # reconnected
        del self.avatars[avatar.avatarId]
        self._ordered_avatars.remove(avatar)
        self._dirty = True
        # NB, feedDeps is dirty. Scrub it of avatars that have logged
        # out
        return [(a, f) for a, f in self.feedDeps.pop(avatar, [])
                if a.avatarId in self.avatars]

    def _getFeederAvatar(self, eater, feedId):
        # FIXME: 'get' part is confusing - this methods _modifies_ structures!
        flowName = eater.getParentName()
        compName, feedName = common.parseFeedId(feedId)
        ffid = common.fullFeedId(flowName, compName, feedName)
        feeder = None
        if ffid in self.feeds:
            feeder, feedName = self.feeds[ffid][0]
            self.feedDeps.add(feeder, (eater, ffid))
            if feeder.getFeedId(feedName) != feedId:
                self.debug('chose %s for feed %s',
                           feeder.getFeedId(feedName), feedId)
        return feeder, feedName

    def _recalc(self):
        if not self._dirty:
            return
        self.feedersForEaters = ffe = {}
        self.eatersForFeeders = eff = dictlist()
        self.feeds = dictlist()
        self.feedDeps = dictlist()

        for comp in self._ordered_avatars:
            for feederName in comp.getFeeders():
                self.feeds.add(comp.getFullFeedId(feederName),
                               (comp, feederName))
            for ffid, pair in comp.getVirtualFeeds().items():
                self.feeds.add(ffid, pair)

        for eater in self.avatars.values():
            for pairs in eater.getEaters().values():
                for feedId, eName in pairs:
                    feeder, fName = self._getFeederAvatar(eater, feedId)
                    if feeder:
                        ffe[eater.getFullFeedId(eName)] = (
                            eName, feeder, fName)
                        eff.add(feeder.getFullFeedId(fName),
                                (fName, eater, eName))
                    else:
                        self.debug('eater %s waiting for feed %s to log in',
                                   eater.getFeedId(eName), feedId)
        self._dirty = False

    def getFeedersForEaters(self, avatar):
        """Get the set of feeds that this component is eating from,
        keyed by eater alias.

        @return: a list of (eaterAlias, feederAvatar, feedName) tuples
        @rtype:  list of (str, ComponentAvatar, str)
        """
        self._recalc()
        ret = []
        for tups in avatar.getEaters().values():
            for feedId, alias in tups:
                ffid = avatar.getFullFeedId(alias)
                if ffid in self.feedersForEaters:
                    ret.append(self.feedersForEaters[ffid])
        return ret

    def getFeedersForEater(self, avatar, ffid):
        """Get the set of feeds that this component is eating from
        for the given feedId.

        @param avatar: the eater component
        @type  avatar: L{ComponentAvatar}
        @param ffid:   full feed id for which to return feeders
        @type  ffid:   str
        @return: a list of (eaterAlias, feederAvatar, feedName) tuples
        @rtype:  list of (str, L{ComponentAvatar}, str)
        """
        self._recalc()
        ret = []
        for feeder, feedName in self.feeds.get(ffid, []):
            rffid = feeder.getFullFeedId(feedName)
            eff = self.eatersForFeeders.get(rffid, [])
            for fName, eater, eaterName in eff:
                if eater == avatar:
                    ret.append((eaterName, feeder, feedName))
        return ret

    def getEatersForFeeders(self, avatar):
        """Get the set of eaters that this component feeds, keyed by
        feeder name.

        @return: a list of (feederName, eaterAvatar, eaterAlias) tuples
        @rtype:  list of (str, ComponentAvatar, str)
        """
        self._recalc()
        ret = []
        for feedName in avatar.getFeeders():
            ffid = avatar.getFullFeedId(feedName)
            if ffid in self.eatersForFeeders:
                ret.extend(self.eatersForFeeders[ffid])
        return ret


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
        self.feedMap = FeedMap()

    ### our methods

    def feedServerAvailable(self, workerName):
        self.debug('feed server %s logged in, we can connect to its port',
                   workerName)
        # can be made more efficient
        for avatar in self.avatars.values():
            if avatar.getWorkerName() == workerName:
                self._setupClocking(avatar)
                self._connectEatersAndFeeders(avatar)

    def masterClockAvailable(self, component):
        self.debug('master clock for %r provided on %r', component.avatarId,
                   component.clocking)
        component_flow = component.getParentName()
        # can be made more efficient
        for avatar in self.avatars.values():
            if avatar.avatarId != component.avatarId:
                flow = avatar.getParentName()
                if flow == component_flow:
                    self._setupClocking(avatar)

    def _setupClocking(self, avatar):
        master = avatar.getClockMaster()
        if master:
            if master == avatar.avatarId:
                self.debug('Need for %r to provide a clock master',
                           master)
                avatar.provideMasterClock()
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
                        avatar.setClocking(host, port, base_time)
                    else:
                        self.warning('%r should provide a clock master '
                                     'but is not doing so', master)
                        # should we componentAvatar.provideMasterClock() ?
                else:
                    self.debug('clock master not logged in yet, will '
                               'set clocking later')

    def componentAttached(self, avatar):
        # No need to wait for any of this, they are not interdependent
        assert avatar.avatarId in self.avatars
        self.feedMap.componentAttached(avatar)
        self._setupClocking(avatar)
        self._connectEatersAndFeeders(avatar)

    def componentDetached(self, avatar):
        assert avatar.avatarId not in self.avatars
        compsNeedingReconnect = self.feedMap.componentDetached(avatar)
        if self.vishnu.running:
            self.debug('will reconnect: %r', compsNeedingReconnect)
            # FIXME: this will need revision when we have the 'feedTo'
            # direction working
            for comp, ffid in compsNeedingReconnect:
                self._connectEaters(comp, ffid)

    def mapNetFeed(self, fromAvatar, toAvatar):
        """
        @param fromAvatar: the avatar to connect from
        @type  fromAvatar: L{ComponentAvatar}
        @param fromAvatar: the avatar to connect to
        @type  toAvatar:   L{ComponentAvatar}

        @returns: the host and port on which to make the connection to
                  toAvatar from fromAvatar
        @rtype:   tuple of (str, int or None)
        """
        toHost = toAvatar.getClientAddress()
        toPort = toAvatar.getFeedServerPort() # can be None

        # FIXME: until network map is implemented, hack to assume that
        # connections from what appears to us to be the same IP go
        # through localhost instead. Allows connections between
        # components on a worker behind a firewall, but not between
        # components running on different workers, both behind a
        # firewall
        fromHost = fromAvatar.mind.broker.transport.getPeer().host
        if fromHost == toHost:
            toHost = '127.0.0.1'

        self.debug('mapNetFeed from %r to %r: %s:%r', fromAvatar, toAvatar,
            toHost, toPort)
        return toHost, toPort

    def _connectFeederToEater(self, fromComp, fromFeed,
                              toComp, toFeed, method):
        host, port = self.mapNetFeed(fromComp, toComp)
        if port:
            fullFeedId = toComp.getFullFeedId(toFeed)
            proc = getattr(fromComp, method)
            proc(fromFeed, fullFeedId, host, port)
        else:
            self.debug('postponing connection to %s: feed server '
                       'unavailable', toComp.getFeedId(toFeed))

    def _connectEatersAndFeeders(self, avatar):
        # FIXME: all connections are upstream for now

        def always(otherComp):
            return True

        def never(otherComp):
            return False
        directions = [(self.feedMap.getFeedersForEaters,
                       always, 'eatFrom', 'feedTo'),
                      (self.feedMap.getEatersForFeeders,
                       never, 'feedTo', 'eatFrom')]

        myComp = avatar
        for getPeers, initiate, directMethod, reversedMethod in directions:
            for myFeedName, otherComp, otherFeedName in getPeers(myComp):
                if initiate(otherComp):
                    # we initiate the connection
                    self._connectFeederToEater(myComp, myFeedName, otherComp,
                                               otherFeedName, directMethod)
                else:
                    # make the other component initiate connection
                    self._connectFeederToEater(otherComp, otherFeedName,
                                               myComp, myFeedName,
                                               reversedMethod)

    def _connectEaters(self, avatar, ffid):
        # FIXME: all connections are upstream for now
        ffe = self.feedMap.getFeedersForEater(avatar, ffid)
        for myFeedName, otherComp, otherFeedName in ffe:
            self._connectFeederToEater(avatar, myFeedName, otherComp,
                                       otherFeedName, 'eatFrom')
