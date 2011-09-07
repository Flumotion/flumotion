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
from twisted.internet import defer

from flumotion.component import feedcomponent

__version__ = "$Rev$"


class Ogg(feedcomponent.MuxerComponent):
    checkTimestamp = True

    def do_check(self):
        self.debug('running Ogg check')
        import checks
        d1 = checks.checkOgg()
        d2 = checks.checkTicket1344()
        dl = defer.DeferredList([d1, d2])
        dl.addCallback(self._checkCallback)
        return dl

    def _checkCallback(self, results):
        for (state, result) in results:
            for m in result.messages:
                self.addMessage(m)

    def get_muxer_string(self, properties):
        maxDelay = 500 * 1000 * 1000
        maxPageDelay = 500 * 1000 * 1000
        muxer = 'oggmux name=muxer max-delay=%d max-page-delay=%d' % (
            maxDelay, maxPageDelay)

        return muxer
