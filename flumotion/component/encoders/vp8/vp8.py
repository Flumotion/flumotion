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

from flumotion.common import messages, errors
from flumotion.common.i18n import N_, gettexter
from flumotion.component import feedcomponent


__version__ = "$Rev$"
T_ = gettexter()


class VP8(feedcomponent.EncoderComponent):
    checkTimestamp = True
    checkOffset = True

    def check_properties(self, props, addMessage):

        def check_limit(prop_name, lower_limit, upper_limit):
            val = props.get(prop_name, None)
            if val is None:
                return
            if val < lower_limit or val > upper_limit:
                msg = messages.Error(T_(N_(
                    "The configuration property '%s' can only take "
                    "values from %d to %d"),
                    prop_name, lower_limit, upper_limit), mid='config')
                addMessage(msg)
                raise errors.ConfigError(msg)

        check_limit('speed', 0, 2)
        check_limit('threads', 1, 64)

    def get_pipeline_string(self, properties):
        return "ffmpegcolorspace ! vp8enc name=encoder"

    def configure_pipeline(self, pipeline, properties):
        element = pipeline.get_by_name('encoder')

        props = (('bitrate', 'bitrate', 400),
                 ('quality', 'quality', None),
                 ('speed', 'speed', 2),
                 ('threads', 'threads', 4),
                 ('keyframe-maxdistance', 'max-keyframe-distance', 50))

        for pproperty, eproperty, default in props:
            if eproperty is None:
                eproperty = properties

            if not pproperty in properties and default is None:
                continue

            value = properties.get(pproperty, default)
            self.debug('Setting GStreamer property %s to %r' % (
                eproperty, value))

            element.set_property(eproperty, value)

    def modify_property_Bitrate(self, value):
        if not self.checkPropertyType('bitrate', value, int):
            return False
        self.modify_element_property('encoder', 'bitrate', value)
        return True
