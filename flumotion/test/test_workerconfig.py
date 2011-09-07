# -*- Mode: Python; test-case-name:flumotion.test.test_workerconfig -*-
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
from flumotion.worker import config


def parse(string):
    return config.WorkerConfigXML(None, string)


class TestConfig(testsuite.TestCase):

    def testParseEmpty(self):
        conf = parse('<worker></worker>')
        self.assertEquals(conf.name, None)

    def testParseError(self):
        s = """<bad-root-node></bad-root-node>"""
        self.assertRaises(config.ConfigError, parse, s)

    def testParseWorkerName(self):
        conf = parse('<worker name="myname"></worker>')
        self.assertEquals(conf.name, 'myname')

    def testParseWorkerError(self):
        s = """<worker><invalid-name/></worker>"""
        self.assertRaises(config.ConfigError, parse, s)

    def testParseWorkerRandomFeederPorts(self):
        s = """<worker><feederports random="yes" /></worker>"""
        conf = parse(s)
        self.assertEquals(conf.feederports, [])
        self.assertEquals(conf.randomFeederports, True)

    def testParseWorkerFeederPorts(self):
        s = ('<worker><feederports random="no">'
             '1000-1002</feederports></worker>')
        conf = parse(s)
        self.assertEquals(conf.feederports, [1000, 1001, 1002])
        self.assertEquals(conf.randomFeederports, False)

    def testParseManager(self):
        conf = parse("""<worker><manager>
        <host>hostname</host>
        <port>9999</port>
        <transport>ssl</transport>
        </manager></worker>""")

        self.assertEquals(conf.manager.host, 'hostname')
        self.assertEquals(conf.manager.port, 9999)
        self.assertEquals(conf.manager.transport, 'ssl')

    def testParseManagerError(self):
        s = """<worker><manager><invalid-name/></manager></worker>"""
        self.assertRaises(config.ConfigError, parse, s)

        s = """<worker><manager><port>badport</port></manager></worker>"""
        self.assertRaises(config.ConfigError, parse, s)

        s = ('<worker><manager><transport>badtransport'
             '</transport></manager></worker>')
        self.assertRaises(config.ConfigError, parse, s)

    def testParseAuthentication(self):
        conf = parse("""<worker><authentication>
        <username>foobie</username>
        <password>boobie</password>
        </authentication></worker>""")

        self.assertEquals(conf.authentication.username, 'foobie')
        self.assertEquals(conf.authentication.password, 'boobie')

    def testParseAuthenticationError(self):
        s = ('<worker><authentication><invalid-name/>'
             '</authentication></worker>')
        self.assertRaises(config.ConfigError, parse, s)
