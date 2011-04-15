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

from flumotion.common import messages, errors, gstreamer
from flumotion.common.i18n import N_, gettexter
from flumotion.component import feedcomponent
from flumotion.worker.checks import check


__version__ = "$Rev$"
T_ = gettexter()


class Theora(feedcomponent.EncoderComponent):
    checkTimestamp = True
    checkOffset = True

    def do_check(self):
        self.debug('running Theora check')
        from flumotion.worker.checks import encoder
        return check.do_check(self, encoder.checkTheora)

    def check_properties(self, props, addMessage):
        props = self.config['properties']
        speed = props.get('speed', 3)

        if speed > 3:
            msg = messages.Error(T_(N_(
                "The configuration property 'speed' can only take "
                "values from 0 to 3")), mid='speed')
            addMessage(msg)
            raise errors.ConfigError(msg)

    def get_pipeline_string(self, properties):
        return "ffmpegcolorspace ! theoraenc name=encoder"

    def configure_pipeline(self, pipeline, properties):
        element = pipeline.get_by_name('encoder')

        for p in ['sharpness', 'quick-compress', 'noise-sensitivity']:
            if properties.get(p, None) is not None:
                self.warnDeprecatedProperties([p])

        props = ('bitrate',
                 'quality',
                 ('speed', 'speed-level'),
                 ('keyframe-mindistance', 'keyframe-freq'),
                 ('keyframe-maxdistance', 'keyframe-force'))

        for p in props:
            if isinstance(p, tuple):
                pproperty, eproperty = p
            else:
                pproperty = eproperty = p

            if not pproperty in properties:
                continue

            value = properties[pproperty]
            self.debug('Setting GStreamer property %s to %r' % (
                eproperty, value))

            # FIXME: GStreamer 0.10 has bitrate in kbps, inconsistent
            # with all other elements, so fix it up
            if pproperty == 'bitrate':
                value = int(value/1000)
            # Check for the speed-level property, introduced in
            # gst-plugins-base-0.10.24
            if eproperty == 'speed-level':
                if not gstreamer.element_has_property(element, 'speed-level'):
                    self.warning("Trying to set the 'speed-level' property "
                                  "in a old version of gstreamer's theora "
                                  "encoder element")
                    self.warning("We will fallback to the 'quick' property")
                    eproperty = 'quick'
                    value = value > 0 and True or False
            element.set_property(eproperty, value)
