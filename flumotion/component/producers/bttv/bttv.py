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
import gst.interfaces

from flumotion.common import log

from flumotion.component import feedcomponent
from flumotion.component.effects.colorbalance import colorbalance

# FIXME: rename to TVCard
# FIXME: what does __all__ *do* ?
__all__ = ['BTTV']

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
        if gst.gst_version < (0,9):
            framerate_string = '%f' % (float(framerate[0]) / framerate[1])
        else:
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
            hue, saturation, brightness, contrast)
        self.addEffect(cb)

        # register state change notify to set channel and norm
        element = pipeline.get_by_name('source')
        channel = properties['channel']
        norm = properties['signal']
        element.connect('state-change', self.state_changed_cb, channel, norm)

    # called to set initial channel and norm from NULL->READY
    def state_changed_cb(self, element, old, new, channel, norm):
        if not (old == gst.STATE_NULL and new == gst.STATE_READY):
            return

        self.debug("bttv NULL->READY, setting channel %s and norm %s" % (
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
