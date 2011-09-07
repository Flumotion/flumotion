# -*- Mode: Python; test-case-name: flumotion.test.test_options -*-
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
from flumotion.common.options import OptionGroup, OptionParser
from flumotion.common.log import getLogSettings, setLogSettings


class TestOptions(testsuite.TestCase):

    def setUp(self):
        self.log_settings = getLogSettings()

    def tearDown(self):
        setLogSettings(self.log_settings)

    def testParser(self):
        parser = OptionParser()

        options, rest = parser.parse_args(['--verbose'])
        self.failUnless(options.verbose)
        self.failIf(rest)

        options, rest = parser.parse_args(['--debug', '*:5'])
        self.assertEqual(options.debug, "*:5")
        self.failIf(rest)

        options, rest = parser.parse_args(['rest'])
        self.assertEqual(rest, ["rest"])

    def testGroup(self):
        parser = OptionParser()

        group = OptionGroup(parser, "group")
        group.add_option('-t', '--test', action="store_true", dest="test")

        parser.add_option_group(group)


        options, rest = parser.parse_args([])
        self.failIf(options.test)
        self.failIf(rest)

        options, rest = parser.parse_args(['--test'])
        self.failUnless(options.test)
        self.failIf(rest)

        options, rest = parser.parse_args(['--test', '--verbose', 'rest'])
        self.failUnless(options.test)
        self.failUnless(options.verbose)
        self.assertEqual(rest, ["rest"])
