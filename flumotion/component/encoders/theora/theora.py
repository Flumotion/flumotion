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

from flumotion.component import feedcomponent
from flumotion.common import messages

from flumotion.common.messages import N_
T_ = messages.gettexter('flumotion')

class Theora(feedcomponent.ParseLaunchComponent):
    def do_check(self):
        self.debug('running Theora check')
        from flumotion.worker.checks import encoder
        d = encoder.checkTheora()

        d.addCallback(self._checkCallback)

        return d

    def _checkCallback(self, result):
        for m in result.messages:
            self.addMessage(m)

    def get_pipeline_string(self, properties):
        return "ffmpegcolorspace ! theoraenc name=encoder"

    def configure_pipeline(self, pipeline, properties):
        element = pipeline.get_by_name('encoder')

        props = ('bitrate',
                 'quality',
                 'keyframe-threshold',
                 'keyframe-mindistance', 
                 ('quick-compress', 'quick'),
                 ('keyframe-maxdistance', 'keyframe-freq'),
                 ('keyframe-maxdistance', 'keyframe-force'),
                 'noise-sensitivity')

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
                        "kbit/sec.  Please convert it to a value in bit/sec by "
                        "multiplying the value by 1000.")), id='bitrate'))
                properties['bitrate'] *= 1000

        # FIXME: GStreamer 0.10 has bitrate in kbps, inconsistent
        # with all other elements, so fix it up
        if 'bitrate' in properties:
            properties['bitrate'] = int(properties['bitrate'] / 1000)

        for p in props:
            pproperty = isinstance(p, tuple) and p[0] or p
            eproperty = isinstance(p, tuple) and p[1] or p

            if pproperty in properties:
                self.debug('Setting GStreamer property %s to %r' % (
                    eproperty, properties[pproperty]))
                element.set_property(eproperty, properties[pproperty])

