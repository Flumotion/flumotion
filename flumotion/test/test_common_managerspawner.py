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
import shutil

from flumotion.common.managerspawner import LocalManagerSpawner
from flumotion.common import testsuite
from flumotion.common.netutils import tryPort


class TestLocalManagerSpwaner(testsuite.TestCase):

    _port = tryPort()

    def checkProcessStatus(self, isRunning, runDir, logDir):
        import subprocess
        ps = subprocess.Popen("ps -ef | grep flumotion",
                shell=True, stdout=subprocess.PIPE)
        result = ps.stdout.read()
        for serviceName in ['manager', 'worker']:
            compStr = 'flumotion-%s --rundir=%s --logdir=%s'\
                    % (serviceName, runDir, logDir)
            if isRunning:
                self.assertNotEqual(result.find(compStr), -1)
            else:
                self.assertEqual(result.find(compStr), -1)
        ps.stdout.close()
        ps.wait()

    def testPort(self):
        spawner = LocalManagerSpawner(self._port)
        self.assertEquals(self._port, spawner.getPort())
        spawner = None
    testPort.skip = "Skip test"

    def testManagerStart(self):
        spawner = LocalManagerSpawner(self._port)

        def done(unused):
            self.assert_(os.path.exists(spawner.getRunDir()))
            self.assert_(os.path.exists(spawner.getConfDir()))
            self.assert_(os.path.exists(spawner.getLogDir()))
            self.checkProcessStatus(True,
                    spawner.getRunDir(),
                    spawner.getLogDir())
            return spawner.stop(True)

        d = spawner.start()
        d.addCallback(done)
        return d
    testManagerStart.skip = "Skip test"

    def testManagerStop(self):
        spawner = LocalManagerSpawner(self._port)
        runDir = spawner.getRunDir()
        confDir = spawner.getConfDir()
        logDir = spawner.getLogDir()

        def closeDone(unused):
            self.assert_(os.path.exists(runDir))
            self.assert_(os.path.exists(confDir))
            self.assert_(os.path.exists(logDir))
            self.checkProcessStatus(False, runDir, logDir)
            shutil.rmtree(spawner._path)

        def startDone(unused):
            self.checkProcessStatus(True, runDir, logDir)
            return spawner.stop(False)

        d =spawner.start()
        d.addCallback(startDone)
        d.addCallback(closeDone)
        return d
    testManagerStop.skip = "Skip test"

    def testManagerStopAndCleanUp(self):
        spawner = LocalManagerSpawner(self._port)
        runDir = spawner.getRunDir()
        confDir = spawner.getConfDir()
        logDir = spawner.getLogDir()

        def closeDone(unused):
            self.assert_(not os.path.exists(runDir))
            self.assert_(not os.path.exists(confDir))
            self.assert_(not os.path.exists(logDir))
            self.checkProcessStatus(False, runDir, logDir)

        def startDone(unused):
            return spawner.stop(True)

        d = spawner.start()
        d.addCallback(startDone)
        d.addCallback(closeDone)
        return d
    testManagerStopAndCleanUp.skip = "Skip test"
