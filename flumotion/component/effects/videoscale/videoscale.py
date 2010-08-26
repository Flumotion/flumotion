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

from twisted.internet import reactor
import gobject
import gst

from flumotion.common import errors, messages, gstreamer
from flumotion.common.i18n import N_, gettexter
from flumotion.component import feedcomponent
from flumotion.component.producers.playlist import smartscale

__version__ = "$Rev$"
T_ = gettexter()


class VideoscaleBin(gst.Bin):
    """
    I am a GStreamer bin that can scale a video stream from its source pad.
    """
    logCategory = "videoscale"

    __gproperties__ = {
        'width': (gobject.TYPE_UINT, 'width',
            'Output width',
            1, 10000, 100, gobject.PARAM_READWRITE),
        'height': (gobject.TYPE_UINT, 'height',
            'Output height',
            1, 10000, 100, gobject.PARAM_READWRITE),
        'is-square': (gobject.TYPE_BOOLEAN, 'PAR 1/1',
            'Output with PAR 1/1',
            False, gobject.PARAM_READWRITE),
        'add-borders': (gobject.TYPE_BOOLEAN, 'Add borders',
            'Add black borders to keep DAR if needed',
            False, gobject.PARAM_READWRITE)}

    def __init__(self, width, height, is_square, add_borders):
        gst.Bin.__init__(self)
        self._width = width
        self._height = height
        self._is_square = is_square
        self._add_borders = add_borders

        self._inpar = None # will be set when active
        self._inwidth = None
        self._inheight = None

        self._videoscaler = gst.element_factory_make("videoscale")
        self._capsfilter = gst.element_factory_make("capsfilter")
        self._videobox = gst.element_factory_make("videobox")
        self.add(self._videoscaler, self._capsfilter, self._videobox)

        self._videoscaler.link(self._capsfilter)
        self._capsfilter.link(self._videobox)

        # Create source and sink pads
        self._sinkPad = gst.GhostPad('sink', self._videoscaler.get_pad('sink'))
        self._srcPad = gst.GhostPad('src', self._videobox.get_pad('src'))
        self.add_pad(self._sinkPad)
        self.add_pad(self._srcPad)

        self._configureOutput()

        # Add setcaps callback in the sink pad
        self._sinkPad.set_setcaps_function(self._sinkSetCaps)
        # Add a callback for caps changes in the videoscaler source pad
        # to recalculate the scale correction
        self._videoscaler.get_pad('src').connect(
            'notify::caps', self._scaleCorrectionCallback)

    def _updateFilter(self, blockPad):

        def unlinkAndReplace(pad, blocked):
            self._videoscaler.set_state(gst.STATE_NULL)
            self._capsfilter.set_state(gst.STATE_NULL)
            self._videobox.set_state(gst.STATE_NULL)

            self._configureOutput()

            self._videobox.set_state(gst.STATE_PLAYING)
            self._videoscaler.set_state(gst.STATE_PLAYING)
            self._capsfilter.set_state(gst.STATE_PLAYING)

            # unlink the sink and source pad of the old deinterlacer
            reactor.callFromThread(blockPad.set_blocked, False)

        event = gst.event_new_custom(gst.EVENT_CUSTOM_DOWNSTREAM,
            gst.Structure('flumotion-reset'))
        self._sinkPad.send_event(event)

        # We might be called from the streaming thread
        self.info("Replaced capsfilter")
        reactor.callFromThread(blockPad.set_blocked_async,
            True, unlinkAndReplace)

    def _scaleCorrectionCallback(self, pad, param):
        # the point of width correction is to get to a multiple of 8 for width
        # so codecs are happy; it's unrelated to the aspect ratio correction
        # to get to 4:3 or 16:9
        c = pad.get_negotiated_caps()
        if c is not None:
            width = c[0]['width']
            scale_correction = width % 8
            if scale_correction and self._width:
                self.info('"width" given, but output is not a multiple of 8!')
                return
            self._videobox.set_property("right", -scale_correction)

    def _configureOutput(self):
        p = ""
        if self._is_square:
            p = ",pixel-aspect-ratio=(fraction)1/1"
        if self._width:
            p = "%s,width=(int)%d" % (p, self._width)
        if self._height:
            p = "%s,height=(int)%d" % (p, self._height)
        p = "video/x-raw-yuv%s;video/x-raw-rgb%s" % (p, p)
        self.info("out:%s" % p)
        caps = gst.Caps(p)

        self._capsfilter.set_property("caps", caps)
        if gstreamer.element_has_property(self._videoscaler, 'add-borders'):
            self._videoscaler.set_property('add-borders', self._add_borders)

    def _sinkSetCaps(self, pad, caps):
        self.info("in:%s" % caps.to_string())
        if not caps.is_fixed():
            return
        struc = caps[0]
        if struc.has_field('pixel-aspect-ratio'):
            self._inpar = struc['pixel-aspect-ratio']
        self._inwidth = struc['width']
        self._inheight = struc['height']
        return True

    def do_set_property(self, property, value):
        if property.name == 'width':
            self._width = value
        elif property.name == 'height':
            self._height = value
        elif property.name == 'add-borders':
            if not gstreamer.element_has_property(self._videoscaler,
                                                  'add-borders'):
                self.warning("Can't add black borders because videoscale\
                    element doesn't have 'add-borders' property.")
            self._add_borders = value
        elif property.name == 'is-square':
            self._is_square = value
        else:
            raise AttributeError('unknown property %s' % property.name)

    def do_get_property(self, property):
        if property.name == 'width':
            return self._width or 0
        elif property.name == 'height':
            return self._height or 0
        elif property.name == 'add-borders':
            return self._add_borders
        elif property.name == 'is-square':
            return self._is_square or False
        else:
            raise AttributeError('unknown property %s' % property.name)

    def apply(self):
        peer = self._sinkPad.get_peer()
        self._updateFilter(peer)


