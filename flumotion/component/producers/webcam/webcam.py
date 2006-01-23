# -*- Mode: Python -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# Flumotion - a streaming media server
# Copyright (C) 2004,2005,2006 Fluendo, S.L. (www.fluendo.com).
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

from flumotion.common import gstreamer

from flumotion.component import feedcomponent
from flumotion.component.effects.colorbalance import colorbalance

class Webcam(feedcomponent.ParseLaunchComponent):

    def get_pipeline_string(self, properties):
        device = properties['device']

        # Filtered caps
        format = properties.get('format', 'video/x-raw-yuv')
        struct = gst.structure_from_string('%s,format=(fourcc)I420' % format)

        if 'framerate' in properties:
            framerate = properties['framerate']
            if gst.gst_version < (0,9):
                struct['framerate'] = float(framerate[0]) / framerate[1]
            else:
                struct['framerate'] = gst.Fraction(framerate[0], framerate[1])

        for k in 'width', 'height':
            if k in properties:
                struct[k] = properties[k]
        caps = gst.Caps(struct)
       
        # create component
        autoprobe = "autoprobe=false"
        # added in gst-plugins 0.8.6
        if gstreamer.element_factory_has_property('v4lsrc', 'autoprobe-fps'):
            autoprobe += " autoprobe-fps=false"
        
        # FIXME: ffmpegcolorspace in the pipeline causes bad negotiation.
        # hack in 0.9 to work around, not in 0.8
        # correct solution would be to find the colorspaces, see halogen
        # pipeline = 'v4lsrc name=source %s copy-mode=1 device=%s ! ' \
        #           'ffmpegcolorspace ! "%s" ! videorate ! "%s"' \
        #           % (autoprobe, device, caps, caps)
        return ('v4lsrc name=source %s copy-mode=1 device=%s ! '
                'videorate ! %s' % (autoprobe, device, caps))

    def configure_pipeline(self, pipeline, properties):
        # create and add colorbalance effect
        if gst.gst_version < (0,9):
            source = pipeline.get_by_name('source')
            hue = properties.get('hue', None)
            saturation = properties.get('saturation', None)
            brightness = properties.get('brightness', None)
            contrast = properties.get('contrast', None)
            cb = colorbalance.Colorbalance('outputColorbalance', source,
                hue, saturation, brightness, contrast)
            self.addEffect(cb)
