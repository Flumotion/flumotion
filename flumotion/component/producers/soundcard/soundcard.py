# -*- Mode: Python; test-case-name:flumotion.test.test_soundcard -*-
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
import gst.interfaces

from twisted.internet import defer

from flumotion.component import feedcomponent
from flumotion.component.effects.volume import volume

    
class Soundcard(feedcomponent.ParseLaunchComponent):
    def do_check(self):
        self.debug('running PyGTK/PyGST checks')
        from flumotion.component.producers import checks
        d1 = checks.checkTicket347()
        d2 = checks.checkTicket348()
        dl = defer.DeferredList([d1, d2])
        dl.addCallback(self._checkCallback)
        return dl

    def _checkCallback(self, results):
        for (state, result) in results:
            for m in result.messages:
                self.addMessage(m)

    def get_pipeline_string(self, properties):
        element = properties.get('source-element', 'alsasrc')
        device = properties.get('device', 'hw:0')
        rate = properties.get('rate', 44100)
        depth = properties.get('depth', 16)
        channels = properties.get('channels', 2)

        # FIXME: why do we not connect to state_changed_cb so correct
        # soundcard input is used?
        
        # FIXME: we should find a way to figure out what the card supports,
        # so we can add in correct elements on the fly
        # just adding audioscale and audioconvert always makes the soundcard
        # open in 1000 Hz, mono
        caps = 'audio/x-raw-int,rate=(int)%d,depth=%d,channels=%d' % (
            rate, depth, channels)
        pipeline = '%s device=%s ! %s ! level name=volumelevel message=true' % (
            element, device, caps)

        return pipeline

    def configure_pipeline(self, pipeline, properties):
        # add volume effect
        comp_level = pipeline.get_by_name('volumelevel')
        vol = volume.Volume('inputVolume', comp_level, pipeline)
        self.addEffect(vol)

    def state_changed_cb(self, element, old, new, trackLabel):
        if old == gst.STATE_NULL and new == gst.STATE_READY:
            for track in element.list_tracks():
                element.set_record(track, track.label == trackLabel)

    def setVolume(self, value):
        self.debug("Volume set to: %d" % (value))
        self.warning("FIXME: soundcard.setVolume not implemented yet")

    def getVolume(self):
        self.warning("FIXME: soundcard.getVolume not implemented yet")
        return 1.0