class Videoscale(feedcomponent.PostProcEffect):
    """
    I am an effect that can be added to any component that has a video scaler
    component and a way of changing the size and PAR.
    """
    logCategory = "videoscale-effect"

    def __init__(self, name, component, sourcePad, pipeline,
                 width, height, is_square, add_borders=False):
        """
        @param element:     the video source element on which the post
                            processing effect will be added
        @param pipeline:    the pipeline of the element
        """
        feedcomponent.PostProcEffect.__init__(self, name, sourcePad,
            VideoscaleBin(width, height, is_square, add_borders), pipeline)
        self.pipeline = pipeline
        self.component = component

        vt = gstreamer.get_plugin_version('videoscale')
        if not vt:
            raise errors.MissingElementError('videoscale')
        if not vt > (0, 10, 29, 0):
            self.component.addMessage(
                messages.Warning(T_(N_(
                    "The videoscale element correctly "
                    "works with GStreamer base newer than 0.10.29.1."
                    "You should update your version of GStreamer."))))

    def setUIState(self, state):
        feedcomponent.Effect.setUIState(self, state)
        if state:
            for k in 'width', 'height', 'is-square', 'add-borders':
                state.addKey('videoscale-%s' % k,
                    self.effectBin.get_property(k))

    def _setHeight(self, height):
        self.effectBin.set_property('height', height)
        self.info('Changing height to %d' % height)
        self.uiState.set('videoscale-height', height)

    def effect_setHeight(self, height):
        self._setHeight(height)
        if self.effect_getIsSquare():
            self._setWidth(height *
                (self.effectBin._inwidth * self.effectBin._inpar.num) /
                (self.effectBin._inheight * self.effectBin._inpar.denom))
        return height

    def effect_getHeight(self):
        return self.effectBin.get_property('height')

    def _setWidth(self, width):
        self.effectBin.set_property('width', width)
        self.info('Changing width to %d' % width)
        self.uiState.set('videoscale-width', width)

    def effect_setWidth(self, width):
        self._setWidth(width)
        if self.effect_getIsSquare():
            self._setHeight(width *
                (self.effectBin._inheight * self.effectBin._inpar.denom) /
                (self.effectBin._inwidth * self.effectBin._inpar.num))
        return width

    def effect_getWidth(self):
        return self.effectBin.get_property('width')

    def effect_setIsSquare(self, is_square):
        self.effectBin.set_property('is-square', is_square)
        self.info('Changing is-square to %r' % is_square)
        self.uiState.set('videoscale-is-square', is_square)
        return is_square

    def effect_getIsSquare(self):
        return self.effectBin.get_property('is-square')

    def effect_setAddBorders(self, add_borders):
        self.effectBin.set_property('add-borders', add_borders)
        self.info('Changing add-borders to %r' % add_borders)
        self.uiState.set('videoscale-add-borders', add_borders)
        return add_borders

    def effect_getAddBorders(self):
        return self.effectBin.get_property('add-borders')

    def effect_setPAR(self, par):
        self.par = par
        self.info('Changing PAR to %s' % str(par))
        #self.uiState.set('videoscale-par', self.par)
        return repr(par) # FIXME: why does it complain with tuples returns...

    def effect_getPAR(self):
        return self.par

    def effect_apply(self):
        self.info("apply videoscale")
        self.effectBin.apply()
        return True
