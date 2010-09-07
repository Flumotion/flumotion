# -*- Mode: Python -*-
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

import gobject
import gst

from flumotion.common.i18n import gettexter
from flumotion.component import feedcomponent

__version__ = "$Rev$"
T_ = gettexter()


class AudiorateBin(gst.Bin):
    """
    I am a GStreamer bin that can change the samplerate of an audio stream.
    """
    logCategory = "audiorate"
    CAPS_TEMPLATE = "audio/x-raw-int,rate=%(rate)d;"\
                    "audio/x-raw-float,rate=%(rate)d"

    __gproperties__ = {
        'samplerate': (gobject.TYPE_UINT, 'samplerate',
                       'Audio samplerate', 1, 200000, 44100,
                       gobject.PARAM_READWRITE)}

    def __init__(self, samplerate=44100):
        gst.Bin.__init__(self)
        self._samplerate = samplerate

        self._audioconv = gst.element_factory_make("audioconvert")
        self._audiorate = gst.element_factory_make("legacyresample")
        self._capsfilter = gst.element_factory_make("capsfilter")
        self._identity = gst.element_factory_make("identity")
        self.add(self._audioconv)
        self.add(self._audiorate)
        self.add(self._capsfilter)
        self.add(self._identity)

        self._audioconv.link(self._audiorate)
        self._audiorate.link(self._capsfilter)
        self._capsfilter.link(self._identity)

        # Create source and sink pads
        self._sinkPad = gst.GhostPad('sink', self._audioconv.get_pad('sink'))
        self._srcPad = gst.GhostPad('src', self._identity.get_pad('src'))
        self.add_pad(self._sinkPad)
        self.add_pad(self._srcPad)

        self._setSamplerate(samplerate)

    def _setSamplerate(self, samplerate):
        self._samplerate = samplerate
        self._capsfilter.set_property('caps',
            gst.Caps(self.CAPS_TEMPLATE % dict(rate=samplerate)))

    def do_set_property(self, property, value):
        if property.name == 'samplerate':
            self._setSamplerate(value)
        else:
            raise AttributeError('unknown property %s' % property.name)

    def do_get_property(self, property):
        if property.name == 'samplerate':
            return self._samplerate
        else:
            raise AttributeError('unknown property %s' % property.name)


class Audiorate(feedcomponent.PostProcEffect):
    """
    I am an effect that can be added to any component that changes the
    samplerate of the audio output.
    """
    logCategory = "audiorate-effect"

    def __init__(self, name, sourcePad, pipeline, samplerate):
        """
        @param element:     the video source element on which the post
                            processing effect will be added
        @param sourcePad:   source pad used for linking the effect
        @param pipeline:    the pipeline of the element
        @param samplerate:  output samplerate
        """
        feedcomponent.PostProcEffect.__init__(self, name, sourcePad,
            AudiorateBin(samplerate), pipeline)

    def effect_setSamplerate(self, samplerate):
        self.effectBin.set_property("samplerate", samplerate)
        return samplerate

    def effect_getSamplerate(self):
        return self.effectBin.get_property('samplerate')
