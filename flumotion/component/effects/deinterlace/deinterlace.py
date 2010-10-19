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

import gst
import gobject
from twisted.internet import reactor

from flumotion.component import feedcomponent

__version__ = "$Rev$"

GST_DEINTERLACER = "deinterlace"
FF_DEINTERLACER = "ffdeinterlace"
PASSTHROUGH_DEINTERLACER = "identity"

DEINTERLACE_MODE = [
    "auto",
    "interlaced",
    "disabled"]

DEINTERLACE_METHOD = {
    # deinterlace2 methods
    "tomsmocomp": GST_DEINTERLACER,
    "greedyh": GST_DEINTERLACER,
    "greedyl": GST_DEINTERLACER,
    "vfir": GST_DEINTERLACER,
    "linear": GST_DEINTERLACER,
    "linearblend": GST_DEINTERLACER,
    "scalerbob": GST_DEINTERLACER,
    "weave": GST_DEINTERLACER,
    "weavetff": GST_DEINTERLACER,
    "weavebff": GST_DEINTERLACER,
    # ffmpeg methods
    "ffmpeg": FF_DEINTERLACER}


class DeinterlaceBin(gst.Bin):
    """
    I am a GStreamer bin that can deinterlace a video stream from its
    source pad using different methods.
    """
    logCategory = "deinterlace"
    DEFAULT_MODE = 'auto'
    DEFAULT_METHOD = 'ffmpeg'

    __gproperties__ = {
        'keep-framerate': (gobject.TYPE_BOOLEAN, 'keeps the input framerate',
            'keeps in the output the same framerate as in the output '
            'even if the deinterlacer changes it',
            True, gobject.PARAM_READWRITE),
        'mode': (gobject.TYPE_STRING, 'deinterlace mode',
            'mode used to deinterlace incoming frames',
            'auto', gobject.PARAM_READWRITE),
        'method': (gobject.TYPE_STRING, 'deinterlace method',
            'method/algorithm used to deinterlace incoming frames',
            'ffmpeg', gobject.PARAM_READWRITE)}

    def __init__(self, mode, method):
        gst.Bin.__init__(self)

        self.keepFR = True
        self.deinterlacerName = PASSTHROUGH_DEINTERLACER
        self._interlaced = False

        # Create elements
        self._colorspace = gst.element_factory_make("ffmpegcolorspace")
        self._colorfilter = gst.element_factory_make("capsfilter")
        self._deinterlacer = gst.element_factory_make(PASSTHROUGH_DEINTERLACER)
        self._videorate = gst.element_factory_make("videorate")
        self._ratefilter = gst.element_factory_make("capsfilter")

        # Add elements to the bin
        self.add(self._colorspace, self._colorfilter, self._deinterlacer,
            self._videorate, self._ratefilter)

        # FIXME: I420 is the only format support by the ffmpeg deinterlacer.
        # Forcing it simplifies renegotiation issues if the input colorspace
        # is different and the ffmpeg deinterlacer is added after the
        # negotiation happened in a different colorspace. This makes this
        # element not-passthrough.
        self._colorfilter.set_property('caps', gst.Caps(
            'video/x-raw-yuv, format=(fourcc)I420'))

        # Link elements
        self._colorspace.link(self._colorfilter)
        self._colorfilter.link(self._deinterlacer)
        self._deinterlacer.link(self._videorate)
        self._videorate.link(self._ratefilter)

        # Create source and sink pads
        self._sinkPad = gst.GhostPad('sink', self._colorspace.get_pad('sink'))
        self._srcPad = gst.GhostPad('src', self._ratefilter.get_pad('src'))
        self.add_pad(self._sinkPad)
        self.add_pad(self._srcPad)

        # Store deinterlacer's sink and source peer pads
        self._sinkPeerPad = self._colorspace.get_pad('src')
        self._srcPeerPad = self._videorate.get_pad('sink')

        # Add setcaps callback in the sink pad
        self._sinkPad.set_setcaps_function(self._sinkSetCaps)

        # Set the mode and method in the deinterlacer
        self._setMethod(method)
        self._setMode(mode)

    def isPassthrough(self):
        return self.deinterlacerName == PASSTHROUGH_DEINTERLACER

    def _sinkSetCaps(self, pad, caps):
        struct = caps[0]
        # Set in the source pad the same framerate as in the sink pad
        if self.keepFR:
            try:
                framerate = struct['framerate']
            except KeyError:
                framerate = gst.Fraction(25, 1)
            fr = '%s/%s' % (framerate.num, framerate.denom)
            self._ratefilter.set_property('caps', gst.Caps(
                'video/x-raw-yuv, framerate=%s;'
                'video/x-raw-rgb, framerate=%s' % (fr, fr)))
        # Detect if it's an interlaced stream using the 'interlaced' field
        try:
            interlaced = struct['interlaced']
        except KeyError:
            interlaced = False
        if interlaced == self._interlaced:
            return True
        else:
            self.debug("Input is%sinterlaced" %
                (interlaced and " " or " not "))
            self._interlaced = interlaced
        # If we are in 'auto' mode and the interlaced field has changed,
        # switch to the appropiate deinterlacer
        if self.mode == 'auto':
            if self._interlaced == True and self.isPassthrough():
                self._replaceDeinterlacer(self._sinkPeerPad,
                    DEINTERLACE_METHOD[self.method])
            elif self._interlaced == False and not self.isPassthrough():
                self._replaceDeinterlacer(self._sinkPeerPad,
                    PASSTHROUGH_DEINTERLACER)
        return True

    def _replaceDeinterlacer(self, blockPad, deinterlacerName):

        def unlinkAndReplace(Pad, blocked, deinterlacerName):
            oldDeinterlacer = self._deinterlacer
            self._deinterlacer = gst.element_factory_make(deinterlacerName)
            if deinterlacerName == GST_DEINTERLACER:
                self._deinterlacer.set_property("method", self.method)
            self._deinterlacer.set_state(gst.STATE_PLAYING)
            self.add(self._deinterlacer)
            # unlink the sink and source pad of the old deinterlacer
            self._colorfilter.unlink(oldDeinterlacer)
            oldDeinterlacer.unlink(self._videorate)
            # remove the old deinterlacer from the bin
            oldDeinterlacer.set_state(gst.STATE_NULL)
            self.remove(oldDeinterlacer)
            self._colorfilter.link(self._deinterlacer)
            self._deinterlacer.link(self._videorate)
            reactor.callFromThread(self._sinkPeerPad.set_blocked, False)
            self.debug("%s has been replaced succesfully" %
                self.deinterlacerName)
            self.deinterlacerName = deinterlacerName

        # We might be called from the streaming thread
        self.debug("Replacing %s deinterlacer with %s:%s" %
            (self.deinterlacerName, deinterlacerName, self.method))
        reactor.callFromThread(blockPad.set_blocked_async,
            True, unlinkAndReplace, deinterlacerName)

    def _setMode(self, mode):
        if mode not in DEINTERLACE_MODE:
            raise AttributeError('unknown mode %s' % mode)

        self.mode = mode

        # If the new mode is 'disabled' use the passthrough deinterlacer
        if self.mode == 'disabled':
            if not self.isPassthrough():
                self._replaceDeinterlacer(self._sinkPeerPad,
                    PASSTHROUGH_DEINTERLACER)
        # If the new mode is 'interlaced' force deinterlacing by replacing
        # the deinterlacer if it was the passthrough one
        elif self.mode == 'interlaced':
            if self.isPassthrough():
                self._replaceDeinterlacer(self._sinkPeerPad,
                    DEINTERLACE_METHOD[self.method])
        # If the new mode is 'auto' replace the deinterlacer if the old one is
        # passthough and the input content is interlaced
        elif self.mode == 'auto':
            if self._interlaced and self.isPassthrough():
                self._replaceDeinterlacer(self._sinkPeerPad,
                    DEINTERLACE_METHOD[self.method])

    def _setMethod(self, method):
        if method not in DEINTERLACE_METHOD:
            raise AttributeError('unknown mode %s' % method)

        self.method = method
        deinterlacerName = DEINTERLACE_METHOD[method]
        if self.deinterlacerName == deinterlacerName:
            # If the deinterlacer is 'deinterlace2', change
            # the method property in the component
            if self.deinterlacerName == GST_DEINTERLACER \
                and not self._passthrough:
                self.debug("Changed method to %s" % method)
                self._deinterlacer.set_property("method", method)
            return

        if not self.isPassthrough():
            # Replace the deinterlacer
            self._replaceDeinterlacer(self._sinkPeerPad, deinterlacerName)

    def do_set_property(self, property, value):
        if property.name == 'mode':
            if value != self.mode:
                self._setMode(value)
        elif property.name == 'method':
            if value != self.method:
                self._setMethod(value)
        elif property.name == 'keep-framerate':
            self.keepFR = value
        else:
            raise AttributeError('uknown property %s' % property.name)

    def do_get_property(self, property):
        if property.name == 'mode':
            return self.mode
        elif property.name == 'method':
            return self.method
        elif property.name == 'keep-framerate':
            return self.keepFR
        else:
            raise AttributeError('uknown property %s' % property.name)


