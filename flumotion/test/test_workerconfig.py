# -*- Mode: Python; test-case-name:flumotion.test.test_workerconfig -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# flumotion/test/test_worker.py: regression test for flumotion.worker.config
#
# Flumotion - a streaming media server
# Copyright (C) 2004 Fluendo (www.fluendo.com)

# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
# See "LICENSE.GPL" in the source distribution for more information.

# This program is also licensed under the Flumotion license.
# See "LICENSE.Flumotion" in the source distribution for more information.

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
