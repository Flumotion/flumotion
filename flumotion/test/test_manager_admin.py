# -*- Mode: Python; test-case-name: flumotion.test.test_manager_admin -*-
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

from twisted.spread import pb

from flumotion.common import keycards, testsuite, interfaces
from flumotion.manager import admin, manager


class FakeTransport:

    def getPeer(self):
        from twisted.internet.address import IPv4Address
        return IPv4Address('TCP', 'nullhost', 1)

    def getHost(self):
        from twisted.internet.address import IPv4Address
        return IPv4Address('TCP', 'nullhost', 1)


class FakeBroker:

    def __init__(self):
        self.transport = FakeTransport()


class FakeMind:

    def __init__(self):
        self.broker = FakeBroker()

    def notifyOnDisconnect(self, proc):
        pass


class TestAdminAvatar(testsuite.TestCase):

    def setUp(self):
        self.vishnu = manager.Vishnu('test', unsafeTracebacks=True)
        keycard = keycards.KeycardUACPP('user', 'test', '127.0.0.1')
        self.heaven = self.vishnu.adminHeaven
        d = self.vishnu.dispatcher.requestAvatar('foo-avatar-id',
                                                 keycard,
                                                 FakeMind(),
                                                 pb.IPerspective,
                                                 interfaces.IAdminMedium)

        def gotAvatar((iface, avatar, cleanup)):
            self.avatar = avatar
            self._cleanup = cleanup
        d.addCallback(gotAvatar)
        return d

    def tearDown(self):
        self._cleanup()
        self.assertEquals(self.heaven.getAvatars(), [])

    def testAvatarSet(self):
        self.assertEquals(self.heaven.getAvatars(), [self.avatar])
