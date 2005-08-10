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

from flumotion.component import feedcomponent, component as basecomponent
from flumotion.common import common, interfaces, errors, log
from twisted.internet import reactor, defer
from flumotion.common.planet import moods

class Vorbis(feedcomponent.FeedComponent):
    def __init__(self, name, eaters, bitrate, quality, numChannels):
    	"""
        @param name:        name of the component
        @param eaters:      entry between <source>...</source> from config
        @param feeders:     entry between <feed>...</feed> from config
        @param bitrate:     bitrate of the vorbis stream (-1 if quality is used)
        @param quality:     quality of the vorbis stream (used if bitrate=-1)
        @param numChannels: number of channels of output stream
        """
        self._numChannels = numChannels
        self._bitrate = bitrate
        self._quality = quality
        feedcomponent.FeedComponent.__init__(self, name, eaters, ['default'])
    
    ### FeedComponent methods
    def setup_pipeline(self):
        # create the initial pipeline; called during __init__
        # is responsible for creating self.pipeline
        eater_names = self.get_eater_names()
        if not eater_names:
            raise TypeError, "Need an eater"
        
        # we expand the pipeline based on the templates and eater/feeder names
        # elements are named eater:(source_component_name):(feed_name)
        # or feeder:(component_name):(feed_name)
        eater_element_names = map(lambda n: "eater:" + n, eater_names)
        feeder_element_names = map(lambda n: "feeder:" + n, self.feeder_names)
        self.debug('we eat with eater elements %s' % eater_element_names)
        self.debug('we feed with feeder elements %s' % feeder_element_names)

        # We should only have one eater and one feeder
        # create element's eater ! audioscale
        # the rest we create once we have the caps

        self.pipeline = gst.Pipeline(self.name)
        # FIXME: when our eaters become more than one element, this will
        # parse into a pipeline instead, so at that point we need bins
        # and search for unconnected pads to use
        eater_element = gst.parse_launch(
            self.EATER_TMPL % {'name': eater_element_names[0]})

        wc_element = gst.element_factory_make("audioconvert", "widthconvert")
        as_element = gst.element_factory_make("audioscale", "audioscale")
        fake_element = gst.element_factory_make("fakesink", "fakesink")
        fake_element.set_property("silent", 1)

        self.pipeline.add_many(eater_element, wc_element, as_element,
            fake_element)
        eater_element.link(wc_element)
        wc_element.link(as_element)
        as_element.link(fake_element)
        
        # connect to notify::caps
        self.debug("Adding notify::caps handler to audioscale's sink pad")
        as_pad = as_element.get_pad('sink')

        self.have_caps_handler = as_pad.connect_after('notify::caps', 
            self.have_caps)

        feedcomponent.FeedComponent.setup_pipeline(self)

    ### BaseComponent methods
    def start(self, eatersData, feedersData):
        """
        Tell the component to start, linking itself to other components.

        @type eatersData: list of (feedername, host, port) tuples of elements
                          feeding our eaters.
        @type feedersData: list of (name, host) tuples of our feeding elements

        @returns: a deferred
        """
        self.debug('start with eaters data %s and feeders data %s' % (
            eatersData, feedersData))
        self._start_deferred = defer.Deferred()
        self.setMood(moods.waking)
        self.feedersData = feedersData
        
        # we'll first start eating, so we can figure out caps from the incoming
        # stream and make decisions before starting to feed
        if not self._start_eaters(eatersData):
            return None

        # chain to parent 
        basecomponent.BaseComponent.start(self)
        
        return self._start_deferred
    
    # start eaters
    def _start_eaters(self, eatersData):
        """
        Make the component eat from the feeds it depends on and NOT start
        producing feeds itself.

        @param eatersData: list of (feederName, host, port) tuples to eat from

        @returns: whether the eaters got started succesfully
        """
        # if we have eaters waiting, we start out hungry, else waking
        if self.eatersWaiting:
            self.setMood(moods.hungry)
        else:
            self.setMood(moods.waking)

        self.debug('setting up eaters')
        self._setup_eaters(eatersData)

        self.debug('setting pipeline to play')
        return self.pipeline_play()
    
    def _start_feeders(self, feedersData):
        """
        Make the component start producing feeds

        @params feedersData: list of (feederName, host) tuples to feed to
        """
        # FIXME: _setup_feeders is a FeedComponent method, clean up
        retval = self._setup_feeders(feedersData)
        # pipeline is in paused state when in this function
        self.pipeline_play()
        self.emit('notify-feed-ports')
        self.debug('_start_feeders() returning %s' % retval)

        return retval
        
    def have_caps(self, arg1, arg2):
        as = self.pipeline.get_by_name('audioscale')
        as_pad = as.get_pad('sink')
        caps = as_pad.get_negotiated_caps()
        if caps == None:
            self.debug('have_caps called but caps not negotiated yet')
            return
        self.debug('have_caps called')
        caps_struct = caps.get_structure(0)
        samplerate = caps_struct.get_int('rate')
        width = caps_struct.get_int('width')
        
        self.debug('sample rate %d Hz, width %d' % (samplerate, width))
        as_pad.disconnect(self.have_caps_handler)
        # need to defer because shouldnt modify pipeline in signal
        # handler
        reactor.callLater(0, self._create_rest_pipeline, samplerate, width)
    
    def _create_rest_pipeline(self, samplerate, width):
        # Now need to create rest of pipeline as incoming caps is known
        self.pause()
        audioscale = self.pipeline.get_by_name("audioscale")
        audioconvert = gst.element_factory_make("audioconvert", "audioconvert")
        fakesink = self.pipeline.get_by_name("fakesink")
        enc = gst.element_factory_make("rawvorbisenc", "enc")
        if self._bitrate > -1:
            enc.set_property('bitrate', self._bitrate)
        else:
            enc.set_property('quality', self._quality)
        
        # create feeder
        feeder_element_names = map(lambda n: "feeder:" + n, self.feeder_names)
        feeder = gst.parse_launch(
            self.FEEDER_TMPL % {'name': feeder_element_names[0]})

        self.pipeline.add_many(audioconvert, enc, feeder)
        audioscale.unlink(fakesink)
        self.pipeline.remove(fakesink)
        
        # now do necessary filtercaps
        if self._bitrate > -1:
            maxsamplerate = self._get_max_sample_rate(self._bitrate, 
                                                      self._numChannels)
            if samplerate > maxsamplerate:
                self.debug(
                    'rate %d > max rate %d (for %d kbit/sec), clamping' % (
                        samplerate, maxsamplerate, self._bitrate))
                samplerate = maxsamplerate

        # link audio scale filtered with this rate because of gst caps
        # nego problems
        audioscale.link_filtered(audioconvert, gst.caps_from_string(
            'audio/x-raw-int, rate=%d' % (samplerate)))

        # link audioconvert to rawvorbisenc with the number of channels
        # from config
        audioconvert.link_filtered(enc, gst.caps_from_string(
            'audio/x-raw-float, channels=%d' % (self._numChannels)))

        enc.link(feeder)

        retval = self._start_feeders(self.feedersData)
        
        self.pipeline_play()
        self.debug('emitting feed port notify')
        self.emit('notify-feed-ports')

        self._start_deferred.callback(retval)

    def _get_max_sample_rate(self, bitrate, channels):
        # maybe better in a hashtable/associative array?
        # ZAHEER: these really are "magic" limits that i found by trial and
        # error used
        # by libvorbis's encoder to determine what maximum samplerate it
        # accepts for a bitrate, numchannels combo
        # THOMAS: strangely enough they don't seem to be easily extractable from
        # vorbis/lib/modes/setup_*.h
        # might make sense to figure this out once and for all and verify
        # GStreamer's behaviour as well
        if channels == 2:
            if bitrate >= 45000:
                retval = 50000
            elif bitrate >= 40000:
                retval = 40000
            elif bitrate >= 30000:
                retval = 26000
            elif bitrate >= 24000:
                retval = 19000
            elif bitrate >= 16000:
                retval = 15000
            elif bitrate >= 12000:
                retval = 9000
            else:
                retval = -1
            
        elif channels == 1:
            if bitrate >= 32000:
                retval = 50000
            elif bitrate >= 24000:
                retval = 40000
            elif bitrate >= 16000:
                retval = 26000
            elif bitrate >= 12000:
                retval = 15000
            elif bitrate >= 8000:
                retval = 9000
            else:
                retval = -1
        
        return retval

def createComponent(config):
    channels = config.get('channels', 2)
    bitrate = config.get('bitrate', -1)
    quality = config.get('quality', 0.3)
            
    component = Vorbis(config['name'], [config['source']], bitrate,
                    quality, channels)
              
    return component
