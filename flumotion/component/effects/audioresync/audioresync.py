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


class AudioResyncer(gst.Element):
    '''
    I retimestamp incomming buffers adding a fixed delay.
    '''

    __gproperties__ = {
        'delay': (float, 'delay (in ms)',
            'Resynchronisation delay in milliseconds',
            -1000000, 1000000, 0,
            gobject.PARAM_READWRITE)}

    _sinkpadtemplate = gst.PadTemplate("sink",
                                        gst.PAD_SINK,
                                        gst.PAD_ALWAYS,
                                        gst.caps_from_string(
                                            "audio/x-raw-float;"
                                            "audio/x-raw-int"))

    _srcpadtemplate = gst.PadTemplate("src",
                                        gst.PAD_SRC,
                                        gst.PAD_ALWAYS,
                                        gst.caps_from_string(
                                            "audio/x-raw-float;"
                                            "audio/x-raw-int"))

    def __init__(self, delay=0):
        gst.Element.__init__(self)

        self.sinkpad = gst.Pad(self._sinkpadtemplate, "sink")
        self.sinkpad.set_chain_function(self.chainfunc)
        self.add_pad(self.sinkpad)

        self.srcpad = gst.Pad(self._srcpadtemplate, "src")
        self.add_pad(self.srcpad)

        self._delay = long(delay * gst.MSECOND)
        print self._delay

    def do_get_property(self, property):
        if property.name == "delay":
            return self._delay
        else:
            raise AttributeError('unknown property %s' % property.name)

    def do_set_property(self, property, value):
        if property.name == "delay":
            self._delay = long(value * gst.MSECOND)
        else:
            raise AttributeError('unknown property %s' % property.name)

    def chainfunc(self, pad, buffer):
        if self._delay != 0:
            buffer.make_metadata_writable
            buffer.timestamp = buffer.timestamp + self._delay
        self.srcpad.push(buffer)
        return gst.FLOW_OK


class Audioresync(feedcomponent.PostProcEffect):
    """
    Post processing audio effect to increase/decrease the audio delay an
    synchronise it on the fly with the video stream.
    """
    logCategory = "audioresync-effect"

    def __init__(self, name, sourcePad, pipeline, delay):
        """
        @param element:     the video source element on which the post
                            processing effect will be added
        @param sourcePad:   source pad used for linking the effect
        @param pipeline:    the pipeline of the element
        @param delay:       audio delay added
        """
        feedcomponent.PostProcEffect.__init__(self, name, sourcePad,
            AudioResyncer(delay), pipeline)

    def setUIState(self, state):
        feedcomponent.Effect.setUIState(self, state)
        if state:
            state.addKey('audioresync-delay',
                self.effectBin.get_property('delay'))

    def effect_setDelay(self, delay):
        self.effectBin.set_property("delay", delay)
        return delay

    def effect_getDelay(self):
        return self.effectBin.get_property('delay')
