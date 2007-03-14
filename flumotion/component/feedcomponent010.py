# -*- Mode: Python; test-case-name: flumotion.test.test_feedcomponent010 -*-
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

import gst
import gobject

import os
import time

from twisted.internet import reactor, defer

from flumotion.component import component as basecomponent
from flumotion.common import common, errors, pygobject, messages
from flumotion.common import gstreamer, componentui
from flumotion.worker import feed

from flumotion.common.planet import moods
from flumotion.common.pygobject import gsignal

from flumotion.common.messages import N_
T_ = messages.gettexter('flumotion')

class Feeder:
    """
    This class groups feeder-related information as used by a Feed Component.

    @ivar feedId:  id of the feed this is a feeder for
    @ivar uiState: the serializable UI State for this feeder
    """
    def __init__(self, feedId):
        self.feedId = feedId
        self.uiState = componentui.WorkerComponentUIState()
        self.uiState.addKey('feedId')
        self.uiState.set('feedId', feedId)
        self.uiState.addListKey('clients')
        self._fdToClient = {} # fd -> (FeederClient, cleanupfunc)
        self._clients = {} # id -> FeederClient

    def clientConnected(self, clientId, fd, cleanup):
        """
        The given client has connected on the given file descriptor, and is
        being added to multifdsink. This is called solely from the reactor 
        thread.

        @param clientId: id of the client of the feeder
        @param fd:       file descriptor representing the client
        @param cleanup:  callable to be called when the given fd is removed
        """
        if clientId not in self._clients:
            # first time we see this client, create an object
            client = FeederClient(clientId)
            self._clients[clientId] = client
            self.uiState.append('clients', client.uiState)

        client = self._clients[clientId]
        self._fdToClient[fd] = (client, cleanup)

        client.connected(fd)

        return client

    def clientDisconnected(self, fd):
        """
        The client has been entirely removed from multifdsink, and we may
        now close its file descriptor.
        The client object stays around so we can track over multiple
        connections.

        Called from GStreamer threads.

        @type fd: file descriptor
        """
        (client, cleanup) = self._fdToClient.pop(fd)
        client.disconnected()

        # To avoid races between this thread (a GStreamer thread) closing the
        # FD, and the reactor thread reusing this FD, we only actually perform
        # the close in the reactor thread.
        reactor.callFromThread(cleanup, fd)

    def getClients(self):
        """
        @rtype: list of all L{FeederClient}s ever seen, including currently 
                disconnected clients
        """
        return self._clients.values()

class FeederClient:
    """
    This class groups information related to the client of a feeder.
    The client is identified by an id.
    The information remains valid for the lifetime of the feeder, so it
    can track reconnects of the client.

    @ivar clientId: id of the client of the feeder
    @ivar fd:       file descriptor the client is currently using, or None.
    """
    def __init__(self, clientId):
        self.uiState = componentui.WorkerComponentUIState()
        self.uiState.addKey('clientId', clientId)
        self.fd = None
        self.uiState.addKey('fd', None)

        # these values can be set to None, which would mean
        # Unknown, not supported
        # these are supported
        for key in (
            'bytesReadCurrent',      # bytes read over current connection
            'bytesReadTotal',        # bytes read over all connections
            'reconnects',            # number of connections made by this client
            'lastConnect',           # last client connection, in epoch seconds
            'lastDisconnect',        # last client disconnect, in epoch seconds
            'lastActivity',          # last time client read or connected
            ):
            self.uiState.addKey(key, 0)
        # these are possibly unsupported
        for key in (
            'buffersDroppedCurrent', # buffers dropped over current connection
            'buffersDroppedTotal',   # buffers dropped over all connections
            ):
            self.uiState.addKey(key, None)

        # internal state allowing us to track global numbers
        self._buffersDroppedBefore = 0
        self._bytesReadBefore = 0

    def setStats(self, stats):
        """
        @type stats: list
        """
        bytesSent = stats[0]
        #timeAdded = stats[1]
        #timeRemoved = stats[2]
        #timeActive = stats[3]
        timeLastActivity = float(stats[4]) / gst.SECOND
        if len(stats) > 5:
            # added in gst-plugins-base 0.10.11
            buffersDropped = stats[5]
        else:
            # We don't know, but we cannot use None
            # since that would break integer addition below
            buffersDropped = 0

        self.uiState.set('bytesReadCurrent', bytesSent)
        self.uiState.set('buffersDroppedCurrent', buffersDropped)
        self.uiState.set('bytesReadTotal', self._bytesReadBefore + bytesSent)
        self.uiState.set('lastActivity', timeLastActivity)
        if buffersDropped is not None:
            self.uiState.set('buffersDroppedTotal',
                self._buffersDroppedBefore + buffersDropped)

    def connected(self, fd, when=None):
        """
        The client has connected on this fd.
        Update related stats.

        Called only from the reactor thread.
        """
        if not when:
            when = time.time()
        self.fd = fd
        self.uiState.set('fd', fd)
        self.uiState.set('lastConnect', when)
        self.uiState.set('reconnects', self.uiState.get('reconnects', 0) + 1)

    def disconnected(self, when=None):
        """
        The client has disconnected.
        Update related stats.

        Called from GStreamer threads.
        """
        if not when:
            when = time.time()
        self.fd = None

        def updateUIState():
            self.uiState.set('fd', None)
            self.uiState.set('lastDisconnect', when)

            # update our internal counters and reset current counters to 0
            self._bytesReadBefore += self.uiState.get('bytesReadCurrent')
            self.uiState.set('bytesReadCurrent', 0)
            if self.uiState.get('buffersDroppedCurrent') is not None:
                self._buffersDroppedBefore += self.uiState.get(
                    'buffersDroppedCurrent')
                self.uiState.set('buffersDroppedCurrent', 0)
        reactor.callFromThread(updateUIState)

