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

from flumotion.common import gstreamer
from flumotion.component import feedcomponent

__version__ = "$Rev$"


class Mulaw(feedcomponent.EncoderComponent):

    def get_pipeline_string(self, properties):
        resampler = 'audioresample'
        if gstreamer.element_factory_exists('legacyresample'):
            resampler = 'legacyresample'
        # we only support mulaw in multipart, and multipart mandates
        # the audio/basic content-type to be 8000 Hz mono, c.f. RFC2046
        return ('%s ! audioconvert ! audio/x-raw-int,rate=8000,channels=1 '
                '! mulawenc name=encoder' % resampler)
