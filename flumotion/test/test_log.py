# -*- Mode: Python; test-case-name: flumotion.test.test_log -*-
# vi:si:et:sw=4:sts=4:ts=4

# Flumotion - a video streaming server
# Copyright (C) 2004 Fluendo
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Street #330, Boston, MA 02111-1307, USA.

from twisted.trial import unittest

from flumotion.common import errors
from flumotion.utils import log

class LogTester(log.Loggable):
    logCategory = 'testlog'

class LogFunctionTester(log.Loggable):
    def logFunction(self, message):
        return "override " + message

class TestLog(unittest.TestCase):
    def setUp(self):
        self.category = self.level = self.message = None
        self.tester = LogTester()

    # just test for parsing semi- or non-valid FLU_DEBUG variables
    def testFluDebug(self):
        log.setFluDebug(":5")
        log.setFluDebug("*")
        log.setFluDebug("5")

    # test for adding a log handler
    def handler(self, category, level, message):
        self.category = category
        self.level = level
        self.message = message

    def testLimitInvisible(self):
        log.setFluDebug("testlog:3")
        log.addLogHandler(self.handler)
        
        # log 2 we shouldn't get
        self.tester.log("not visible")
        assert not self.category
        assert not self.level
        assert not self.message
        
        self.tester.debug("not visible")
        assert not self.category
        assert not self.level
        assert not self.message

    def testLimitedVisible(self):
        log.setFluDebug("testlog:3")
        log.addLogHandler(self.handler)
        
        # log 3 we should get
        self.tester.info("visible")
        assert self.category == 'testlog'
        assert self.level == 'INFO'
        assert self.message == 'visible'
  
        self.tester.warning("also visible")
        assert self.category == 'testlog'
        assert self.level == 'WARN'
        assert self.message == 'also visible'
  
    def testLimitedError(self):
        log.setFluDebug("testlog:3")
        log.addLogHandler(self.handler)
        
        self.assertRaises(errors.SystemError, self.tester.error, "error")
        assert self.category == 'testlog'
        assert self.level == 'ERROR'
        assert self.message == 'error'

    def testLogHandlerLimitedLevels(self):
        log.setFluDebug("testlog:3")
        log.addLogHandler(self.handler)
        
        # now try debug and log again too
        log.setFluDebug("testlog:5")

        self.tester.debug("debug")
        assert self.category == 'testlog'
        assert self.level == 'DEBUG'
        assert self.message == 'debug'
  
        self.tester.log("log")
        assert self.category == 'testlog'
        assert self.level == 'LOG'
        assert self.message == 'log'

    # test that we get all log messages
    def testLogHandler(self):
        log.setFluDebug("testlog:3")
        log.addLogHandler(self.handler, limited=False)

        self.tester.log("visible")
        assert self.message == 'visible'

        self.tester.warning("also visible")
        assert self.message == 'also visible'

class TestOwnLogHandler(unittest.TestCase):
    def setUp(self):
        self.category = self.level = self.message = None
        self.tester = LogFunctionTester()

    def handler(self, category, level, message):
        self.category = category
        self.level = level
        self.message = message

    # test if our own log handler correctly mangles the message
    def testOwnLogHandlerLimited(self):
        log.setFluDebug("testlog:3")
        log.addLogHandler(self.handler, limited=False)
        
        self.tester.log("visible")
        assert self.message == 'override visible'
  
    def testLogHandlerAssertion(self):
        self.assertRaises(TypeError, log.addLogHandler, None)
  
if __name__ == '__main__':
     unittest.main()