class Eater:
    """
    This class groups eater-related information as used by a Feed Component.

    @ivar eaterId:  id of the feed this is eating from
    @ivar uiState: the serializable UI State for this eater
    """
    def __init__(self, eaterId):
        self.eaterId = eaterId
        self.uiState = componentui.WorkerComponentUIState()
        self.uiState.addKey('eaterId')
        self.uiState.set('eaterId', eaterId)
        # dict for the current connection
        connectionDict = { 
            "timeTimestampDiscont":  None,
            "timestampTimestampDiscont":  0.0,  # ts of buffer after discont,
                                                # in float seconds
            "lastTimestampDiscont":  0.0,
            "totalTimestampDiscont": 0.0,
            "countTimestampDiscont": 0,
            "timeOffsetDiscont":     None,
            "offsetOffsetDiscont":   0,         # offset of buffer after discont
            "lastOffsetDiscont":     0,
            "totalOffsetDiscont":    0,
            "countOffsetDiscont":    0,

         }
        self.uiState.addDictKey('connection', connectionDict)

        for key in (
            'lastConnect',           # last client connection, in epoch seconds
            'lastDisconnect',        # last client disconnect, in epoch seconds
            'totalConnections',      # number of connections made by this client
            'countTimestampDiscont', # number of timestamp disconts seen
            'countOffsetDiscont',    # number of timestamp disconts seen
            ):
            self.uiState.addKey(key, 0)
        for key in (
            'totalTimestampDiscont', # total timestamp discontinuity
            'totalOffsetDiscont',    # total offset discontinuity
            ):
            self.uiState.addKey(key, 0.0)
        self.uiState.addKey('fd', None)

    def connected(self, fd, when=None):
        """
        The eater has been connected.
        Update related stats.
        """
        if not when:
            when = time.time()

        def updateUIState():
            self.uiState.set('lastConnect', when)
            self.uiState.set('fd', fd)
            self.uiState.set('totalConnections',
                self.uiState.get('totalConnections', 0) + 1)

            self.uiState.setitem("connection", "countTimestampDiscont", 0)
            self.uiState.setitem("connection", "timeTimestampDiscont",  None)
            self.uiState.setitem("connection", "lastTimestampDiscont",  0.0)
            self.uiState.setitem("connection", "totalTimestampDiscont", 0.0)
            self.uiState.setitem("connection", "countOffsetDiscont",    0)
            self.uiState.setitem("connection", "timeOffsetDiscont",     None)
            self.uiState.setitem("connection", "lastOffsetDiscont",     0)
            self.uiState.setitem("connection", "totalOffsetDiscont",    0)

        reactor.callFromThread(updateUIState)

    def disconnected(self, when=None):
        """
        The eater has been disconnected.
        Update related stats.
        """
        if not when:
            when = time.time()

        def updateUIState():
            self.uiState.set('lastDisconnect', when)
            self.uiState.set('fd', None)

        reactor.callFromThread(updateUIState)

    def timestampDiscont(self, seconds, timestamp):
        """
        @param seconds:   discont duration in seconds
        @param timestamp: GStreamer timestamp of new buffer, in seconds.

        Inform the eater of a timestamp discontinuity.
        This is called from a bus message handler, so in the main thread.
        """
        uiState = self.uiState

        c = uiState.get('connection') # dict
        uiState.setitem('connection', 'countTimestampDiscont',
            c.get('countTimestampDiscont', 0) + 1)
        uiState.set('countTimestampDiscont',
            uiState.get('countTimestampDiscont', 0) + 1)

        uiState.setitem('connection', 'timeTimestampDiscont', time.time())
        uiState.setitem('connection', 'timestampTimestampDiscont', timestamp)
        uiState.setitem('connection', 'lastTimestampDiscont', seconds)
        uiState.setitem('connection', 'totalTimestampDiscont', 
            c.get('totalTimestampDiscont', 0) + seconds)
        uiState.set('totalTimestampDiscont',
            uiState.get('totalTimestampDiscont', 0) + seconds)

    def offsetDiscont(self, units, offset):
        """
        Inform the eater of an offset discontinuity.
        This is called from a bus message handler, so in the main thread.
        """
        uiState = self.uiState

        c = uiState.get('connection') # dict
        uiState.setitem('connection', 'countOffsetDiscont',
            c.get('countOffsetDiscont', 0) + 1)
        uiState.set('countOffsetDiscont',
            uiState.get('countOffsetDiscont', 0) + 1)

        uiState.setitem('connection', 'timeOffsetDiscont', time.time())
        uiState.setitem('connection', 'offsetOffsetDiscont', offset)
        uiState.setitem('connection', 'lastOffsetDiscont', units)
        uiState.setitem('connection', 'totalOffsetDiscont', 
            c.get('totalOffsetDiscont', 0) + units)
        uiState.set('totalOffsetDiscont',
            uiState.get('totalOffsetDiscont', 0) + units)

