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

from flumotion.common import gstreamer

from flumotion.component import feedcomponent

from flumotion.component.effects.colorbalance import colorbalance

__version__ = "$Rev$"


class Webcam(feedcomponent.ParseLaunchComponent):

    def get_pipeline_string(self, properties):
        device = properties['device']

        # v4l was removed from the kernel, so v4l2 is default one
        factory_name = properties.get('element-factory', 'v4l2src')

        # Filtered caps
        mime = properties.get('mime', 'video/x-raw-yuv')
        colorspace = properties.get('format', 'I420')
        width = properties.get('width', None)
        height = properties.get('height', None)

        string = mime
        if mime == 'video/x-raw-yuv':
            string += ",format=(fourcc)%s" % colorspace
        if width:
            string += ",width=%d" % width
        if height:
            string += ",height=%d" % height
        if 'framerate' in properties:
            f = properties['framerate']
            string += ",framerate=(fraction)%d/%d" % (f[0], f[1])

        if factory_name == 'v4lsrc':
            factory_name += ' autoprobe=false autoprobe-fps=false copy-mode=1'
        # v4l2src automatically copies

        # FIXME: ffmpegcolorspace in the pipeline causes bad negotiation.
        # hack in 0.9 to work around, not in 0.8
        # correct solution would be to find the colorspaces, see halogen
        # pipeline = 'v4lsrc name=source %s copy-mode=1 device=%s ! ' \
        #           'ffmpegcolorspace ! "%s" ! videorate ! "%s"' \
        #           % (autoprobe, device, caps, caps)
        return ('%s name=source device=%s ! %s ! videorate'
                % (factory_name, device, string))

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
