# -*- Mode: Python; test-case-name: flumotion.test.test_feedcomponent010 -*-
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

import time

from flumotion.common import testsuite

from twisted.internet import defer, reactor

from flumotion.component import feeder


class TestFeeder(testsuite.TestCase):

    def setUp(self):
        self.feeder = feeder.Feeder('video:default')

    def test_clientConnected(self):
        clientId = '/default/muxer-video'
        client = self.feeder.clientConnected(clientId, 3, lambda _: None)
        clients = self.feeder.getClients()
        self.failUnless(client in clients)
        self.assertEquals(client.uiState.get('client-id'), clientId)

    def testReconnect(self):
        clientId = '/default/muxer-video'

        # This needed because disconnecting clients only updates the stats in
        # a callFromThread (which is roughly the same as a callLater).
        d = defer.Deferred()

        def checkClientDisconnected():
            self.clientAssertStats(c, 0, 0, 10, 1, 1)

            # connect again
            self.feeder.clientConnected(clientId, 3, lambda _: None)
            self.clientAssertStats(c, 0, 0, 10, 1, 2)

            # read 20 bytes, drop 2 buffers
            c.setStats((20, None, None, None, time.time(), 2))
            self.clientAssertStats(c, 20, 2, 30, 3, 2)

            d.callback(None)

        # connect
        c = self.feeder.clientConnected(clientId, 3, lambda _: None)

        # verify some stuff
        self.clientAssertStats(c, 0, None, 0, None, 1)

        # read 10 bytes, drop 1 buffer
        c.setStats((10, None, None, None, time.time(), 1))
        self.clientAssertStats(c, 10, 1, 10, 1, 1)

        # remove client
        self.feeder.clientDisconnected(3)

        reactor.callLater(0, checkClientDisconnected)

        return d

    def clientAssertEquals(self, client, key, value):
        self.assertEquals(client.uiState.get(key), value)

    def clientAssertStats(self, client, brc, bdc, brt, bdt, reconnects):
        self.clientAssertEquals(client, 'bytes-read-current', brc)
        self.clientAssertEquals(client, 'buffers-dropped-current', bdc)
        self.clientAssertEquals(client, 'bytes-read-total', brt)
        self.clientAssertEquals(client, 'buffers-dropped-total', bdt)
        self.clientAssertEquals(client, 'reconnects', reconnects)
