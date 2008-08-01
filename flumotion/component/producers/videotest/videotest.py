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

from flumotion.common import errors, gstreamer, messages
from flumotion.common.i18n import N_, gettexter
from flumotion.component import feedcomponent

__version__ = "$Rev$"
T_ = gettexter()


class VideoTestMedium(feedcomponent.FeedComponentMedium):
    def remote_setPattern(self, pattern):
        return self.comp.set_element_property('source', 'pattern',
                                              pattern)

class VideoTest(feedcomponent.ParseLaunchComponent):
    componentMediumClass = VideoTestMedium

    def init(self):
        self.uiState.addKey('pattern', 0)

    def get_pipeline_string(self, properties):
        format = properties.get('format', 'video/x-raw-yuv')

        if format == 'video/x-raw-yuv':
            format = '%s,format=(fourcc)I420' % format

        # Filtered caps
        struct = gst.structure_from_string(format)
        for k in 'width', 'height':
            if k in properties:
                struct[k] = properties[k]

        if 'framerate' in properties:
            framerate = properties['framerate']
            struct['framerate'] = gst.Fraction(framerate[0], framerate[1])

        # always set par
        struct['pixel-aspect-ratio']= gst.Fraction(1, 1)
        if 'pixel-aspect-ratio' in properties:
            par = properties['pixel-aspect-ratio']
            struct['pixel-aspect-ratio'] = gst.Fraction(par[0], par[1])

        # If RGB, set something ffmpegcolorspace can convert.
        if format == 'video/x-raw-rgb':
            struct['red_mask'] = 0xff00
        caps = gst.Caps(struct)

        is_live = 'is-live=true'

        overlay = ""
        overlayTimestamps = properties.get('overlay-timestamps', False)
        if overlayTimestamps:
            overlay = " timeoverlay ! "

        return "videotestsrc %s name=source ! " % is_live + overlay + \
            "identity name=identity silent=TRUE ! %s" % caps

    # Set properties
    def configure_pipeline(self, pipeline, properties):
        def notify_pattern(obj, pspec):
            self.uiState.set('pattern', int(obj.get_property('pattern')))

        source = self.get_element('source')
        source.connect('notify::pattern', notify_pattern)
        if 'pattern' in properties:
            source.set_property('pattern', properties['pattern'])

        if 'drop-probability' in properties:
            vt = gstreamer.get_plugin_version('coreelements')
            if not vt:
                raise errors.MissingElementError('identity')
            if not vt > (0, 10, 12, 0):
                self.addMessage(
                    messages.Warning(T_(N_(
                        "The 'drop-probability' property is specified, but "
                        "it only works with GStreamer core newer than 0.10.12."
                        " You should update your version of GStreamer."))))
            else:
                drop_probability = properties['drop-probability']
                if drop_probability < 0.0 or drop_probability > 1.0:
                    self.addMessage(
                        messages.Warning(T_(N_(
                            "The 'drop-probability' property can only be "
                            "between 0.0 and 1.0."))))
                else:
                    identity = self.get_element('identity')
                    identity.set_property('drop-probability',
                        drop_probability)
