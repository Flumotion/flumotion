# -*- Mode: Python -*-
# vi:si:et:sw=4:sts=4:ts=4

# Flumotion - a streaming media server
# Copyright (C) 2004,2005,2006,2007,2008,2009 Fluendo, S.L.
# Copyright (C) 2010,2011 Flumotion Services, S.A.
# All rights reserved.
#
# This file may be distributed and/or modified under the terms of
# the GNU Lesser General Public License version 2.1 as published by
# the Free Software Foundation.
# This file is distributed without any warranty; without even the implied
# warranty of merchantability or fitness for a particular purpose.
# See "LICENSE.LGPL" in the source distribution for more information.
#
# Headers in this file shall remain intact.

import gst
from twisted.internet import defer

from flumotion.common import errors, messages
from flumotion.common.i18n import N_, gettexter
from flumotion.component import feedcomponent
from flumotion.component.effects.deinterlace import deinterlace
from flumotion.component.effects.videorate import videorate
from flumotion.component.effects.videoscale import videoscale
from flumotion.component.effects.audioconvert import audioconvert

__version__ = "$Rev$"
T_ = gettexter()


class AVProducerBase(feedcomponent.ParseLaunchComponent):

    def get_raw_video_element(self):
        raise NotImplementedError("Subclasses must implement "
                                  "'get_raw_video_element'")

    def get_pipeline_template(self):
        raise NotImplementedError("Subclasses must implement "
                                  "'get_pipeline_template'")

    def do_check(self):
        self.debug('running PyGTK/PyGST and configuration checks')
        from flumotion.component.producers import checks
        d1 = checks.checkTicket347()
        d2 = checks.checkTicket348()
        dl = defer.DeferredList([d1, d2])
        dl.addCallback(self._checkCallback)
        return dl

    def check_properties(self, props, addMessage):
        deintMode = props.get('deinterlace-mode', 'auto')
        deintMethod = props.get('deinterlace-method', 'ffmpeg')

        if deintMode not in deinterlace.DEINTERLACE_MODE:
            msg = messages.Error(T_(N_("Configuration error: '%s' " \
                "is not a valid deinterlace mode." % deintMode)))
            addMessage(msg)
            raise errors.ConfigError(msg)

        if deintMethod not in deinterlace.DEINTERLACE_METHOD:
            msg = messages.Error(T_(N_("Configuration error: '%s' " \
                "is not a valid deinterlace method." % deintMethod)))
            self.debug("'%s' is not a valid deinterlace method",
                deintMethod)
            addMessage(msg)
            raise errors.ConfigError(msg)

    def _checkCallback(self, results):
        for (state, result) in results:
            for m in result.messages:
                self.addMessage(m)

    def get_pipeline_string(self, props):
        self.is_square = props.get('is-square', False)
        self.width = props.get('width', None)
        self.height = props.get('height', None)
        self.add_borders = props.get('add-borders', True)
        self.deintMode = props.get('deinterlace-mode', 'auto')
        self.deintMethod = props.get('deinterlace-method', 'ffmpeg')
        fr = props.get('framerate', None)
        self.framerate = fr and gst.Fraction(fr[0], fr[1]) or None
        return self.get_pipeline_template()

    def configure_pipeline(self, pipeline, properties):
        if self.get_raw_video_element() is not None:
            self._add_video_effects(pipeline)
        self._add_audio_effects()

    def getVolume(self):
        return self.volume.get_property('volume')

    def setVolume(self, value):
        """
        @param value: float between 0.0 and 4.0
        """
        self.debug("Setting volume to %f" % (value))
        self.volume.set_property('volume', value)

    def _add_video_effects(self, pipeline):
        # Add deinterlacer
        deinterlacer = deinterlace.Deinterlace('deinterlace',
            self.get_raw_video_element().get_pad("src"), pipeline,
            self.deintMode, self.deintMethod)
        self.addEffect(deinterlacer)
        deinterlacer.plug()

        # Add video rate converter
        rateconverter = videorate.Videorate('videorate',
            deinterlacer.effectBin.get_pad("src"), pipeline,
            self.framerate)
        self.addEffect(rateconverter)
        rateconverter.plug()

        # Add video scaler
        videoscaler = videoscale.Videoscale('videoscale', self,
            rateconverter.effectBin.get_pad("src"), pipeline,
            self.width, self.height, self.is_square, self.add_borders)
        self.addEffect(videoscaler)
        videoscaler.plug()

    def _add_audio_effects(self, pipeline):
        # Add volume setter
        self.volume = pipeline.get_by_name("setvolume")
        from flumotion.component.effects.volume import volume
        comp_level = pipeline.get_by_name('volumelevel')
        vol = volume.Volume('inputVolume', comp_level, pipeline)
        self.addEffect(vol)

        # Add audio converter
        audioconverter = audioconvert.Audioconvert('audioconvert',
            comp_level.get_pad("src"), pipeline, tolerance=40 * gst.MSECOND)
        self.addEffect(audioconverter)
        audioconverter.plug()
