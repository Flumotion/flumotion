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

from flumotion.component.common.avproducer import avproducer

__version__ = "$Rev$"


class Ivtv(avproducer.AVProducerBase):

    decoder = None
    device = None

    def get_raw_video_element(self):
        return self.decoder

    def get_pipeline_template(self):
        return ("filesrc name=src location=%s"
                "   ! decodebin name=dec "
                "  dec. ! identity silent=true name=video ! @feeder:video@"
                "  dec. ! audioconvert ! audio/x-raw-int !"
                "  volume name=setvolume !"
                "  level name=volumelevel message=true !"
                "  @feeder:audio@" % self.device)

    def _parse_aditional_properties(self, properties):
        self.decoder = self.get_element('video')
        self.device = properties.get('device', '/dev/video0')
