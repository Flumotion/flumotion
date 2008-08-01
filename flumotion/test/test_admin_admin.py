# -*- Mode: Python; test-case-name: flumotion.test.test_admin_admin -*-
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

from flumotion.admin import admin
from flumotion.common import connection
from flumotion.common import testsuite
from flumotion.twisted import pb


class AdminTest(testsuite.TestCaseWithManager):

    def testConstructor(self):
        model = admin.AdminModel()

    def testConnectSuccess(self):

        def connected(_):
            self.failUnless(a.planet is not None)
            self.assertEqual(len(self.vishnu.adminHeaven.avatars),
                             1)
            a.shutdown()

        a = admin.AdminModel()
        d = a.connectToManager(self.connectionInfo,
                               writeConnection=False)
        d.addCallback(connected)
        return d

    def testReconnect(self):
        disconnectDeferred = defer.Deferred()
        reconnectDeferred = defer.Deferred()

        def connected(_):
            self.failUnless(a.planet is not None)
            self.assertEqual(len(self.vishnu.adminHeaven.avatars),
                             1)

            def _disconnected(_):
                disconnectDeferred.callback(None)

            def _connected(_):
                map(a.disconnect, ids)
                reconnectDeferred.callback(None)

            ids = []
            ids.append(a.connect('disconnected', _disconnected))
            ids.append(a.connect('connected', _connected))
            a.clientFactory.disconnect()
            return disconnectDeferred

        def disconnected(_):
            return reconnectDeferred

        def reconnected(_):
            # yay
            a.shutdown()

        a = admin.AdminModel()
        d = a.connectToManager(self.connectionInfo,
                               writeConnection=False)
        d.addCallback(connected)
        d.addCallback(disconnected)
        d.addCallback(reconnected)
        return d

    def testConnectFailure(self):

        def connected(_):
            self.fail('should not have connected')

        def failure(f):
            # ok!
            a.shutdown()

        a = admin.AdminModel()
        # create a connectionInfo that will not succeed
        i = connection.PBConnectionInfo(self.connectionInfo.host,
                                        self.connectionInfo.port,
                                        self.connectionInfo.use_ssl,
                                        pb.Authenticator(username='user',
                                                         password='pest'))
        d = a.connectToManager(i, writeConnection=False)
        d.addCallbacks(connected, failure)
        return d
