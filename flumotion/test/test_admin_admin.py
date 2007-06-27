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

import common

from StringIO import StringIO

from twisted.cred import error
from twisted.trial import unittest
from twisted.internet import reactor
from twisted.python import log as tlog

from flumotion.common import config, server, connection, log
from flumotion.twisted import pb
from flumotion.manager import manager
from flumotion.admin import admin


managerConf = """
<planet>
<manager name="planet">
    <host>localhost</host>
    <port>0</port>
    <transport>tcp</transport>
    <component name="manager-bouncer" type="htpasswdcrypt-bouncer">
      <property name="data"><![CDATA[
user:PSfNpHTkpTx1M
]]></property>
    </component>
  </manager>
</planet>
"""


class TestCaseWithManager(unittest.TestCase):
    def setUp(self):
        # This bit about log flushing is repeated in various tests;
        # would be good to see about making it unnecessary. Perhaps
        # returning a pb.Error subclass instead of UnauthorizedLogin
        # would do the trick.

        # don't output Twisted tracebacks for PB errors we will trigger
        log._getTheFluLogObserver().ignoreErrors(error.UnauthorizedLogin)

        conf = config.ManagerConfigParser(StringIO(managerConf)).manager
        self.vishnu = manager.Vishnu(conf.name,
                                     unsafeTracebacks=True)
        self.vishnu.loadManagerConfigurationXML(StringIO(managerConf))
        s = server.Server(self.vishnu)
        if conf.transport == "ssl":
            p = s.startSSL(conf.host, conf.port, conf.certificate,
                           configure.configdir) 
        elif conf.transport == "tcp":
            p = s.startTCP(conf.host, conf.port)
        self.tport = p
        self.port = p.getHost().port
        i = connection.PBConnectionInfo('localhost', self.port,
                                        conf.transport == 'ssl',
                                        pb.Authenticator(username='user',
                                                         password='test'))
        self.connectionInfo = i
        
    def tearDown(self):
        try:
            self.flushLoggedErrors(error.UnauthorizedLogin)
        except AttributeError:
            tlog.flushErrors(error.UnauthorizedLogin)
        log._getTheFluLogObserver().clearIgnores()

        d = self.vishnu.shutdown()
        d.addCallback(lambda _: self.tport.stopListening())
        return d


class AdminTest(TestCaseWithManager):
    def testConstructor(self):
        model = admin.AdminModel()

    def testConnectSuccess(self):
        def connected(_):
            self.failUnless(a.planet is not None)
            self.assertEqual(len(self.vishnu.adminHeaven.avatars),
                             1)
            a.shutdown()

        a = admin.AdminModel()
        d = a.connectToManager(self.connectionInfo)
        d.addCallback(connected)
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
        d = a.connectToManager(i)
        d.addCallbacks(connected, failure)
        return d
