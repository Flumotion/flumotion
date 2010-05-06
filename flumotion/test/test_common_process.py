# -*- Mode: Python; test-case-name: flumotion.test.test_common -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# Flumotion - a streaming media server
# Copyright (C) 2004,2005,2006,2007,2008 Fluendo, S.L. (www.fluendo.com).
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

import os
import time

from flumotion.common.process import checkPidRunning, deletePidFile, getPid, \
     killPid, termPid, waitForTerm, waitPidFile, writePidFile
from flumotion.common.testsuite import attr, TestCase


class TestPid(TestCase):

    def testAll(self):
        pid = getPid('test', 'default')
        self.failIf(pid)
        writePidFile('test', 'default')
        waitPidFile('test', 'default')
        pid = getPid('test', 'default')
        self.assertEquals(os.getpid(), pid)
        deletePidFile('test', 'default')


class TestProcess(TestCase):

    @attr('slow')
    def testTermPid(self):
        ret = os.fork()
        if ret == 0:
            # child
            time.sleep(4)
            os._exit(0)
        else:
            # parent
            self.failUnless(checkPidRunning(ret))
            self.failUnless(termPid(ret))

            os.waitpid(ret, 0)

            # now that it's gone, it should fail
            self.failIf(checkPidRunning(ret))
            self.failIf(termPid(ret))

    def testKillPid(self):
        ret = os.fork()
        if ret == 0:
            # child
            waitForTerm()
            os._exit(0)
        else:
            # parent
            self.failUnless(killPid(ret))
            os.waitpid(ret, 0)
            # now that it's gone, it should fail
            self.failIf(killPid(ret))

    def test_checkPidRunning(self):
        # we should be running
        pid = os.getpid()
        self.failUnless(checkPidRunning(pid))

        # so should init as pid 1, but run as root
        self.failUnless(checkPidRunning(1))
