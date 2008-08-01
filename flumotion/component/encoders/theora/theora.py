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

from flumotion.common import messages
from flumotion.common.i18n import N_, gettexter
from flumotion.component import feedcomponent
from flumotion.worker.checks import check


__version__ = "$Rev$"
T_ = gettexter()


class Theora(feedcomponent.ParseLaunchComponent):
    checkTimestamp = True
    checkOffset = True

    def do_check(self):
        self.debug('running Theora check')
        from flumotion.worker.checks import encoder
        return check.do_check(self, encoder.checkTheora)

    def get_pipeline_string(self, properties):
        return "ffmpegcolorspace ! theoraenc name=encoder"

    def configure_pipeline(self, pipeline, properties):
        element = pipeline.get_by_name('encoder')

        props = ('bitrate',
                 'quality',
                 'keyframe-mindistance',
                 ('quick-compress', 'quick'),
                 ('keyframe-maxdistance', 'keyframe-freq'),
                 ('keyframe-maxdistance', 'keyframe-force'),
                 'noise-sensitivity',
                 'sharpness')

        # F0.6: remove this code
        # before 0.3.2, bitrate was interpreted as kbps, inconsistent
        # with other flumotion components
        # safe to assume that nobody will want less than 10 kbit/sec
        # also, MikeS *requires* a kbit/sec to be seen as 1000 bit/sec
        if 'bitrate' in properties:
            if properties['bitrate'] < 10000:
                self.addMessage(
                    messages.Warning(T_(N_(
                        "Your configuration uses 'bitrate' expressed in "
                        "kbit/sec.  Please convert it to a value in bit/sec by"
                        " multiplying the value by 1000.")), mid='bitrate'))
                properties['bitrate'] *= 1000

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
            element.set_property(eproperty, value)
