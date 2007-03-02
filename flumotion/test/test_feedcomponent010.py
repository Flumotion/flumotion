# -*- Mode: Python; test-case-name: flumotion.test.test_feedcomponent010 -*-
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

from twisted.trial import unittest

import common

from twisted.python import failure
from twisted.internet import defer

from flumotion.component import feedcomponent010 as fc

class TestFeeder(unittest.TestCase):
    def setUp(self):
        self.feeder = fc.Feeder('video:default')

    def test_addClient(self):
        clientId = '/default/muxer-video'
        self.feeder.addClient(clientId, 3)
        clients = self.feeder.getClients()
        self.failUnless(3 in clients.keys())
        client = clients[3]
        self.assertEquals(client.uiState.get('clientId'), clientId)

    def testReconnect(self):
        clientId = '/default/muxer-video'

        # connect
        c = self.feeder.addClient(clientId, 3)

        # verify some stuff
        self.clientAssertStats(c, 0, 0, 0, 0, 1)

        # read 10 bytes, drop 1 buffer
        c.setStats((10, None, None, None, None, 1))
        self.clientAssertStats(c, 10, 1, 10, 1, 1)

        # disconnect
        self.feeder.removeClient(3)
        self.clientAssertStats(c, 0, 0, 10, 1, 1)

        # connect again
        self.feeder.addClient(clientId, 3)
        self.clientAssertStats(c, 0, 0, 10, 1, 2)

        # read 20 bytes, drop 2 buffers
        c.setStats((20, None, None, None, None, 2))
        self.clientAssertStats(c, 20, 2, 30, 3, 2)

    def clientAssertEquals(self, client, key, value):
        self.assertEquals(client.uiState.get(key), value)

    def clientAssertStats(self, client, brc, bdc, brt, bdt, reconnects):
        self.clientAssertEquals(client, 'bytesReadCurrent', brc)
        self.clientAssertEquals(client, 'buffersDroppedCurrent', bdc)
        self.clientAssertEquals(client, 'bytesReadTotal', brt)
        self.clientAssertEquals(client, 'buffersDroppedTotal', bdt)
        self.clientAssertEquals(client, 'reconnects', reconnects)

if __name__ == '__main__':
    unittest.main()
