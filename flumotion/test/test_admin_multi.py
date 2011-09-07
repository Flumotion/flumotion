# -*- Mode: Python; test-case-name: flumotion.test.test_admin_multi -*-
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

from flumotion.common import testsuite

from twisted.internet import defer

from flumotion.admin import multi
from flumotion.common import connection
from flumotion.twisted import pb

attr = testsuite.attr


class MultiAdminTest(testsuite.TestCaseWithManager):

    def testConstructor(self):
        model = multi.MultiAdminModel()

    def testConnectSuccess(self):

        def connected(_):
            self.assertEqual(len(self.vishnu.adminHeaven.avatars),
                             1)
            return m.removeManager(str(self.connectionInfo))

        m = multi.MultiAdminModel()
        d = m.addManager(self.connectionInfo, writeConnection=False)
        d.addCallback(connected)
        return d

    def testConnectFailure(self):

        def connected(_):
            self.fail('should not have connected')

        def failure(f):
            # ok!
            self.assertEqual(len(self.vishnu.adminHeaven.avatars), 0)
            self.assertEqual(m.admins, {})
            self.assertEqual(m._reconnectHandlerIds, {})

        m = multi.MultiAdminModel()
        i = connection.PBConnectionInfo(self.connectionInfo.host,
                                        self.connectionInfo.port,
                                        self.connectionInfo.use_ssl,
                                        pb.Authenticator(username='user',
                                                         password='pest'))
        d = m.addManager(i, writeConnection=False)
        d.addCallbacks(connected, failure)
        return d

    @attr('slow')
    def testReconnect(self):

        class Listener:

            def __init__(self):
                self.disconnectDeferred = defer.Deferred()
                self.reconnectDeferred = defer.Deferred()

            def model_addPlanet(self, admin, planet):
                self.reconnectDeferred.callback(admin)
                self.reconnectDeferred = None

            def model_removePlanet(self, admin, planet):
                self.disconnectDeferred.callback(admin)
                self.disconnectDeferred = None
        Listener = Listener()

        def connected(_):
            self.assertEqual(len(self.vishnu.adminHeaven.avatars),
                             1)
            a = m.admins[str(self.connectionInfo)]

            m.addListener(Listener)

            a.clientFactory.disconnect()

            return Listener.disconnectDeferred

        def disconnected(_):
            return Listener.reconnectDeferred

        def reconnected(_):
            m.removeListener(Listener)
            return m.removeManager(str(self.connectionInfo))

        m = multi.MultiAdminModel()
        d = m.addManager(self.connectionInfo, writeConnection=False)
        d.addCallback(connected)
        d.addCallback(disconnected)
        d.addCallback(reconnected)
        return d
