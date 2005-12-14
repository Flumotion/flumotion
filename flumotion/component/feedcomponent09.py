# -*- Mode: Python -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# Flumotion - a streaming media server
# Copyright (C) 2004,2005 Fluendo, S.L. (www.fluendo.com). All rights reserved.

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

from twisted.internet import reactor

from flumotion.component import component as basecomponent
from flumotion.common import common, errors, compat
from flumotion.common import gstreamer, pygobject

from flumotion.common.planet import moods
from flumotion.common.pygobject import gsignal

class FeedComponent(basecomponent.BaseComponent):
    """
    I am a base class for all Flumotion feed components.
    """
    # keep these as class variables for the tests
    EATER_TMPL = 'tcpclientsrc name=%(name)s'
    FEEDER_TMPL = 'tcpserversink sync=false name=%(name)s buffers-max=500 buffers-soft-max=450 recover-policy=1'

    logCategory = 'feedcomponent'

    gsignal('feed-ready', str, bool)
    gsignal('error', str, str)

    _reconnectInterval = 3
    
    def setup(self, config):
        """
        @param config: the configuration dictionary of the component
        @type  config: dict
        """
        basecomponent.BaseComponent.setup(self, config)

        eater_config = config.get('source', [])
        feeder_config = config.get('feed', [])

        self.debug("feedcomponent.setup(): eater_config %r" % eater_config)
        self.debug("feedcomponent.setup(): feeder_config %r" % feeder_config)
        
        self.pipeline = None
        self.pipeline_signals = []
        self.bus_watch_id = None
        self.files = []
        self.effects = {}
        self._probe_ids = {} # eater name -> probe handler id

        self.clock_provider = None

        # add extra keys to state
        self.state.addKey('eaterNames')
        self.state.addKey('feederNames')

        self.feed_names = None # done by self.parse*
        self.feeder_names = None

        self.eater_names = [] # componentName:feedName list
        self.parseEaterConfig(eater_config)
        self.eatersWaiting = len(self.eater_names)
        self._eaterReconnectDC = {} 
        for name in self.eater_names:
            self._eaterReconnectDC['eater:' + name] = None

        self.feedersFeeding = 0
        self.feed_names = []
        self.feeder_names = []
        self.parseFeederConfig(feeder_config)
        self.feedersWaiting = len(self.feeder_names)
        self.debug('setup() with %d eaters and %d feeders waiting' % (
            self.eatersWaiting, self.feedersWaiting))

        pipeline = self.create_pipeline()
        self.set_pipeline(pipeline)

        self.debug('setup() finished')

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
        self.eater_names = eater_names
            
    def parseFeederConfig(self, feeder_config):
        # for pipeline components, in the case there is only one
        # feeder, <feed></feed> still needs to be listed explicitly

        # the feed names come from the config
        # they are specified under <component> as <feed> elements in XML
        self.feed_names = feeder_config
        #self.debug("parseFeederConfig: feed_names: %r" % self.feed_names)

        # we create feeder names this component contains based on feed names
        self.feeder_names = map(lambda n: self.name + ':' + n, self.feed_names)

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

    def create_pipeline(self):
        raise NotImplementedError, "subclass must implement create_pipeline"
        
    def set_pipeline(self, pipeline):
        self.pipeline = pipeline
        self.setup_pipeline()
        
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
            err, debug = message.parse_error()
            self.debug('element %s error %s %s' %
                       (src.get_path_string(), err, debug))
            self.setMood(moods.sad)
            self.state.set('message',
                "GStreamer error in component %s (%s)" % (self.name, message))
            self.emit('error', src.get_path_string(), err.message)
        elif t == gst.MESSAGE_EOS:
            if src == self.pipeline:
                self.info('End-of-stream in pipeline, stopping')
                self.cleanup()
        else:
            self.log('message received: %r' % message)

        return True

    def setup_pipeline(self):
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

    def pipeline_stop(self):
        if not self.pipeline:
            return
        
        if self.clock_provider:
            self.clock_provider.set_property('active', False)
            self.clock_provider = None
        retval = self.pipeline.set_state(gst.STATE_NULL)
        if retval != gst.STATE_CHANGE_SUCCESS:
            self.warning('Setting pipeline to NULL failed')

    def _setup_eaters(self, eatersData):
        """
        Set up the feeded GStreamer elements in our pipeline based on
        information in the tuple.  For each feeded element in the tuple,
        it sets the host and port of the feeder on the feeded element.

        @type eatersData: list
        @param eatersData: list of (feederName, host, port) tuples
        """
        if not self.pipeline:
            raise errors.NotReadyError('No pipeline')
        
        # Setup all eaters
        for feederName, host, port in eatersData:
            self.debug('Going to connect to feeder %s (%s:%d)' % (feederName, host, port))
            name = 'eater:' + feederName
            eater = self.get_element(name)
            assert eater, 'No eater element named %s in pipeline' % name
            assert isinstance(eater, gst.Element)
            
            eater.set_property('host', host)
            eater.set_property('port', port)
            eater.set_property('protocol', 'gdp')

    def _setup_feeders(self, feedersData):
        """
        Set up the feeding GStreamer elements in our pipeline based on
        information in the tuple.  For each feeding element in the tuple,
        it sets the host and port it will listen as.

        @type  feedersData: tuple
        @param feedersData: a list of (feederName, host, port) tuples.
        """
 
        if not self.pipeline:
            raise errors.NotReadyError('No pipeline')

        self.debug("_setup_feeders: feedersData %r" % feedersData)

        for feeder in self.feeder_names:
            assert feeder in [x[0] for x in feedersData], \
                   "feedersData does not mention feeder %s" % feeder

        for feeder_name, host, port in feedersData:
            self.debug('Going to listen on feeder %s (%s:%d)' % (
                feeder_name, host, port))
            name = 'feeder:' + feeder_name
            feeder = self.get_element(name)
            assert feeder, 'No feeder element named %s in pipeline' % name
            assert isinstance(feeder, gst.Element)

            feeder.set_property('host', host)
            feeder.set_property('port', port)
            feeder.set_property('protocol', 'gdp')

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

    def stop(self):
        self.debug('Stopping')
        if self.pipeline:
            self.cleanup()
        self.debug('Stopped')
        basecomponent.BaseComponent.stop(self)

    def set_master_clock(self, ip, port, base_time):
        clock = gst.NetClientClock(None, ip, port, base_time)
        self.pipeline.set_base_time(base_time)
        self.pipeline.use_clock(clock)

    def provide_master_clock(self, port):
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

        ip = self.state.get('ip')

        return (ip, port, base_time)

    # FIXME: rename the comment, unambiguate it, and comment on it
    # FIXME: rename, unambiguate and comment
    def link(self, eatersData, feedersData):
        """
        Make the component eat from the feeds it depends on and start
        producing feeds itself.

        @param eatersData: list of (feederName, host, port) tuples to eat from
        @param feedersData: list of (feederName, host, port) tuples to
        use as feeders
        """
        # if we have eaters waiting, we start out hungry, else waking
        self.setMood(moods.waking)

        self.debug('manager asks us to link')
        self.debug('setting up eaters')
        self._setup_eaters(eatersData)

        self.debug('setting up feeders')
        self._setup_feeders(feedersData)
        
        # call a child's link_setup() method if it has it
        func = getattr(self, 'link_setup', None)
        if func:
            self.debug('calling function %r' % func)
            func(eatersData, feedersData)
            
        self.debug('setting pipeline to playing')

        if self.clock_provider:
            self.clock_provider.set_property('active', True)
        self.pipeline.set_state(gst.STATE_PLAYING)

        # attach one-time buffer-probe callbacks for each eater
        for eaterName in self.get_eater_names():
            self.debug('adding buffer probe for eater %s' % eaterName)
            name = "eater:%s" % eaterName
            eater = self.get_element(name)
            # FIXME: should probably raise
            if not eater:
                self.warning('No element named %s in pipeline' % name)
                continue
            pad = eater.get_pad("src")
            self._probe_ids[name] = pad.add_buffer_probe(self._buffer_probe_cb,
                name)

    def _buffer_probe_cb(self, pad, buffer, name):
        # log info about first incoming buffer, then remove ourselves
        self.debug('first buffer probe on eater %s has timestamp %.3f' % (
            name, float(buffer.timestamp) / gst.SECOND))
        if self._probe_ids[name]:
            pad.remove_buffer_probe(self._probe_ids[name])
            self._probe_ids[name] = None
        return True
        
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
    
compat.type_register(FeedComponent)
