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

from twisted.internet import defer, task
from twisted.trial import unittest

from flumotion.configure import configure
from flumotion.common import medium, testsuite


class FakeRemote:

    disconnected = False

    def __init__(self):
        # mock self.broker.transport.loseConnection()
        self.broker = self.transport = self
        self.loseConnection = self.disconnect

    def notifyOnDisconnect(self, callback):
        self.disconnectCallback = callback

    def disconnect(self):
        self.disconnectCallback(self)
        self.disconnected = True

    def callRemote(self, name, *args, **kw):
        self.d = defer.Deferred()
        self.call = (name, args, kw)
        return self.d

    def callback(self, result):
        return self.d.callback(result)


class TestPingingMedium(testsuite.TestCase):

    pingCheckInterval = (configure.heartbeatInterval *
                         configure.pingTimeoutMultiplier)

    def setUp(self):
        self.remote = FakeRemote()

    def tearDown(self):
        self.remote.disconnect()

    def testInitialPing(self):
        m = medium.PingingMedium()
        m.setRemoteReference(self.remote)
        self.assertEquals(self.remote.call, ('ping', (), {}))

    def testNoPingback(self):
        clock = task.Clock()

        m = medium.PingingMedium()
        m.setRemoteReference(self.remote, clock=clock)
        self.assert_(not self.remote.disconnected)

        clock.advance(self.pingCheckInterval)
        self.assert_(not self.remote.disconnected)

        clock.advance(self.pingCheckInterval)
        self.assert_(self.remote.disconnected)

    def testPingbackResetsTimeout(self):
        clock = task.Clock()

        m = medium.PingingMedium()
        m.setRemoteReference(self.remote, clock=clock)

        clock.advance(self.pingCheckInterval)

        # pingback (should extend ping timeout)
        self.remote.callback(True)

        clock.advance(self.pingCheckInterval)
        self.assert_(not self.remote.disconnected)

        clock.advance(self.pingCheckInterval)
        self.assert_(self.remote.disconnected)


if __name__ == '__main__':
    unittest.main()