class Deinterlace(feedcomponent.PostProcEffect):
    """
    I am an effect that can be added to any component that has a deinterlacer
    component and a way of changing the deinterlace method.
    """
    logCategory = "deinterlace"

    def __init__(self, name, sourcePad, pipeline, mode, method):
        """
        @param element:     the video source element on which the post
                            processing effect will be added
        @param pipeline:    the pipeline of the element
        @param mode:        deinterlace mode
        @param methid:      deinterlace method
        """
        feedcomponent.PostProcEffect.__init__(self, name, sourcePad,
            DeinterlaceBin(mode, method), pipeline)

    def setUIState(self, state):
        feedcomponent.Effect.setUIState(self, state)
        if state:
            for k in 'mode', 'method':
                state.addKey('deinterlace-%s' % k,
                    self.effectBin.get_property(k))

    def effect_setMethod(self, method):
        """
        Sets the deinterlacing method

        @param value: the method to set to deinterlace

        @return: the actual method set to deinterlace
        """
        self.effectBin.set_property('method', method)
        self.info('Changing deinterlacing method to %s', method)
        # notify admin clients
        self.uiState.set('deinterlace-method', method)
        return method

    def effect_getMethod(self):
        """
        Gets the deinterlacing method

        @return: the method set for deinterlacing
        @rtype: string
        """
        return self.effectBin.get_property('method')

    def effect_setMode(self, mode):
        """
        Sets the deinterlacing mode

        @param value: the method to set to deinterlace

        @return: the actual method set to deinterlace
        """
        self.effectBin.set_property('mode', mode)
        self.info('Changing deinterlacing mode to %s', mode)
        # notify admin clients
        self.uiState.set('deinterlace-mode', mode)
        return mode

    def effect_getMode(self, mode):
        """
        GetSets the deinterlacing method

        @param value: the method used for deinterlacing

        Returns: the actual method used to deinterlace
        """
        return self.effectBin.get_property('mode')
