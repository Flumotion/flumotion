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
    FEEDER_TMPL = 'tcpserversink name=%(name)s buffers-max=500 buffers-soft-max=450 recover-policy=1'

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
        self.files = []
        self.effects = {}

        self.feed_names = None # done by self.parse*
        self.feeder_names = None

        self.eater_names = [] # componentName:feedName list
        self._eaterReconnectDC = {} 

        self.feedersFeeding = 0
        self.feed_names = []
        self.feeder_names = []

    def do_setup(self):
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
        raise NotImplementedError, "subclass must implement create_pipeline"
        
    def set_pipeline(self, pipeline):
        self.pipeline = pipeline
        self.setup_pipeline()
  
    ### FeedComponent methods
    def updateMood(self):
        """
        Update the mood because a mood condition has changed.
        Will not change the mood if it's sad - sad needs to be explicitly
        fixed.

        See the mood transition diagram.
        """
        mood = self.state.get('mood')
        self.debug('updateMood: currently in %r' % moods.get(mood).name)
        if mood == moods.sad.value:
            self.debug('updateMood: sad, not changing')
            return

        if self.eatersWaiting == 0 and self.feedersWaiting == 0:
            self.debug('no eaters or feeders waiting, happy')
            self.setMood(moods.happy)
            return

        if self.eatersWaiting == 0:
            self.debug('%d feeders waiting, waking' % self.feedersWaiting)
            self.setMood(moods.waking)
        else:
            self.debug('%d eaters waiting, hungry' % self.eatersWaiting)
            self.setMood(moods.hungry)
        return

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
        """
        return self.eater_names
    
    def get_feeder_names(self):
        """
        Return the list of feeder names this component has.
        """
        return self.feeder_names

    def get_feed_names(self):
        """
        Return the list of feeder names this component has.
        """
        return self.feed_names

    def restart(self):
        self.debug('restarting')
        self.cleanup()
        self.setup_pipeline()
       
    def set_state_and_iterate(self, state):
        """
        Set the given gst state and start iterating the pipeline if not done
        yet.
        """
        retval = self.pipeline.set_state(state)
        if not retval:
            self.warning('Changing state to %s failed' %
                    gst.element_state_get_name(state))
        # the idle handler will go away as soon as iterate returns FALSE
        gobject.idle_add(self.pipeline.iterate)

        return retval

    def get_pipeline(self):
        return self.pipeline

       
    def _pipeline_error_cb(self, object, element, error, arg):
        self.debug('element %s error %s %s' % (element.get_path_string(), str(error), repr(arg)))
        self.setMood(moods.sad)
        self.state.set('message',
            "GStreamer error in component %s (%s)" % (self.name, error.message))
        self.emit('error', element.get_path_string(), error.message)
        #self.restart()
     
    def setup_pipeline(self):
        self.pipeline.set_name('pipeline-' + self.getName())
        sig_id = self.pipeline.connect('error', self._pipeline_error_cb)
        self.pipeline_signals.append(sig_id)
        
        sig_id = self.pipeline.connect('deep-notify',
                                       gstreamer.verbose_deep_notify_cb, self)
        self.pipeline_signals.append(sig_id)

    def pipeline_pause(self):
        self.set_state_and_iterate(gst.STATE_PAUSED)
        
    def pipeline_play(self):
        """
        Start playing the pipeline.

        @returns: whether or not the pipeline was started successfully.
        """
        retval = self.set_state_and_iterate(gst.STATE_PLAYING)
        if not retval:
            self.setMood(moods.sad)
            self.state.set('message',
                "Component %s could not start" % self.name)
            return False

        return True

    def pipeline_stop(self):
        if not self.pipeline:
            return
        
        retval = self.set_state_and_iterate(gst.STATE_NULL)
        if not retval:
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
            eater.connect('state-change', self.eater_state_change_cb)

    def eater_state_change_cb(self, element, old, state):
        """
        Called when the eater element changes state.
        """
        # also called by subclasses
        name = element.get_name()
        self.debug('eater-state-changed: eater %s, element %s, state %s' % (
            name,
            element.get_path_string(),
            gst.element_state_get_name(state)))

        # update eatersWaiting count
        if old == gst.STATE_PAUSED and state == gst.STATE_PLAYING:
            self.debug('eater %s is now eating' % name)
            self.eatersWaiting -= 1
            self.updateMood()
            if self._eaterReconnectDC[name]:
                self._eaterReconnectDC[name].cancel()
                self._eaterReconnectDC[name] = None
                
        if old == gst.STATE_PLAYING and state == gst.STATE_PAUSED:
            self.debug('eater %s is now hungry' % name)
            self.eatersWaiting += 1
            self.state.set('message',
                "Component %s is now hungry, starting reconnect" % self.name)
            self.updateMood()
            self._eaterReconnectDC[name] = reactor.callLater(
                self._reconnectInterval, self._eaterReconnect, element)
            
        self.debug('%d eaters waiting' % self.eatersWaiting)

    def _eaterReconnect(self, element):
        name = element.get_name()
        self.debug('Trying to reconnect eater %s' % name)
        host = element.get_property('host')
        port = element.get_property('port')
        if common.checkRemotePort(host, port):
            self.debug('%s:%d accepting connections, setting to PLAYING' % (
                host, port))
            self._eaterReconnectDC[name] = None
            # currently, we need to make sure all other elements go to PLAYING
            # as well, so we PAUSE then PLAY the complete pipeline
            #element.set_state(gst.STATE_PLAYING)
            self.debug('pausing and iterating')
            self.pipeline_pause()
            self.debug('playing and iterating')
            self.pipeline_play()
            self.debug('reconnected')
        else:
            self.debug('%s:%d not accepting connections, trying later' % (
                host, port))
            self._eaterReconnectDC[name] = reactor.callLater(
                self._reconnectInterval, self._eaterReconnect, element)
            
    # FIXME: vorbis.py calls this method, clean that up
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

        for feeder_name, host, port in feedersData:
            feed_name = feeder_name.split(':')[1]
            self.debug('Going to listen on feeder %s (%s:%d)' % (
                feeder_name, host, port))
            name = 'feeder:' + feeder_name
            feeder = self.get_element(name)
            assert feeder, 'No feeder element named %s in pipeline' % name
            assert isinstance(feeder, gst.Element)

            feeder.connect('state-change', self.feeder_state_change_cb, feed_name)
            feeder.set_property('host', host)
            feeder.set_property('port', port)
            feeder.set_property('protocol', 'gdp')

    def feeder_state_change_cb(self, element, old, state, feed_name):
        # also called by subclasses
        self.debug('feed %s changed state: element %s, state %s' % (
            feed_name, element.get_path_string(),
            gst.element_state_get_name(state)))

        # update feedersWaiting count
        if old == gst.STATE_PAUSED and state == gst.STATE_PLAYING:
            self.debug('feeder %s is now feeding' % element.get_name())
            self.feedersWaiting -= 1
            self.updateMood()
            self.emit('feed-ready', feed_name, True)
        if old == gst.STATE_PLAYING and state == gst.STATE_PAUSED:
            self.debug('feeder %s is now waiting' % element.get_name())
            self.feedersWaiting += 1
            self.updateMood()
            self.emit('feed-ready', feed_name, False)

        self.debug('%d feeders waiting' % self.feedersWaiting)

    def cleanup(self):
        self.debug("cleaning up")
        
        assert self.pipeline != None

        if self.pipeline.get_state() != gst.STATE_NULL:
            self.debug('Pipeline was in state %s, changing to NULL' %
                     gst.element_state_get_name(self.pipeline.get_state()))
            self.pipeline.set_state(gst.STATE_NULL)
                
        # Disconnect signals
        map(self.pipeline.disconnect, self.pipeline_signals)
        self.pipeline = None
        self.pipeline_signals = []

    def play(self):
        self.debug('Playing')
        self.pipeline_play()

    def stop(self):
        self.debug('Stopping')
        self.pipeline_stop()
        self.debug('Stopped')
        basecomponent.BaseComponent.stop(self)

    def pause(self):
        self.debug('Pausing')
        self.pipeline_pause()
                
    def set_master_clock(self, ip, port, base_time):
        self.info('Told to slave clock to master, but GStreamer 0.8 does '
                  'not support master/slave clocking. Ignoring request.')
        return

    def provide_master_clock(self, port):
        self.info('Told to provide master clock, but GStreamer 0.8 does '
                  'not support master/slave clocking. Ignoring request.')
        return None

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
        if self.eatersWaiting:
            self.setMood(moods.hungry)
        else:
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
        self.pipeline_play()

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
