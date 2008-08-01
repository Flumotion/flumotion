# -*- Mode: Python; test-case-name:flumotion.test.test_worker_worker -*-
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

from twisted.internet import defer
from twisted.spread import pb

from flumotion.common import testsuite
from flumotion.test import realm
from flumotion.twisted import pb as fpb
from flumotion.worker import medium


class TestWorkerAvatar(fpb.PingableAvatar):

    def __init__(self, avatarId, mind):
        fpb.PingableAvatar.__init__(self, avatarId)
        self.setMind(mind)


class TestWorkerRealm(realm.TestRealm):
    deferredAvatar = None
    deferredLogout = None

    def getDeferredAvatar(self):
        if self.deferredAvatar is None:
            self.deferredAvatar = defer.Deferred()
        return self.deferredAvatar

    def getDeferredLogout(self):
        if self.deferredLogout is None:
            self.deferredLogout = defer.Deferred()
        return self.deferredLogout

    def requestAvatar(self, avatarId, keycard, mind, *ifaces):
        avatar = TestWorkerAvatar(avatarId, mind)
        self.getDeferredAvatar().callback(avatar)
        return (pb.IPerspective, avatar,
                lambda: self.avatarLogout(avatar))

    def avatarLogout(self, avatar):
        self.debug('worker logged out: %s', avatar.avatarId)
        self.getDeferredLogout().callback(avatar)


class TestWorkerMedium(testsuite.TestCase):

    def setUp(self):
        self.realm = TestWorkerRealm()

    def tearDown(self):
        return self.realm.shutdown()

    def testConnect(self):
        m = medium.WorkerMedium(None)
        connectionInfo = self.realm.getConnectionInfo()
        connectionInfo.authenticator.avatarId = 'foo'
        m.startConnecting(connectionInfo)

        def connected(avatar):
            m.stopConnecting()
            return self.realm.getDeferredLogout()

        def disconnected(avatar):
            self.assertEquals(avatar.avatarId, 'foo')

        d = self.realm.getDeferredAvatar()
        d.addCallback(connected)
        d.addCallback(disconnected)
        return d
