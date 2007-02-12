# -*- Mode: Python; test-case-name:flumotion.test.test_config -*-
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

from twisted.trial import unittest

from flumotion.common.netutils import ipv4StringToInt, ipv4IntToString
from flumotion.common.netutils import Network


class TestIpv4Parse(unittest.TestCase):
    def assertParseInvariant(self, ipv4String):
        self.assertEquals(ipv4IntToString(ipv4StringToInt(ipv4String)),
                          ipv4String)

    def testIpv4Parse(self):
        self.assertParseInvariant('0.0.0.1')
        self.assertParseInvariant('0.0.1.0')
        self.assertParseInvariant('0.1.0.0')
        self.assertParseInvariant('1.0.0.0')
        self.assertParseInvariant('0.10.0.10')
        self.assertParseInvariant('10.0.10.0')
        self.assertParseInvariant('192.168.10.1')
        self.assertParseInvariant('195.10.6.237')
        
    def testIpv4ParseString(self):
        self.assertEquals(ipv4StringToInt('0.0.0.1'), 1<<0)
        self.assertEquals(ipv4StringToInt('0.0.1.0'), 1<<8)
        self.assertEquals(ipv4StringToInt('0.1.0.0'), 1<<16)
        self.assertEquals(ipv4StringToInt('1.0.0.0'), 1<<24)

class TestNetwork(unittest.TestCase):
    def testName(self):
        self.assertEquals(Network().name, None)
        self.assertEquals(Network('foo').name, 'foo')

    def testAddRemove(self):
        net = Network()
        net.addSubnet('192.168.0.0', 24)
        net.addSubnet('192.168.1.0', 24)
        self.assertEquals(len(net), 2)
        net.removeSubnet('192.168.0.0', 24)
        net.removeSubnet('192.168.1.0', 24)
        self.assertEquals(len(net), 0)
        
    def testMatch(self):
        net = Network()

        self.failIf(net.match('192.168.1.0'))
        
        net.addSubnet('192.168.1.0', 24)

        self.failUnless(net.match('192.168.1.0'))
        self.failUnless(net.match('192.168.1.10'))
        self.failUnless(net.match('192.168.1.255'))
        
        self.failIf(net.match('192.168.0.255'))
        self.failIf(net.match('192.168.2.0'))

        net.addSubnet('192.168.2.0', 24)

        self.failIf(net.match('192.168.0.255'))
        self.failUnless(net.match('192.168.1.255'))
        self.failUnless(net.match('192.168.2.0'))

        net.removeSubnet('192.168.1.0', 24)
        net.removeSubnet('192.168.2.0', 24)

        self.failIf(net.match('192.168.1.0'))
        self.failIf(net.match('192.168.1.10'))
        self.failIf(net.match('192.168.1.255'))
        
        self.failIf(net.match('192.168.0.255'))
        self.failIf(net.match('192.168.2.0'))