class FeedComponent(basecomponent.BaseComponent):
    """
    I am a base class for all Flumotion feed components.

    @cvar checkTimestamp: whether to check continuity of timestamps for eaters
    @cvar checkOffset:    whether to check continuity of offsets for eaters
    """
    # keep these as class variables for the tests
    FDSRC_TMPL = 'fdsrc name=%(name)s'
    DEPAY_TMPL = 'gdpdepay name=%(name)s-depay'
    FEEDER_TMPL = 'gdppay ! multifdsink sync=false name=%(name)s buffers-max=500 buffers-soft-max=450 recover-policy=1'
    # EATER_TMPL is no longer used due to it being dynamic
    # how often to add the buffer probe
    BUFFER_PROBE_ADD_FREQUENCY = 5

    # how often to check that a buffer has arrived recently
    BUFFER_CHECK_FREQUENCY = BUFFER_PROBE_ADD_FREQUENCY * 2.5

    BUFFER_TIME_THRESHOLD = BUFFER_CHECK_FREQUENCY

    logCategory = 'feedcomponent'

    gsignal('feed-ready', str, bool)
    gsignal('error', str, str)

    _reconnectInterval = 3
    
    checkTimestamp = False
    checkOffset = False

    ### BaseComponent interface implementations
    def init(self):
        # add extra keys to state
        self.state.addKey('eaterNames') # feedId of eaters
        self.state.addKey('feederNames') # feedId of feeders

        # add keys for eaters and feeders uiState
        self._feeders = {} # feeder feedId -> Feeder
        self._eaters = {} # eater feedId -> Eater
        self.uiState.addListKey('feeders')
        self.uiState.addListKey('eaters')

        self.pipeline = None
        self.pipeline_signals = []
        self.bus_watch_id = None
        self.files = []
        self.effects = {}
        self._probe_ids = {} # eater name -> probe handler id
        self._feeder_probe_cl = None

        self.clock_provider = None

        self.eater_names = [] # componentName:feedName list
        self._eaterReconnectDC = {} 

        self.feedersFeeding = 0
        self.feed_names = []   # list of feedName
        self.feeder_names = [] # list of feedId

        self._inactiveEaters = [] # list of feedId's
        # feedId -> dict of lastTime, lastConnectTime, lastConnectD,
        # checkEaterDC,
        self._eaterStatus = {}

        # statechange -> [ deferred ]
        self._stateChangeDeferreds = {}

        self._gotFirstNewSegment = {}

        # multifdsink's get-stats signal had critical bugs before this version
        tcppluginversion = gstreamer.get_plugin_version('tcp')
        self._get_stats_supported = tcppluginversion >= (0, 10, 11, 0)

        # check for identity version and set checkTimestamp and checkOffset
        # to false if too old
        vt = gstreamer.get_plugin_version('coreelements')
        if not vt:
            raise errors.MissingElementError('identity')
        if not vt > (0, 10, 12, 0):
            self.checkTimestamp = False
            self.checkOffset = False
            self.addMessage(
                messages.Info(T_(N_(
                    "You will get more debugging information "
                    "if you upgrade to GStreamer 0.10.13 or later "
                    "as and when available."))))

    def do_setup(self):
        """
        Sets up component.
        """
        eater_config = self.config.get('source', [])
        feeder_config = self.config.get('feed', [])

        self.debug("feedcomponent.setup(): eater_config %r" % eater_config)
        self.debug("feedcomponent.setup(): feeder_config %r" % feeder_config)
        
        # this sets self.eater_names
        self.parseEaterConfig(eater_config)

        # all eaters start out inactive
        self._inactiveEaters = self.eater_names[:]

        for name in self.eater_names:
            d = {
                'lastTime': 0,
                'lastConnectTime': 0,
                'lastConnectD': None,
                'checkEaterDC': None
            }
            self._eaterStatus[name] = d
            self._eaters[name] = Eater(name)
            self.uiState.append('eaters', self._eaters[name].uiState)
            self._eaterReconnectDC['eater:' + name] = None

        # this sets self.feeder_names
        self.parseFeederConfig(feeder_config)
        self.feedersWaiting = len(self.feeder_names)
        for feederName in self.feeder_names:
            self._feeders[feederName] = Feeder(feederName)
            self.uiState.append('feeders',
                                 self._feeders[feederName].uiState)

        self.debug('setup() with %d eaters and %d feeders waiting' % (
            len(self._inactiveEaters), self.feedersWaiting))

        pipeline = self.create_pipeline()
        self.set_pipeline(pipeline)

        self.debug('setup() finished')

        return defer.succeed(None)

    ### FeedComponent interface for subclasses
    def create_pipeline(self):
        """
        Subclasses have to implement this method.

        @rtype: L{gst.Pipeline}
        """
        raise NotImplementedError, "subclass must implement create_pipeline"
        
    def set_pipeline(self, pipeline):
        """
        Subclasses can override me.
        They should chain up first.
        """
        if self.pipeline:
            self.cleanup()
        self.pipeline = pipeline
        self.setup_pipeline()
 
    def eaterSetInactive(self, feedId):
        """
        The eater for the given feedId is no longer active
        By default, the component will go hungry.
        """
        self.info('Eater of %s is inactive' % feedId)
        if feedId in self._inactiveEaters:
            self.warning('Eater of %s was already inactive' % feedId)
        else:
            self._inactiveEaters.append(feedId)
        self.setMood(moods.hungry)

    def eaterSetActive(self, feedId):
        """
        The eater for the given feedId is now active and producing data.
        By default, the component will go happy if all eaters are active.
        """
        self.info('Eater of %s is active' % feedId)
        if feedId not in self._inactiveEaters:
            self.warning('Eater of %s was already active' % feedId)
        else:
            self._inactiveEaters.remove(feedId)
        if not self._inactiveEaters:
            self.setMood(moods.happy)
    # FIXME: it may make sense to have an updateMood method, that can be used
    # by the two previous methods, but also in other places, and then
    # overridden.  That would make us have to publicize inactiveEaters

    def eaterTimestampDiscont(self, feedId, prevTs, prevDuration, curTs):
        """
        Inform of a timestamp discontinuity for the given eater.
        """
        discont = curTs - (prevTs + prevDuration)
        dSeconds = discont / float(gst.SECOND)
        self.debug("we have a discont on feedId %s of %f s between %s and %s ", 
            feedId, dSeconds,
            gst.TIME_ARGS(prevTs),
            gst.TIME_ARGS(curTs))
        self._eaters[feedId].timestampDiscont(dSeconds, 
            float(curTs) / float(gst.SECOND))

    def eaterOffsetDiscont(self, feedId, prevOffsetEnd, curOffset):
        """
        Inform of a timestamp discontinuity for the given eater.
        """
        discont = curOffset - prevOffsetEnd
        self.debug(
            "we have a discont on feedId %s of %d units between %d and %d ", 
            feedId, discont, prevOffsetEnd, curOffset)
        self._eaters[feedId].offsetDiscont(discont, curOffset)
         
    ### FeedComponent methods
    def addEffect(self, effect):
        self.effects[effect.name] = effect
        effect.setComponent(self)

    def effectPropertyChanged(self, effectName, propertyName, value):
        """
        Notify the manager that an effect property has changed to a new value.
        
        Admin clients will receive it as a propertyChanged message for
        effectName:propertyName.
        """
        self.medium.callRemote("propertyChanged", self.name,
            "%s:%s" % (effectName, propertyName), value)

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
        self.debug('parsed eater config, eater feedIds %r' % eater_names)
        self.eater_names = eater_names
        self.state.set('eaterNames', self.eater_names)
            
    def parseFeederConfig(self, feeder_config):
        # for pipeline components, in the case there is only one
        # feeder, <feed></feed> still needs to be listed explicitly

        # the feed names come from the config
        # they are specified under <component> as <feed> elements in XML
        self.feed_names = feeder_config
        #self.debug("parseFeederConfig: feed_names: %r" % self.feed_names)

        # we create feeder names this component contains based on feed names
        self.feeder_names = map(lambda n: self.name + ':' + n, self.feed_names)
        self.debug('parsed feeder config, feeders %r' % self.feeder_names)
        self.state.set('feederNames', self.feeder_names)

    def get_eater_names(self):
        """
        Return the list of feeder names this component eats from.

        @returns: a list of "componentName:feedName" strings
        """
        return self.eater_names
    
    def get_feeder_names(self):
        """
        Return the list of feedId's of feeders this component has.

        @returns: a list of "componentName:feedName" strings
        """
        return self.feeder_names

    def get_feed_names(self):
        """
        Return the list of feedeNames for feeds this component has.

        @returns: a list of "feedName" strings
        """
        return self.feed_names

    def get_pipeline(self):
        return self.pipeline

    def _addStateChangeDeferred(self, statechange):
        if statechange not in self._stateChangeDeferreds:
            self._stateChangeDeferreds[statechange] = []

        d = defer.Deferred()
        self._stateChangeDeferreds[statechange].append(d)

        return d

    # GstPython should have something for this, but doesn't.
    def _getStateChange(self, old, new):
        if old == gst.STATE_NULL and new == gst.STATE_READY:
            return gst.STATE_CHANGE_NULL_TO_READY
        elif old == gst.STATE_READY and new == gst.STATE_PAUSED:
            return gst.STATE_CHANGE_READY_TO_PAUSED
        elif old == gst.STATE_PAUSED and new == gst.STATE_PLAYING:
            return gst.STATE_CHANGE_PAUSED_TO_PLAYING
        elif old == gst.STATE_PLAYING and new == gst.STATE_PAUSED:
            return gst.STATE_CHANGE_PLAYING_TO_PAUSED
        elif old == gst.STATE_PAUSED and new == gst.STATE_READY:
            return gst.STATE_CHANGE_PAUSED_TO_READY
        elif old == gst.STATE_READY and new == gst.STATE_NULL:
            return gst.STATE_CHANGE_READY_TO_NULL
        else:
            return 0
       
    def bus_watch_func(self, bus, message):
        t = message.type
        src = message.src

        # print 'message:', t, src and src.get_name() or '(no source)'
        if t == gst.MESSAGE_STATE_CHANGED:
            old, new, pending = message.parse_state_changed()
            # print src.get_name(), old.value_nick, new.value_nick, pending.value_nick
            if src == self.pipeline:
                self.log('state change: %r %s->%s'
                    % (src, old.value_nick, new.value_nick)) 
                if old == gst.STATE_PAUSED and new == gst.STATE_PLAYING:
                    self.setMood(moods.happy)

                change = self._getStateChange(old,new)
                if change in self._stateChangeDeferreds:
                    dlist = self._stateChangeDeferreds[change]
                    for d in dlist:
                        d.callback(None)
                    del self._stateChangeDeferreds[change]

            elif src.get_name() in ['feeder:'+n for n in self.feeder_names]:
                if old == gst.STATE_PAUSED and new == gst.STATE_PLAYING:
                    self.debug('feeder %s is now feeding' % src.get_name())
                    self.feedersWaiting -= 1
                    self.debug('%d feeders waiting' % self.feedersWaiting)
                    # somewhat hacky... feeder:foo:default => default
                    feed_name = src.get_name().split(':')[2]
                    self.emit('feed-ready', feed_name, True)
        elif t == gst.MESSAGE_ERROR:
            gerror, debug = message.parse_error()
            self.warning('element %s error %s %s' %
                         (src.get_path_string(), gerror, debug))
            self.setMood(moods.sad)
            # generate a unique id
            id = "%s-%s-%d" % (self.name, gerror.domain, gerror.code)
            m = messages.Error(T_(N_(
                "Internal GStreamer error.")),
                debug="%s\n%s: %d\n%s" % (
                    gerror.message, gerror.domain, gerror.code, debug),
                id=id, priority=40)
            self.state.append('messages', m)
            # if we have a state change defer that has not yet
            # fired, we should errback it
            changes = [gst.STATE_CHANGE_NULL_TO_READY, 
                gst.STATE_CHANGE_READY_TO_PAUSED,
                gst.STATE_CHANGE_PAUSED_TO_PLAYING]
            # get current state and add downward state changes from states
            # higher than current element state
            curstate = self.pipeline.get_state()
            if curstate == gst.STATE_NULL:
                changes.append(gst.STATE_CHANGE_READY_TO_NULL)
            if curstate <= gst.STATE_PAUSED:
                changes.append(gst.STATE_CHANGE_PLAYING_TO_PAUSED)
            if curstate <= gst.STATE_READY:
                changes.append(gst.STATE_CHANGE_PAUSED_TO_READY)
            for change in changes:
                if change in self._stateChangeDeferreds:
                    self.log("We have an error, going to errback pending "
                        "state change defers")
                    dlist = self._stateChangeDeferreds[change]
                    for d in dlist:
                        d.errback(errors.ComponentStartHandledError(
                            gerror.message))
                    del self._stateChangeDeferreds[change]

        elif t == gst.MESSAGE_EOS:
            name = src.get_name()
            if name in ['eater:' + n for n in self.eater_names]:
                self.info('End of stream in eater %s' % src.get_name())
                feedId = name[len('eater:'):]
                self.eaterSetInactive(feedId)
                # start reconnection
                self._reconnectEater(feedId)
        elif t == gst.MESSAGE_ELEMENT:
            if message.structure.get_name() == 'imperfect-timestamp':
                identityName = src.get_name()
                eaterName = identityName.split("-identity")[0]
                feedId = eaterName[len('eater:'):]
                
                self.log("we have an imperfect stream from %s" % src.get_name())
                # figure out the discontinuity
                s = message.structure
                self.eaterTimestampDiscont(feedId, s["prev-timestamp"],
                    s["prev-duration"], s["cur-timestamp"])
            elif message.structure.get_name() == 'imperfect-offset':
                identityName = src.get_name()
                eaterName = identityName.split("-identity")[0]
                feedId = eaterName[len('eater:'):]
                
                self.log("we have an imperfect stream from %s" % src.get_name())
                # figure out the discontinuity
                s = message.structure
                self.eaterOffsetDiscont(feedId, s["prev-offset-end"],
                    s["cur-offset"])


        else:
            self.log('message received: %r' % message)

        return True

    # FIXME: privatize
    def setup_pipeline(self):
        self.debug('setup_pipeline()')
        assert self.bus_watch_id == None

        # disable the pipeline's management of base_time -- we're going
        # to set it ourselves.
        self.pipeline.set_new_stream_time(gst.CLOCK_TIME_NONE)

        self.pipeline.set_name('pipeline-' + self.getName())
        bus = self.pipeline.get_bus()
        bus.add_signal_watch()
        self.bus_watch_id = bus.connect('message', self.bus_watch_func)
        sig_id = self.pipeline.connect('deep-notify',
                                       gstreamer.verbose_deep_notify_cb, self)
        self.pipeline_signals.append(sig_id)

        # start checking eaters
        for feedId in self.eater_names:
            status = self._eaterStatus[feedId]
            status['checkEaterDC'] = reactor.callLater(
                self.BUFFER_CHECK_FREQUENCY, self._checkEater, feedId)

        # start checking feeders, if we have a sufficiently recent multifdsink
        if self._get_stats_supported:
            self._feeder_probe_cl = reactor.callLater(
                self.BUFFER_CHECK_FREQUENCY, self._feeder_probe_calllater)
        else:
            self.warning("Feeder statistics unavailable, your "
                "gst-plugins-base is too old")
            self.addMessage(
                messages.Warning(T_(N_(
                    "Your gst-plugins-base is too old (older than 0.10.11), so "
                    "feeder statistics will be unavailable. Please upgrade to "
                    "the most recent gst-plugins-base release.")), 
                    id='multifdsink'))

    def pipeline_stop(self):
        if not self.pipeline:
            return
        
        if self.clock_provider:
            self.clock_provider.set_property('active', False)
            self.clock_provider = None
        retval = self.pipeline.set_state(gst.STATE_NULL)
        if retval != gst.STATE_CHANGE_SUCCESS:
            self.warning('Setting pipeline to NULL failed')

    def cleanup(self):
        self.debug("cleaning up")
        
        assert self.pipeline != None

        self.pipeline_stop()
        # Disconnect signals
        map(self.pipeline.disconnect, self.pipeline_signals)
        self.pipeline.get_bus().disconnect(self.bus_watch_id)
        self.pipeline.get_bus().remove_signal_watch()
        self.pipeline = None
        self.pipeline_signals = []
        self.bus_watch_id = None

        if self._feeder_probe_cl:
            self._feeder_probe_cl.cancel()
            self._feeder_probe_cl = None

        # clean up checkEater callLaters
        for feedId in self.eater_names:
            status = self._eaterStatus[feedId]
            if status['checkEaterDC']:
                status['checkEaterDC'].cancel()
                status['checkEaterDC'] = None

    def do_stop(self):
        self.debug('Stopping')
        if self.pipeline:
            self.cleanup()
        self.debug('Stopped')
        return defer.succeed(None)

    def set_master_clock(self, ip, port, base_time):
        self.debug("Master clock set to %s:%d with base_time %s", ip, port, 
            gst.TIME_ARGS(base_time))

        clock = gst.NetClientClock(None, ip, port, base_time)
        self.pipeline.set_base_time(base_time)
        self.pipeline.use_clock(clock)

    def provide_master_clock(self, port):
        """
        Tell the component to provide a master clock on the given port.

        @returns: (ip, port, base_time) triple.
        """
        def pipelinePaused(r):
            clock = self.pipeline.get_clock()
            # make sure the pipeline sticks with this clock
            self.pipeline.use_clock(clock)

            self.clock_provider = gst.NetTimeProvider(clock, None, port)
            # small window here but that's ok
            self.clock_provider.set_property('active', False)
        
            base_time = clock.get_time()
            self.pipeline.set_base_time(base_time)

            self.debug('provided master clock from %r, base time %s'
                       % (clock, gst.TIME_ARGS(base_time)))

            if self.medium:
                # FIXME: This isn't always correct. We need a more flexible API,
                # and a proper network map, to do this. Even then, it's not 
                # always going to be possible.
                ip = self.medium.getIP()
            else:
                ip = "127.0.0.1"

            return (ip, port, base_time)

        if not self.pipeline:
            self.warning('No self.pipeline, cannot provide master clock')
            # FIXME: should we have a NoSetupError() for cases where setup
            # was not called ? For now we fall through and get an exception

        if self.clock_provider:
            self.warning('already had a clock provider, removing it')
            self.clock_provider = None

        # We need to be >= PAUSED to get the correct clock, in general
        (ret, state, pending) = self.pipeline.get_state(0)
        if state != gst.STATE_PAUSED and state != gst.STATE_PLAYING:
            self.info ("Setting pipeline to PAUSED")

            d = self._addStateChangeDeferred(gst.STATE_CHANGE_READY_TO_PAUSED)
            d.addCallback(pipelinePaused)

            self.pipeline.set_state(gst.STATE_PAUSED)
            return d
        else:
            self.info ("Pipeline already started, retrieving clocking")
            # Just return the already set up info, as a fired deferred
            ip = self.state.get('manager-ip')
            base_time = self.pipeline.get_base_time()
            d = defer.Deferred()
            d.callback((ip, port, base_time))
            return d

    # FIXME: rename, since this just starts the pipeline,
    # and linking is done by the manager
    def link(self):
        """
        Make the component eat from the feeds it depends on and start
        producing feeds itself.

        @rtype: L{twisted.internet.defer.Deferred}
        """
        # set pipeline to playing, and provide clock if asked for
        if self.clock_provider:
            self.clock_provider.set_property('active', True)

        # attach event-probe callbacks for each eater
        for feedId in self.get_eater_names():
            self.debug('adding event probe for eater of %s' % feedId)
            name = "eater:%s" % feedId
            eater = self.get_element(name)
            # FIXME: should probably raise
            if not eater:
                self.warning('No element named %s in pipeline' % name)
                continue
            pad = eater.get_pad("src")
            pad.add_event_probe(self._eater_event_probe_cb, feedId)
            gdp_version = gstreamer.get_plugin_version('gdp')
            if gdp_version[2] < 11 and not (gdp_version[2] == 10 and \
                                            gdp_version[3] > 0):
                depay = self.get_element("%s-depay" % name)
                depaysrc = depay.get_pad("src")
                depaysrc.add_event_probe(self._depay_eater_event_probe_cb, 
                    feedId)
            self._add_buffer_probe(pad, feedId, firstTime=True)

        self.debug("Setting pipeline %r to GST_STATE_PLAYING", self.pipeline)
        self.pipeline.set_state(gst.STATE_PLAYING)

    def _feeder_probe_calllater(self):
        for feedId, feeder in self._feeders.items():
            feederElement = self.get_element("feeder:%s" % feedId)
            for client in feeder.getClients():
                # a currently disconnected client will have fd None
                if client.fd is not None:
                    array = feederElement.emit('get-stats', client.fd)
                    if len(array) == 0:
                        # There is an unavoidable race here: we can't know 
                        # whether the fd has been removed from multifdsink.
                        # However, if we call get-stats on an fd that 
                        # multifdsink doesn't know about, we just get a 0-length
                        # array. We ensure that we don't reuse the FD too soon
                        # so this can't result in calling this on a valid but 
                        # WRONG fd
                        self.debug('Feeder element for feed %s does not know '
                            'client fd %d' % (feedId, client.fd))
                    else:
                        client.setStats(array)
        self._feeder_probe_cl = reactor.callLater(self.BUFFER_CHECK_FREQUENCY, 
            self._feeder_probe_calllater)

    def _add_buffer_probe(self, pad, feedId, firstTime=False):
        # attached from above, and called again every
        # BUFFER_PROBE_ADD_FREQUENCY seconds
        method = self.log
        if firstTime: method = self.debug
        method("Adding new scheduled buffer probe for %s" % feedId)
        self._probe_ids[feedId] = pad.add_buffer_probe(self._buffer_probe_cb,
            feedId, firstTime)

    def _buffer_probe_cb(self, pad, buffer, feedId, firstTime=False):
        """
        Periodically scheduled buffer probe, that ensures that we're currently
        actually having dataflow through our eater elements.

        Called from GStreamer threads.

        @param pad       The gst.Pad srcpad for one eater in this component.
        @param buffer    A gst.Buffer that has arrived on this pad
        @param feedId    The feedId for the feed we're eating on this pad
        @param firstTime Boolean, true if this is the first time this buffer 
                         probe has been added for this eater.
        """

        # log info about first incoming buffer for this check interval,
        # then remove ourselves
        method = self.log
        if firstTime: method = self.debug
        method('buffer probe on eater %s has timestamp %s' % (
            feedId, gst.TIME_ARGS(buffer.timestamp)))
        # We carefully only use atomic (w.r.t. the GIL) operations on the dicts
        # here: we pop things from _probe_ids, and only set things in 
        # self._eaterStatus[feedId].

        # now store the last buffer received time
        self._eaterStatus[feedId]['lastTime'] = time.time()
        probeid = self._probe_ids.pop(feedId, None)
        if probeid:
            pad.remove_buffer_probe(probeid)

            # add buffer probe every BUFFER_PROBE_ADD_FREQUENCY seconds
            reactor.callFromThread(reactor.callLater, 
                self.BUFFER_PROBE_ADD_FREQUENCY,
                self._add_buffer_probe, pad, feedId)

        # since we've received a buffer, it makes sense to call _checkEater,
        # allowing us to revert to go back to happy as soon as possible
        reactor.callFromThread(self._checkEater, feedId)

        return True

    def _checkEater(self, feedId):
        """
        Check that buffers are being received by the eater.
        If no buffer was received for more than BUFFER_TIME_THRESHOLD on
        a connected feed, I call eaterSetInactive.
        Likewise, if a buffer was received on an inactive feed, I call
        eaterSetActive.

        I am used both as a callLater and as a direct method.
        """
        status = self._eaterStatus[feedId]
        # a callLater is not active anymore while it's being executed,
        # cancel deferred call if there's one pending (i.e. if we were called
        # by something other than the deferred call)
        if status['checkEaterDC'] and status['checkEaterDC'].active():
            status['checkEaterDC'].cancel()

        self.log('_checkEater: last buffer at %r' % status['lastTime'])
        currentTime = time.time()

        # we do not run any checks if the last buffer time is 0 or lower
        # this allows us to make sure no check is run when this is needed
        # (for example, on eos)
        if status['lastTime'] > 0:
            delta = currentTime - status['lastTime']

            if feedId not in self._inactiveEaters \
            and delta > self.BUFFER_TIME_THRESHOLD:
                self.debug(
                    'No data received for %r seconds, feed %s inactive' % (
                        self.BUFFER_TIME_THRESHOLD, feedId))
                self.eaterSetInactive(feedId)
                # TODO: we never actually disconnect the eater explicitly, but 
                # a successful reconnect will cause the old fd to be closed. 
                # Maybe we should change this?
                # start reconnection
                self._reconnectEater(feedId)

            # mark as connected if recent data received
            elif feedId in self._inactiveEaters \
            and delta < self.BUFFER_TIME_THRESHOLD:
                self.debug('Received data, feed %s active' % feedId)
                self.eaterSetActive(feedId)

        # retry a connect call if it has been too long since the
        # last and we still don't have data
        if feedId in self._inactiveEaters \
        and status['lastConnectTime'] > 0:
            connectDelta = currentTime - status['lastConnectTime']
            if connectDelta > self.BUFFER_TIME_THRESHOLD:
                self.debug('Too long since last reconnect, retrying')
                self._reconnectEater(feedId)

        # we run forever
        status['checkEaterDC'] = reactor.callLater(self.BUFFER_CHECK_FREQUENCY,
            self._checkEater, feedId)
        
    def _reconnectEater(self, feedId):
        eater = self._eaters[feedId]
        eater.disconnected()
        # reconnect the eater for the given feedId, updating the internal
        # status for that eater
        status = self._eaterStatus[feedId]

        # If an eater received a buffer before being marked as disconnected,
        # and still within the buffer check interval, the next eaterCheck
        # call could accidentally think the eater was reconnected properly.
        # Setting lastTime to 0 here avoids that happening in eaterCheck.
        self._eaterStatus[feedId]['lastTime'] = 0

        status['lastConnectTime'] = time.time()
        if status['lastConnectD']:
            self.debug('Cancel previous connection attempt ?')
            # FIXME: it seems fine to not errback explicitly, but we may
            # want to investigate further later
        d = self.medium.connectEater(feedId)
        def connectEaterCb(result, status, eater):
            status['lastConnectD'] = None
        d.addCallback(connectEaterCb, status, eater)
        status['lastConnectD'] = d

    def get_element(self, element_name):
        """Get an element out of the pipeline.

        If it is possible that the component has not yet been set up,
        the caller needs to check if self.pipeline is actually set.
        """
        assert self.pipeline
        element = self.pipeline.get_by_name(element_name)
        return element
    
    def get_element_property(self, element_name, property):
        'Gets a property of an element in the GStreamer pipeline.'
        self.debug("%s: getting property %s of element %s" % (self.getName(), property, element_name))
        element = self.get_element(element_name)
        if not element:
            msg = "Element '%s' does not exist" % element_name
            self.warning(msg)
            raise errors.PropertyError(msg)
        
        self.debug('getting property %s on element %s' % (property, element_name))
        try:
            value = element.get_property(property)
        except (ValueError, TypeError):
            msg = "Property '%s' on element '%s' does not exist" % (property, element_name)
            self.warning(msg)
            raise errors.PropertyError(msg)

        # param enums and enums need to be returned by integer value
        if isinstance(value, gobject.GEnum):
            value = int(value)

        return value

    def set_element_property(self, element_name, property, value):
        'Sets a property on an element in the GStreamer pipeline.'
        self.debug("%s: setting property %s of element %s to %s" % (
            self.getName(), property, element_name, value))
        element = self.get_element(element_name)
        if not element:
            msg = "Element '%s' does not exist" % element_name
            self.warning(msg)
            raise errors.PropertyError(msg)

        self.debug('setting property %s on element %r to %s' %
                   (property, element_name, value))
        pygobject.gobject_set_property(element, property, value)
    
    ### methods to connect component eaters and feeders
    def feedToFD(self, feedName, fd, cleanup, eaterId=None):
        """
        @param feedName: name of the feed to feed to the given fd.
        @type  feedName: str
        @param fd:       the file descriptor to feed to
        @type  fd:       int
        @param cleanup:  the function to call when the FD is no longer feeding
        @type  cleanup:  callable
        """
        self.debug('FeedToFD(%s, %d)' % (feedName, fd))
        feedId = common.feedId(self.name, feedName)

        if not self.pipeline:
            self.warning('told to feed %s to fd %d, but pipeline not '
                         'running yet', feedId, fd)
            cleanup(fd)
            # can happen if we are restarting but the other component is
            # happy; assume other side will reconnect later
            return

        elementName = "feeder:%s" % feedId
        element = self.get_element(elementName)
        if not element:
            msg = "Cannot find feeder element named '%s'" % elementName
            id = "feedToFD-%s" % feedName
            m = messages.Warning(T_(N_("Internal Flumotion error.")),
                debug=msg, id=id, priority=40)
            self.state.append('messages', m)
            self.warning(msg)
            return False

        clientId = eaterId or ('client-%d' % fd)

        element.emit('add', fd)
        self._feeders[feedId].clientConnected(clientId, fd, cleanup)

    def removeClientCallback(self, sink, fd):
        """
        Called (as a signal callback) when the FD is no longer in use by
        multifdsink.
        This will call the registered callable on the fd.

        Called from GStreamer threads.
        """
        self.debug("cleaning up fd %d", fd)
        feedId = ':'.join(sink.get_name().split(':')[1:])
        self._feeders[feedId].clientDisconnected(fd)

    def eatFromFD(self, feedId, fd):
        """
        Tell the component to eat the given feedId from the given fd.
        The component takes over the ownership of the fd, closing it when
        no longer eating.

        @param feedId: feed id (componentName:feedName) to eat from through
                       the given fd
        @type  feedId: str
        @param fd:     the file descriptor to eat from
        @type  fd:     int
        """
        self.debug('EatFromFD(%s, %d)' % (feedId, fd))

        if not self.pipeline:
            self.warning('told to eat %s from fd %d, but pipeline not '
                         'running yet', feedId, fd)
            # can happen if we are restarting but the other component is
            # happy; assume other side will reconnect later
            os.close(fd)
            return

        eaterName = "eater:%s" % feedId
        self.debug('looking up element %s' % eaterName)
        element = self.get_element(eaterName)
 
        # fdsrc only switches to the new fd in ready or below
        (result, current, pending) = element.get_state(0L)
        if current not in [gst.STATE_NULL, gst.STATE_READY]:
            self.debug('eater %s in state %r, kidnapping it' % (
                eaterName, current))

            # we unlink fdsrc from its peer, take it out of the pipeline
            # so we can set it to READY without having it send EOS,
            # then switch fd and put it back in.
            # To do this safely, we first block fdsrc:src, then let the 
            # component do any neccesary unlocking (needed for multi-input
            # elements)
            srcpad = element.get_pad('src')
            
            def _block_cb(pad, blocked):
                pass
            srcpad.set_blocked_async(True, _block_cb)
            self.unblock_eater(feedId)

            # Now, we can switch FD with this mess
            sinkpad = srcpad.get_peer()
            srcpad.unlink(sinkpad)
            self.pipeline.remove(element)
            self.log("setting to ready")
            element.set_state(gst.STATE_READY)
            self.log("setting to ready complete!!!")
            old = element.get_property('fd')
            os.close(old)
            element.set_property('fd', fd)
            self.pipeline.add(element)
            srcpad.link(sinkpad)
            element.set_state(gst.STATE_PLAYING)
            # We're done; unblock the pad
            srcpad.set_blocked_async(False, _block_cb)
        else:
            element.set_property('fd', fd)

        # update our eater uiState
        self._eaters[feedId].connected(fd)

    def unblock_eater(self, feedId):
        """
        After this function returns, the stream lock for this eater must have
        been released. If your component needs to do something here, override
        this method.
        """
        pass

    def _eater_event_probe_cb(self, pad, event, feedId):
        """
        An event probe used to consume unwanted EOS events on eaters.

        Called from GStreamer threads.
        """
        if event.type == gst.EVENT_EOS:    
            self.info(
                'End of stream on feed %s, disconnect will be triggered' %
                    feedId)
            # We swallow it because otherwise our component acts on the EOS
            # and we can't recover from that later.  Instead, fdsrc will be
            # taken out and given a new fd on the next eatFromFD call.
            return False
        return True

    def _depay_eater_event_probe_cb(self, pad, event, feedId):
        """
        An event probe used to consume unwanted duplicate newsegment events.

        Called from GStreamer threads.
        """
        if event.type == gst.EVENT_NEWSEGMENT:
            # We do this because we know gdppay/gdpdepay screw up on 2nd
            # newsegments
            if feedId in self._gotFirstNewSegment:
                self.info(
                    "Subsequent new segment event received on depay on "
                    " feed %s" % feedId)
                # swallow
                return False
            else:
                self._gotFirstNewSegment[feedId] = True
        return True

pygobject.type_register(FeedComponent)
