# -*- Mode: Python; test-case-name: flumotion.test.test_log -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# flumotion/test/test_log.py: regression test from flumotion.utils.log
#
# Flumotion - a streaming media server
# Copyright (C) 2004 Fluendo, S.L. (www.fluendo.com). All rights reserved.

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

from twisted.trial import unittest

from flumotion.common import errors, log

class LogTester(log.Loggable):
    logCategory = 'testlog'

class LogFunctionTester(log.Loggable):
    def logFunction(self, message):
        return "override " + message

class TestLog(unittest.TestCase):
    def setUp(self):
        self.category = self.level = self.message = None
        self.tester = LogTester()
        # we want to remove the default handler so it doesn't show up stuff
        log.reset()

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
