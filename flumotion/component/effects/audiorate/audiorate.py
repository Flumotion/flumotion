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

import sys

import gobject
import gst

from flumotion.common.i18n import gettexter
from flumotion.component import feedcomponent
from flumotion.common import gstreamer

__version__ = "$Rev$"
T_ = gettexter()

DEFAULT_TOLERANCE = 20000000 # 20ms


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
                       gobject.PARAM_READWRITE),
        'tolerance': (gobject.TYPE_UINT, 'tolerance',
                       'Correct imperfect timestamps when it exeeds the '
                       'tolerance', 0, sys.maxint, DEFAULT_TOLERANCE,
                       gobject.PARAM_READWRITE)}

    def __init__(self, samplerate=44100, tolerance=DEFAULT_TOLERANCE):
        gst.Bin.__init__(self)
        self._samplerate = samplerate

        self._audiorate = gst.element_factory_make("audiorate")
        self._audioconv = gst.element_factory_make("audioconvert")
        self._audioresample = gst.element_factory_make("legacyresample")
        self._capsfilter = gst.element_factory_make("capsfilter")
        self._identity = gst.parse_launch("identity silent=true")
        self.add(self._audiorate)
        self.add(self._audioconv)
        self.add(self._audioresample)
        self.add(self._capsfilter)
        self.add(self._identity)

        self._audiorate.link(self._audioconv)
        self._audioconv.link(self._audioresample)
        self._audioresample.link(self._capsfilter)
        self._capsfilter.link(self._identity)

        # Create source and sink pads
        self._sinkPad = gst.GhostPad('sink', self._audiorate.get_pad('sink'))
        self._srcPad = gst.GhostPad('src', self._identity.get_pad('src'))
        self.add_pad(self._sinkPad)
        self.add_pad(self._srcPad)

        self._setSamplerate(samplerate)
        self._setTolerance(tolerance)

    def _setSamplerate(self, samplerate):
        self._samplerate = samplerate
        self._capsfilter.set_property('caps',
            gst.Caps(self.CAPS_TEMPLATE % dict(rate=samplerate)))

    def _setTolerance(self, tolerance):
        self._tolerance = tolerance
        if gstreamer.element_has_property(self._audiorate, 'tolerance'):
            self._audiorate.set_property('tolerance', self._tolerance)
        else:
            self.warning("The 'tolerance' property could not be set in the "
                        "audiorate element.")

    def do_set_property(self, property, value):
        if property.name == 'samplerate':
            self._setSamplerate(value)
        if property.name == 'tolerance':
            self._setTolerance(value)
        else:
            raise AttributeError('unknown property %s' % property.name)

    def do_get_property(self, property):
        if property.name == 'samplerate':
            return self._samplerate
        if property.name == 'tolerance':
            return self._tolerance
        else:
            raise AttributeError('unknown property %s' % property.name)


class Audiorate(feedcomponent.PostProcEffect):
    """
    I am an effect that can be added to any component that changes the
    samplerate of the audio output.
    """
    logCategory = "audiorate-effect"

    def __init__(self, name, sourcePad, pipeline, samplerate,
            tolerance=DEFAULT_TOLERANCE):
        """
        @param element:     the video source element on which the post
                            processing effect will be added
        @param sourcePad:   source pad used for linking the effect
        @param pipeline:    the pipeline of the element
        @param samplerate:  output samplerate
        @param tolerance:   tolerance to correct imperfect timestamps
        """
        feedcomponent.PostProcEffect.__init__(self, name, sourcePad,
            AudiorateBin(samplerate, tolerance), pipeline)

    def effect_setTolerance(self, tolerance):
        self.effectBin.set_property("tolerance", tolerance)
        return tolerance

    def effect_getTolerance(self):
        return self.effectBin.get_property('tolerance')

    def effect_setSamplerate(self, samplerate):
        self.effectBin.set_property("samplerate", samplerate)
        return samplerate

    def effect_getSamplerate(self):
        return self.effectBin.get_property('samplerate')
