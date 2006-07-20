# -*- Mode: Python -*-
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

import gst
import gobject
import time

from twisted.internet import reactor, defer

from flumotion.component import component as basecomponent
from flumotion.common import common, errors, pygobject, messages
from flumotion.common import gstreamer
from flumotion.worker import feed

from flumotion.common.planet import moods
from flumotion.common.pygobject import gsignal

from flumotion.common.messages import N_
T_ = messages.gettexter('flumotion')


class FeedComponent(basecomponent.BaseComponent):
    """
    I am a base class for all Flumotion feed components.
    """
    # keep these as class variables for the tests
    EATER_TMPL = 'fdsrc name=%(name)s ! gdpdepay'
    FEEDER_TMPL = 'gdppay ! multifdsink sync=false name=%(name)s buffers-max=500 buffers-soft-max=450 recover-policy=1'

    # how often to add the buffer probe
    BUFFER_PROBE_ADD_FREQUENCY = 5

    # how often to check that a buffer has arrived recently
    BUFFER_CHECK_FREQUENCY = 5

    BUFFER_TIME_THRESHOLD = 5

    logCategory = 'feedcomponent'

    gsignal('feed-ready', str, bool)
    gsignal('error', str, str)

    _reconnectInterval = 3
    
    ### BaseComponent interface implementations
    def init(self):
        # add extra keys to state
        self.state.addKey('eaterNames')
        self.state.addKey('feederNames')

        self.pipeline = None
        self.pipeline_signals = []
        self.bus_watch_id = None
        self.files = []
        self.effects = {}
        self._probe_ids = {} # eater name -> probe handler id

        self.clock_provider = None

        self.eater_names = [] # componentName:feedName list
        self._eaterReconnectDC = {} 

        self.feedersFeeding = 0
        self.feed_names = []
        self.feeder_names = []

        self.last_buffer_time = 0

    def do_setup(self):
        """
        Sets up component.
        """
        eater_config = self.config.get('source', [])
        feeder_config = self.config.get('feed', [])

        self.debug("feedcomponent.setup(): eater_config %r" % eater_config)
        self.debug("feedcomponent.setup(): feeder_config %r" % feeder_config)
        
        self.parseEaterConfig(eater_config)
        self.eatersWaiting = len(self.eater_names)
        for name in self.eater_names:
            self._eaterReconnectDC['eater:' + name] = None

        self.parseFeederConfig(feeder_config)
        self.feedersWaiting = len(self.feeder_names)
        self.debug('setup() with %d eaters and %d feeders waiting' % (
            self.eatersWaiting, self.feedersWaiting))

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
        assert self.pipeline == None
        self.pipeline = pipeline
        self.setup_pipeline()
 
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
        self.debug('parsed eater config, eaters %r' % eater_names)
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
        Return the list of feeder names this component has.

        @returns: a list of "componentName:feedName" strings
        """
        return self.feeder_names

    def get_feed_names(self):
        """
        Return the list of feeder names this component has.

        @returns: a list of "feedName" strings
        """
        return self.feed_names

    def restart(self):
        self.debug('restarting')
        self.cleanup()
        self.setup_pipeline()
       
    def get_pipeline(self):
        return self.pipeline

       
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
        elif t == gst.MESSAGE_EOS:
            if src == self.pipeline:
                self.info('End-of-stream in pipeline, stopping')
                self.setMood(moods.sad)
                self.cleanup()
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

        # check for buffers
        reactor.callLater(self.BUFFER_CHECK_FREQUENCY,
            self._check_for_buffer_data)

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

    def do_stop(self):
        self.debug('Stopping')
        if self.pipeline:
            self.cleanup()
        self.debug('Stopped')
        return defer.succeed(None)

    def set_master_clock(self, ip, port, base_time):
        clock = gst.NetClientClock(None, ip, port, base_time)
        self.pipeline.set_base_time(base_time)
        self.pipeline.use_clock(clock)

    def provide_master_clock(self, port):
        """
        Tell the component to provide a master clock on the given port.

        @returns: (ip, port, base_time) triple.
        """
        if not self.pipeline:
            self.warning('No self.pipeline, cannot provide master clock')
            # FIXME: should we have a NoSetupError() for cases where setup
            # was not called ? For now we fall through and get an exception

        if self.clock_provider:
            self.warning('already had a clock provider, removing it')
            self.clock_provider = None

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

        # FIXME: this is always localhost, no ? Not sure if this is useful
        ip = self.state.get('ip')

        return (ip, port, base_time)

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
        self.pipeline.set_state(gst.STATE_PLAYING)

        # attach buffer-probe callbacks for each eater
        for eaterName in self.get_eater_names():
            self.debug('adding buffer probe for eater %s' % eaterName)
            name = "eater:%s" % eaterName
            eater = self.get_element(name)
            # FIXME: should probably raise
            if not eater:
                self.warning('No element named %s in pipeline' % name)
                continue
            pad = eater.get_pad("src")
            self._add_buffer_probe(pad, name, firstTime=True)

    def _add_buffer_probe(self, pad, name, firstTime=False):
        # attached from above, and called again every
        # BUFFER_PROBE_ADD_FREQUENCY seconds
        method = self.log
        if firstTime: method = self.debug
        method("Adding new scheduled buffer probe for %s" % name)
        self._probe_ids[name] = pad.add_buffer_probe(self._buffer_probe_cb,
            name, firstTime)

    def _buffer_probe_cb(self, pad, buffer, name, firstTime=False):
        # log info about first incoming buffer for this check interval,
        # then remove ourselves
        method = self.log
        if firstTime: method = self.debug
        method('buffer probe on eater %s has timestamp %.3f' % (
            name, float(buffer.timestamp) / gst.SECOND))
        # now store the last buffer received time
        self.last_buffer_time = time.time()
        if self._probe_ids[name]:
            pad.remove_buffer_probe(self._probe_ids[name])
            self._probe_ids[name] = None
            # add buffer probe every BUFFER_PROBE_ADD_FREQUENCY seconds
            reactor.callLater(self.BUFFER_PROBE_ADD_FREQUENCY,
                self._add_buffer_probe, pad, name)

        return True

    def _check_for_buffer_data(self):
        """
        Check that buffers are being received.
        I am used as a check run every x seconds and set mood to hungry if no
        buffer received within BUFFER_TIME_THRESHOLD and set mood to happy if
        a buffer has been received in that threshold but component is hungry
        """
        self.log('_check_for_buffer_data: last time %r' % self.last_buffer_time)
        if self.last_buffer_time > 0:
            current_time = time.time()
            delta = current_time - self.last_buffer_time
            if self.getMood() == moods.happy.value \
            and delta > self.BUFFER_TIME_THRESHOLD:
                self.info('No data received for %r seconds, turning hungry' %
                    self.BUFFER_TIME_THRESHOLD)
                self.setMood(moods.hungry)
            if self.getMood() == moods.hungry.value \
            and delta < self.BUFFER_TIME_THRESHOLD:
                # we are hungry but we have a recent buffer
                # so set to happy
                self.info('Received data again, turning happy')
                self.setMood(moods.happy)
        reactor.callLater(self.BUFFER_CHECK_FREQUENCY,
            self._check_for_buffer_data)

        
    def get_element(self, element_name):
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
    def feedToFD(self, feedName, fd):
        """
        @param feedName: name of the feed to feed to the given fd.
        @type  feedName: str
        @param fd:       the file descriptor to feed to
        @type  fd:       int
        """
        self.debug('FeedToFD(%s, %d)' % (feedName, fd))
        elementName = "feeder:%s" % common.feedId(self.name, feedName)
        element = self.get_element(elementName)
        element.emit('add', fd)

    def eatFromFD(self, feedId, fd):
        """
        @param feedId: feed id (componentName:feedName) to eat from through
                       the given fd
        @type  feedId: str
        @param fd:     the file descriptor to eat from
        @type  fd:     int
        """
        self.debug('EatFromFD(%s, %d)' % (feedId, fd))
        elementName = "eater:%s" % feedId
        self.debug('looking up element %s' % elementName)
        element = self.get_element(elementName)
        #noreallymyfd = int(fd)
        #element.set_property('fd', noreallymyfd)
        element.set_property('fd', fd)

pygobject.type_register(FeedComponent)
