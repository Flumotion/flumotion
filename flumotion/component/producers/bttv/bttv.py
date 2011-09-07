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
import gst.interfaces

from flumotion.common import log

from flumotion.component import feedcomponent
from flumotion.component.effects.colorbalance import colorbalance

# FIXME: rename to TVCard
__all__ = ['BTTV']
__version__ = "$Rev$"


def arg_filtered(proc, *args):

    def ret(*_args):
        for spec in args:
            if len(spec) == 3:
                key = spec[2]
            else:
                key = lambda x: x
            index = spec[0]
            value = spec[1]
            if len(_args) <= index or key(_args[index]) != value:
                return
        return proc(*_args)
    return ret


def call_on_state_change(element, from_state, to_state, proc, *args, **kwargs):

    def bus_watch_func(bus, message):
        proc(*args, **kwargs)
    bus_watch_func = arg_filtered(bus_watch_func,
        (1, element, lambda x: x.src),
        (1, [from_state, to_state, gst.STATE_VOID_PENDING],
         lambda x: x.parse_state_changed()))
    parent = element
    while parent.get_parent():
        parent = parent.get_parent()
    b = parent.get_bus()
    b.connect('message::state-changed', bus_watch_func)


class BTTV(feedcomponent.ParseLaunchComponent):

    def get_pipeline_string(self, properties):
        device = properties['device']
        width = properties.get('width', 320)
        height = properties.get('height', 240)

        # This needs to be done properly
        device_width = width
        device_height = height
        #device_width = properties['device-width']
        #device_height = properties['device-height']

        framerate = properties.get('framerate', (25, 1))
        framerate_string = '%d/%d' % (framerate[0], framerate[1])

        pipeline = ('v4lsrc name=source device=%s copy-mode=true ! '
                    'video/x-raw-yuv,width=%d,height=%d ! videoscale ! '
                    'video/x-raw-yuv,width=%d,height=%d ! videorate ! '
                    'video/x-raw-yuv,framerate=%s') % (device,
                                                       device_width,
                                                       device_height,
                                                       width, height,
                                                       framerate_string)
        return pipeline

    def configure_pipeline(self, pipeline, properties):
        # create and add colorbalance effect
        source = pipeline.get_by_name('source')
        hue = properties.get('hue', None)
        saturation = properties.get('saturation', None)
        brightness = properties.get('brightness', None)
        contrast = properties.get('contrast', None)
        cb = colorbalance.Colorbalance('outputColorbalance', source,
            hue, saturation, brightness, contrast, pipeline)
        self.addEffect(cb)

        # register state change notify to set channel and norm
        element = pipeline.get_by_name('source')
        channel = properties.get('channel', None)
        norm = properties.get('signal', None)

        call_on_state_change(element, gst.STATE_READY, gst.STATE_PAUSED,
            self.set_channel_and_norm, element, channel, norm)

    def set_channel_and_norm(self, element, channel, norm):
        self.debug("bttv READY->PAUSED, setting channel %s and norm %s" % (
            channel, norm))
        if channel:
            c = element.find_channel_by_name(channel)
            if c:
                self.debug("set channel to %s" % channel)
                element.set_channel(c)
        if norm:
            c = element.find_norm_by_name(norm)
            if c:
                self.debug("set norm to %s" % norm)
                element.set_norm(c)
