# -*- Mode: Python; test-case-name: flumotion.test.test_server_selector -*-
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

import exceptions
import time

import twisted

from twisted.internet import defer, threads, reactor
from flumotion.common import testsuite, errors
from flumotion.component.misc.httpserver.httpcached import server_selection

twisted.internet.base.DelayedCall.debug = True


class TestServerSelector(testsuite.TestCase):

    def setUp(self):
        self.ss = server_selection.ServerSelector()
        self.ss.setup()
        self.s = None

    def tearDown(self):
        self.ss.cleanup()
        self.s = None

    def testEmpty(self):
        s = self.ss.getServers()
        self.failUnlessRaises(exceptions.StopIteration, s.next)

    def testAddLocalhost(self):
        d = self.ss.addServer("localhost", 80)
        d.addCallback(lambda _: self.ss.getServers())
        d.addCallback(lambda s: setattr(self, "s", s))
        d.addCallback(lambda _: self.s.next())
        return d

    def testAddTwiceLocalhost(self):
        d1 = self.ss.addServer("flumotion.com", 80, 1.0)
        d2 = self.ss.addServer("flumotion.com", 80, 1.0)
        d = defer.DeferredList([d1, d2])
        d.addCallback(lambda _: self.ss.getServers())
        d.addCallback(lambda s: setattr(self, "s", s))
        d.addCallback(lambda _: self.s.next())
        d.addCallback(lambda _: self.failUnlessRaises(exceptions.StopIteration,
                                                      self.s.next))
        d.addCallback(lambda _: self.ss.addServer("flumotion.com", 80, 2.0))
        d.addCallback(lambda _: self.ss.getServers())
        d.addCallback(lambda s: setattr(self, "s", s))
        d.addCallback(lambda _: self.s.next())
        d.addCallback(lambda _: self.s.next())
        d.addCallback(lambda _: self.failUnlessRaises(exceptions.StopIteration,
                                                      self.s.next))
        return d

    def testAddFlumotionIsRad(self):
        d = self.ss.addServer("flumotionIs.rad", 80)
        d.addCallback(lambda _: self.ss.getServers())
        d.addCallback(lambda s: setattr(self, "s", s))
        d.addCallback(lambda _: self.failUnlessRaises(exceptions.StopIteration,
                                                      self.s.next))
        return d

    def testAddGoogle(self):

        def _checkAll(s):
            for i in s:
                pass
        d = self.ss.addServer("google.com", 80)
        d.addCallback(lambda _: self.ss.getServers())
        d.addCallback(lambda s: _checkAll(s))
        return d

    def testPriority(self):
        d1 = self.ss.addServer("flumotion.com", 80, 1.0)
        d2 = self.ss.addServer("localhost", 80, 2.0)
        d = defer.DeferredList([d1, d2])
        d.addCallback(lambda _: self.ss.getServers())
        d.addCallback(lambda s: setattr(self, "s", s))
        # first flumotion
        d.addCallback(lambda _: self.s.next())
        d.addCallback(lambda server: self.failIfEqual(server.ip, "127.0.0.1"))
        # then localhost
        d.addCallback(lambda _: self.s.next())
        d.addCallback(lambda server: self.assertEqual(server.ip, "127.0.0.1"))
        return d

    def testRefresh(self):
        self.tearDown()

        table = {"localhost": ["127.0.0.1", "10.0.0.1"],
                 "flumotion.com": ["1.1.1.1"]}
        self.ss = server_selection.ServerSelector(None, DummySocketDNS(table))
        self.ss.setup()

        d = self.ss.addServer("localhost", 80)
        d.addCallback(lambda _: self.ss.getServers())
        d.addCallback(lambda s: setattr(self, "s", s))
        d.addCallback(lambda _: self.s.next())
        d.addCallback(lambda server: self.failUnless(
                server.ip in ["127.0.0.1", "10.0.0.1"]))
        d.addCallback(lambda _: self.s.next())
        d.addCallback(lambda server: self.failUnless(
                server.ip in ["127.0.0.1", "10.0.0.1"]))

        table = {"localhost": ["127.0.0.1"]}
        d.addCallback(lambda _: setattr(self.ss._resolver, "socket",
                                        DummySocketDNS(table)))

        d.addCallback(lambda _: self.ss.refreshServers())
        d.addCallback(self._testHas, ["127.0.0.1"])

        table2 = {"localhost": ["127.0.0.1", "10.0.0.2"]}
        d.addCallback(lambda x: setattr(self.ss._resolver,
                                        "socket", DummySocketDNS(table2)))
        d.addCallback(lambda _: self.ss.refreshServers())
        d.addCallback(self._testHas, ["127.0.0.1", "10.0.0.2"])
        return d

    def _testTimeout(self):
        self.tearDown()
        self.ss = server_selection.ServerSelector(None, TimeoutSocketDNS())
        self.ss.setup()
        d = self.ss.addServer("localhost", 80)
        return d

    def _testHas(self, _, iplist):
        s = self.ss.getServers()
        for i in s:
            if len(iplist) == 0:
                break
            self.failUnless(i.ip in iplist)
            iplist.remove(i.ip)

        self.failUnlessRaises(exceptions.StopIteration, s.next)
        self.assertEqual(len(iplist), 0)

    def bp(self, result):
        import pdb
        print str(result)
        pdb.set_trace()
        return result


class DummySocketDNS:

    def __init__(self, table):
        self.table = table

    def gethostbyname_ex(self, hostname):
        if hostname not in self.table:
            raise Exception("unknown hostname")

        ipaddrlist = self.table[hostname]
        return (hostname, None, ipaddrlist)


class TimeoutSocketDNS:

    def gethostbyname_ex(self, hostname):
        time.sleep(300)
        return (None, None, None)


def delay(ret, t):
    d = defer.Deferred()
    reactor.callLater(t, d.callback, ret)
    return d
