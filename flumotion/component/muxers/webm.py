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

from flumotion.common import messages
from flumotion.common.i18n import N_, gettexter
from flumotion.component import feedcomponent
from flumotion.worker.checks import check

__version__ = "$Rev$"
T_ = gettexter()


class WebM(feedcomponent.MuxerComponent):
    checkTimestamp = True

    def do_check(self):
        return check.do_check(self, check.checkPlugin, 'matroska',
                              'gst-plugins-good', (0, 10, 24))

    def get_muxer_string(self, properties):
        muxer = 'webmmux name=muxer streamable=true'
        return muxer
