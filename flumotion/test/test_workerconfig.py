# -*- Mode: Python; test-case-name:flumotion.test.test_workerconfig -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# Flumotion - a streaming media server
# Copyright (C) 2004,2005 Fluendo, S.L. (www.fluendo.com). All rights reserved.

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

from twisted.trial import unittest

from flumotion.worker import config

def parse(string):
    return config.WorkerConfigXML(None, string)

class TestConfig(unittest.TestCase):
    def testParseEmpty(self):
        conf = parse('<worker></worker>')
        self.assert_(conf.name == 'default')
        
    def testParseError(self):
        s = """<bad-root-node></bad-root-node>"""
        self.assertRaises(config.ConfigError, parse, s)
        
    def testParseWorkerName(self):
        conf = parse('<worker name="myname"></worker>')
        self.assert_(conf.name == 'myname')

    def testParseWorkerError(self):
        s = """<worker><invalid-name/></worker>"""
        self.assertRaises(config.ConfigError, parse, s)

    def testParseManager(self):
        conf = parse("""<worker><manager>
        <host>hostname</host>
        <port>9999</port>
        <transport>ssl</transport>
        </manager></worker>""")
        
        self.assert_(conf.manager.host == 'hostname')
        self.assert_(conf.manager.port == 9999)
        self.assert_(conf.manager.transport == 'ssl')

    def testParseManagerError(self):
        s = """<worker><manager><invalid-name/></manager></worker>"""
        self.assertRaises(config.ConfigError, parse, s)
        
        s = """<worker><manager><port>badport</port></manager></worker>"""
        self.assertRaises(config.ConfigError, parse, s)

        s = """<worker><manager><transport>badtransport</transport></manager></worker>"""
        self.assertRaises(config.ConfigError, parse, s)
        
    def testParseAuthentication(self):
        conf = parse("""<worker><authentication>
        <username>foobie</username>
        <password>boobie</password>
        </authentication></worker>""")
        
        self.assert_(conf.authentication.username == 'foobie')
        self.assert_(conf.authentication.password == 'boobie')


    def testParseAuthenticationError(self):
        s = """<worker><authentication><invalid-name/></authentication></worker>"""
        self.assertRaises(config.ConfigError, parse, s)
