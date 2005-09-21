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

import os

import gst

from twisted.internet import defer

from flumotion.configure import configure
from flumotion.component import component, feedcomponent
from flumotion.common.planet import moods

class Jukebox(feedcomponent.FeedComponent):
    def __init__(self, config):
        name = config.get('name')
        self._rate = config.get('rate', 44100)
        self._channels = config.get('channels', 2)
        self._playlist = config.get('playlist')
        self._random = config.get('random', True)
        self._loops = config.get('loops', -1)
        feedcomponent.FeedComponent.__init__(self, name,
                                                    [],
                                                    ['default'])

    def setup_pipeline(self):
        try:
            from gst.extend import jukebox
        except ImportError:
            self.error('This component needs at least gst-python 0.8.3')

        self.pipeline = gst.Pipeline(self.name)
        picklepath = os.path.join(configure.cachedir, 'jukebox.pck')
        
        if not os.path.exists(self._playlist):
            self.error("Could not load playlist %s" % self._playlist)
            
        self.debug('reading playlist from %s' % self._playlist)
        list = open(self._playlist).read().rstrip().split('\n')
        self._jukebox = jukebox.Jukebox(list, 
            random=self._random, loops=self._loops,
            picklepath=picklepath)
        self.pipeline.add(self._jukebox)
        feedcomponent.FeedComponent.setup_pipeline(self)

    def start(self, eatersData, feedersData):
        self.debug('Jukebox.start')
        self._start_deferred = defer.Deferred()
        self.setMood(moods.waking)

        # set up the jukebox for prerolling
        self._jukebox.connect('prerolled', self._jukebox_prerolled_cb,
            feedersData)
        self._jukebox.connect('done', self._jukebox_done_cb)
        self.debug('prerolling jukebox')
        self._jukebox.preroll()

        component.BaseComponent.start(self)

        return self._start_deferred

    def _jukebox_prerolled_cb(self, jukebox, feedersData):
        self.debug("prerolled jukebox, starting")
        self._identity = gst.element_factory_make('identity')
        self._identity.set_property('sync', True)
        self._identity.set_property('silent', True)
        # create feeder
        feeder_element_names = map(lambda n: "feeder:" + n, self.feeder_names)
        feeder = gst.parse_launch(
            self.FEEDER_TMPL % {'name': feeder_element_names[0]})
        self.debug('created feeder with element name %s' %
            feeder_element_names[0])

        self.pipeline.add_many(self._identity, feeder)
        self._jukebox.link(self._identity,
            gst.caps_from_string(
                "audio/x-raw-int,channels=%d,rate=%d,width=16,depth=16" % (
                    self._channels, self._rate))
        )
        self._identity.link(feeder)
        
        self.debug("telling jukebox to start")
        self._jukebox.start()
        self.debug("told jukebox to start, setup feeders")

        retval = self._setup_feeders(feedersData)
        self.debug('setting pipeline to play')
        ret = self.pipeline_play()
        self.debug('pipeline_play() returned %r' % ret)

        self.debug('firing start callback with result %r' % retval)
        self._start_deferred.callback(retval)

    def _jukebox_done_cb(self, source, reason):
        print "Done"
        if reason != "EOS":
            self.warning("Some jukebox error happened: %s" % reason)
            self.setMood(moods.sad)

    def _error_cb(self, source, element, gerror, message):
        self.error("Some jukebox error happened: %r" % gerror)
        self.setMood(moods.sad)

def createComponent(config):
    component = Jukebox(config)
    return component
