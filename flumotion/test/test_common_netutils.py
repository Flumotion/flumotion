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

import StringIO

from twisted.internet import address

from flumotion.common import testsuite
from flumotion.common.netutils import ipv4StringToInt, ipv4IntToString
from flumotion.common.netutils import RoutingTable
from flumotion.common.netutils import addressGetHost, addressGetPort


class TestIpv4Parse(testsuite.TestCase):
    def assertParseInvariant(self, ipv4String):
        self.assertEquals(ipv4IntToString(ipv4StringToInt(ipv4String)),
                          ipv4String)

    def assertParseFails(self, ipv4String):
        self.assertRaises(ValueError, ipv4StringToInt, ipv4String)

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

        self.assertParseFails('1.1.1.1.1')
        self.assertParseFails('1.1.1')
        self.assertParseFails('1.1.1.256')
        self.assertParseFails('1.1.1.-3')

class TestRoutingTable(testsuite.TestCase):
    def testAddRemove(self):
        net = RoutingTable()
        net.addSubnet('foo', '192.168.0.0', 24)
        net.addSubnet('foo', '192.168.1.0', 24)
        self.assertEquals(len(net), 2)
        net.removeSubnet('foo', '192.168.0.0', 24)
        net.removeSubnet('foo', '192.168.1.0', 24)
        self.assertEquals(len(net), 0)

    def testBasicRouting(self):
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

    def testIterHumanReadable(self):
        routes = [('foo', '192.168.1.0', 32),
                  ('bar', '192.168.1.0', 24)]
        net = RoutingTable()
        for route, ip, mask in routes:
            net.addSubnet(route, ip, mask)
        for expected, actual in zip(routes, net.iterHumanReadable()):
            self.assertEquals(expected, actual)

    def testRouteIteration(self):
        net = RoutingTable()

        net.addSubnet('foo', '192.168.1.0', 24)
        net.addSubnet('bar', '0.0.0.0', 0)

        # Now, an IP in 'foo' should iterate foo, bar, None.
        tests = [('192.168.1.1', ['foo', 'bar', None]),
                 ('203.10.7.20', ['bar', None])]

        for ip, expected in tests:
            results = [result for result in net.route_iter(ip)]
            self.assertEquals(expected, results)

    def testRoutingPrecedence(self):
        net = RoutingTable()

        def ar(ip, route):
            self.assertEquals(net.route(ip), route)

        net.addSubnet('foo', '192.168.1.0', 32)
        net.addSubnet('bar', '192.168.1.0', 24)

        self.assertRaises(ValueError,
                          net.addSubnet,
                          'baz', '192.168.1.0', 16)

        net.addSubnet('baz', '192.168.0.0', 16)

        ar('192.168.1.0', 'foo')
        ar('192.168.1.1', 'bar')
        ar('192.168.2.1', 'baz')

    def assertParseFailure(self, string, **kwargs):
        f = StringIO.StringIO(string)
        self.assertRaises(ValueError, RoutingTable.fromFile, f,
                          **kwargs)
        f.close()

    def assertParseEquals(self, string, routes, **kwargs):
        f = StringIO.StringIO(string)
        net = RoutingTable.fromFile(f, **kwargs)
        f.close()

        expectednet = RoutingTable()
        for route in routes:
            expectednet.addSubnet(*route)
        self.assertEquals(list(iter(net)),
                          list(iter(expectednet)))

    def testParseFromFile(self):
        self.assertParseFailure('bad line')
        self.assertParseFailure('# comment\n'
                                'bad line')
        self.assertParseFailure('bad line\n'
                                '# comment')
        self.assertParseFailure('192.168.1.1/10')
        self.assertParseFailure('192.168.1.1/10  ')
        self.assertParseFailure('192.168.1.1/100 foo')
        self.assertParseFailure('192.168.1.1000/32 foo')
        self.assertParseFailure('192.168.1.0/32 good\n'
                                '192.168.2.0/32')

        self.assertParseEquals('',
                               [])
        self.assertParseEquals('#comment\n'
                               '  ',
                               [])
        self.assertParseEquals('#comment\n'
                               '  \n'
                               '192.168.1.1/32 foo',
                               [('foo', '192.168.1.1', 32)])
        self.assertParseEquals('#comment\n'
                               '  \n'
                               '192.168.1.1/32 foo  bar   ',
                               [('foo  bar', '192.168.1.1', 32)])
        self.assertParseEquals('192.168.1.1/32',
                               [('foo', '192.168.1.1', 32)],
                               requireNames=False, defaultRouteName='foo')
        self.assertParseEquals('#comment\n'
                               '  \n'
                               '192.168.1.1/32 foo\n'
                               '#general\n'
                               '0.0.0.0/0 general',
                               [('foo', '192.168.1.1', 32),
                                ('general', '0.0.0.0', 0)])

    def assertRouteNamesOrder(self, string, routeNames):
        f = StringIO.StringIO(string)
        net = RoutingTable.fromFile(f)
        f.close()

        self.assertEquals(net.getRouteNames(), routeNames)

    def testRouteNamesOrder(self):
        self.assertRouteNamesOrder(
            '#comment\n'
            '  \n'
            '192.168.1.1/32 foo\n'
            '192.168.2.1/32 bar\n'
            '192.168.3.1/32 foo\n',
            ['foo', 'bar'])


class TestAddress(testsuite.TestCase):
    def setUp(self):
        self.address = address.IPv4Address('TCP', 'localhost', '8000')

    def testGetHost(self):
        self.failUnlessEqual(addressGetHost(self.address), 'localhost')

    def testGetPort(self):
        self.failUnlessEqual(addressGetPort(self.address), '8000')
