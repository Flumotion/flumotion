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


from twisted.internet import defer, task
from twisted.spread import pb
from twisted.trial import unittest

from flumotion.configure import configure
from flumotion.common import medium, testsuite


class FakeRemote:

    disconnected = False
    disconnectCallback = None

    def __init__(self):
        # mock self.broker.transport.loseConnection()
        self.broker = self.transport = self
        self.loseConnection = self.disconnect

    def notifyOnDisconnect(self, callback):
        self.disconnectCallback = callback

    def disconnect(self):
        if self.disconnectCallback:
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

    def testCallRemoteAnswerResetsTimeout(self):
        clock = task.Clock()

        m = medium.PingingMedium()
        m.setRemoteReference(self.remote, clock=clock)

        clock.advance(self.pingCheckInterval)

        # answer to callRemote (should extend ping timeout)
        m.callRemote('test')
        self.assertEquals(self.remote.call, ('test', (), {}))
        self.remote.callback(True)

        clock.advance(self.pingCheckInterval)
        self.assert_(not self.remote.disconnected)

        clock.advance(self.pingCheckInterval)
        self.assert_(self.remote.disconnected)

    def testRemoteMessageResetsTimeout(self):
        clock = task.Clock()

        m = medium.PingingMedium()
        m.remote_test = lambda: True
        m.setRemoteReference(self.remote, clock=clock)

        clock.advance(self.pingCheckInterval)

        # received remote message from avatar (should extend ping timeout)
        broker = pb.Broker()
        m.remoteMessageReceived(
            broker, 'test', broker.serialize(()), broker.serialize({}))

        clock.advance(self.pingCheckInterval)
        self.assert_(not self.remote.disconnected)

        clock.advance(self.pingCheckInterval)
        self.assert_(self.remote.disconnected)

    def testRemoteMessageReceivedBeforeSettingRemoteReference(self):
        m = medium.PingingMedium()
        m.remote_test = lambda: True

        broker = pb.Broker()
        d = m.remoteMessageReceived(
            broker, 'test', broker.serialize(()), broker.serialize({}))

        def cb(result):
            result = broker.unserialize(result)
            self.assertEquals(result, True)
        d.addCallback(cb)

if __name__ == '__main__':
    unittest.main()
