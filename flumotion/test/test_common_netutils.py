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
from flumotion.common.netutils import RoutingTable


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

class TestRoutingTable(unittest.TestCase):
    def testAddRemove(self):
        net = RoutingTable()
        net.addSubnet('foo', '192.168.0.0', 24)
        net.addSubnet('foo', '192.168.1.0', 24)
        self.assertEquals(len(net), 2)
        net.removeSubnet('foo', '192.168.0.0', 24)
        net.removeSubnet('foo', '192.168.1.0', 24)
        self.assertEquals(len(net), 0)
        
    def testRoute(self):
        net = RoutingTable()

        def ar(ip, route):
            self.assertEquals(net.route(ip), route)

        ar('192.168.1.0', None)
        
        net.addSubnet('foo', '192.168.1.0', 24)

        ar('192.168.1.0', 'foo')
        ar('192.168.1.10', 'foo')
        ar('192.168.1.255', 'foo')

        ar('192.168.0.255', None)
        ar('192.168.2.0', None)

        net.addSubnet('foo', '192.168.2.0', 24)

        ar('192.168.0.255', None)
        ar('192.168.1.255', 'foo')
        ar('192.168.2.0', 'foo')

        net.removeSubnet('foo', '192.168.1.0', 24)
        net.removeSubnet('foo', '192.168.2.0', 24)

        ar('192.168.1.0', None)
        ar('192.168.1.10', None)
        ar('192.168.1.255', None)
        ar('192.168.0.255', None)
        ar('192.168.2.0', None)
