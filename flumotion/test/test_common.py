# -*- Mode: Python; test-case-name: flumotion.test.test_common -*-
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

import os
import tempfile

from twisted.trial import unittest

from flumotion.common import common

class TestFormatStorage(unittest.TestCase):
    def testBytes(self):
        value = 4
        assert common.formatStorage(value) == "4.00 "

    def testKibibyte(self):
        value = 1024
        assert common.formatStorage(value) == "1.02 k"
        assert common.formatStorage(value, 3) == "1.024 k"

    def testMegabyte(self):
        value = 1000 * 1000
        assert common.formatStorage(value) == "1.00 M"

    def testMebibyte(self):
        value = 1024 * 1024
        assert common.formatStorage(value) == "1.05 M"
        assert common.formatStorage(value, 3) == "1.049 M"
        assert common.formatStorage(value, 4) == "1.0486 M"

    def testGibibyte(self):
        value = 1024 * 1024 * 1024
        assert common.formatStorage(value, 4) == "1.0737 G"
    
    def testTebibyte(self):
        value = 1024 * 1024 * 1024 * 1024
        assert common.formatStorage(value, 4) == "1.0995 T"
    
    def testPebibyte(self):
        value = 1024 * 1024 * 1024 * 1024 * 1024
        assert common.formatStorage(value, 4) == "1.1259 P"
    
    def testExbibyte(self):
        value = 1024 * 1024 * 1024 * 1024 * 1024 * 1024
        assert common.formatStorage(value, 4) == "1.1529 E"

class TestFormatTime(unittest.TestCase):
    def testSecond(self):
        value = 1
        assert common.formatTime(value) == "00:00"

    def testMinuteSecond(self):
        value = 60 + 1
        assert common.formatTime(value) == "00:01"

    def testHourMinuteSecond(self):
        value = 60 * 60 + 60 + 2
        assert common.formatTime(value) == "01:01"

    def testDay(self):
        value = 60 * 60 * 24
        assert common.formatTime(value) == "1 day 00:00"

    def testDays(self):
        value = 60 * 60 * 24 * 2
        assert common.formatTime(value) == "2 days 00:00"
    
    def testWeek(self):
        value = 60 * 60 * 24 * 7
        assert common.formatTime(value) == "1 week 00:00"
    
    def testWeeks(self):
        value = 60 * 60 * 24 * 7 * 2
        assert common.formatTime(value) == "2 weeks 00:00"
    
    def testYear(self):
        value = 60 * 60 * 24 * 365
        assert common.formatTime(value) == "52 weeks 1 day 00:00"
    
    def testReallyLong(self):
        minute = 60
        hour = minute * 60
        day = hour * 24
        week = day * 7
        
        value = week * 291 + day * 5 + hour * 13 + minute * 5
        assert common.formatTime(value) == "291 weeks 5 days 13:05"

class I1: pass
class I2: pass

class A:
    __implements__ = (I1, )

class B:
    __implements__ = (I2, )
    
class C: pass

class TestMergeImplements(unittest.TestCase):
    def testTwoImplements(self):
        self.assertEquals(common.mergeImplements(A, B), (I1, I2))
        
    def testFirstWithout(self):
        self.assertEquals(common.mergeImplements(B, C), (I2, ))

    def testSecondWithout(self):
        self.assertEquals(common.mergeImplements(A, C), (I1, ))

    def testBothWithout(self):
        self.assertEquals(common.mergeImplements(C, C), ( ))
     
class TestVersion(unittest.TestCase):
    def testVersion(self):
        self.assert_(common.version('abinary'))

class TestArgRepr(unittest.TestCase):
    def testEmpty(self):
        self.assertEqual(common.argRepr(), '')
        
    def testArg(self):
        self.assertEqual(common.argRepr((1, '2')), "1, '2'")
        self.assertEqual(common.argRepr(((None,))), "None")

    def testKwargs(self):
        self.assertEqual(common.argRepr((), dict(foo='bar')), "foo='bar'")
        self.assertEqual(common.argRepr(((1,)), dict(foo='bar')), "1, foo='bar'")
        
class TestEnsureDir(unittest.TestCase):
    def testNonExisting(self):
        self.tempdir = tempfile.mkdtemp()
        os.system("rm -r %s" % self.tempdir)
        common.ensureDir(self.tempdir, "a description")
        os.system("rm -r %s" % self.tempdir)
    def testExisting(self):
        self.tempdir = tempfile.mkdtemp()
        common.ensureDir(self.tempdir, "a description")
        os.system("rm -r %s" % self.tempdir)

class TestPid(unittest.TestCase):
    def testAll(self):
        pid = common.getPid('test', 'default')
        self.failIf(pid)
        common.writePidFile('test', 'default')
        common.waitPidFile('test', 'default')
        pid = common.getPid('test', 'default')
        self.assertEquals(os.getpid(), pid)
        common.deletePidFile('test', 'default')

class TestPackagePath(unittest.TestCase):
    def testCurrent(self):
        self.tempdir = tempfile.mkdtemp()
        packagedir = os.path.join(self.tempdir, "package")
        os.mkdir(packagedir)
        handle = open(os.path.join(packagedir, "__init__.py"), "w")
        handle.close()
        common.registerPackagePath(self.tempdir)
        os.system("rm -r %s" % self.tempdir)
          
# FIXME: move to a separate module
#class TestRoot (pb.Root):
#    pass

class TestState:#unittest.TestCase):
    def runClient(self):
        f = pb.PBClientFactory()
        reactor.connectTCP("127.0.0.1", self.port, f)
        f.getRootObject().addCallbacks(self.connected, self.notConnected)
        self.id = reactor.callLater(10, self.timeOut)

    def runServer(self):
        factory = pb.PBServerFactory(TestRoot())
        factory.unsafeTracebacks = self.unsafeTracebacks
        p = reactor.listenTCP(0, factory, interface="127.0.0.1")

    def testState(self):
        self.runServer()
        self.runClient()
        reactor.run()

if __name__ == '__main__':
    unittest.main()
