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

from flumotion.common import errors
from flumotion.common import testsuite
from flumotion.component.base import http


class TestLogFilter(testsuite.TestCase):

    def testSimpleFilter(self):
        filterdef = "192.168.1.0/24"
        filter = http.LogFilter()
        filter.addIPFilter(filterdef)

        self.failUnless(filter.isInRange("192.168.1.200"))
        self.failIf(filter.isInRange("192.168.0.200"))

    def testComplexFilter(self):
        filterdefs = ["192.168.1.0/24", "127.0.0.1"]
        filter = http.LogFilter()
        filter.addIPFilter(filterdefs[0])
        filter.addIPFilter(filterdefs[1])

        self.failUnless(filter.isInRange("192.168.1.200"))
        self.failUnless(filter.isInRange("127.0.0.1"))
        self.failIf(filter.isInRange("192.168.0.200"))
        self.failIf(filter.isInRange("127.0.0.2"))

    def testParseFailure(self):
        filter = http.LogFilter()
        self.assertRaises(errors.ConfigError, filter.addIPFilter, "192.12")
        self.assertRaises(errors.ConfigError, filter.addIPFilter,
            "192.168.0.0/33")
        self.assertRaises(errors.ConfigError, filter.addIPFilter,
            "192.168.0.0/30/1")
