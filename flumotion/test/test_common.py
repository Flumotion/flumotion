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
import sys
import time
import tempfile

from twisted.trial import unittest
from twisted.spread import pb
from twisted.internet import reactor, address

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

class TestComponentPath(unittest.TestCase):
    def testPath(self):
        self.assertEqual(common.componentPath('Cain', 'Adam'), '/Adam/Cain')
        
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

class TestAddress(unittest.TestCase):
    def setUp(self):
        self.address = address.IPv4Address('TCP', 'localhost', '8000')
        
    def testGetHost(self):
        self.failUnlessEqual(common.addressGetHost(self.address), 'localhost')

    def testGetPort(self):
        self.failUnlessEqual(common.addressGetPort(self.address), '8000')

class TestPort(unittest.TestCase):
    def testCheckPortFree(self):
       factory = pb.PBServerFactory(pb.Root())
       p = reactor.listenTCP(0, factory, interface="127.0.0.1")
       port = common.addressGetPort(p.getHost())
       #reactor.callLater(0, self._print, p)
       #reactor.run()
       self.failIf(common.checkPortFree(port))
       self.failUnless(common.checkRemotePort('127.0.0.1', port))
       self.failUnless(common.checkRemotePort('localhost', port))
       self.failIf(common.getFirstFreePort(port) <= port)

       # run reactor and schedule the stop, which would stop the factory
       reactor.callLater(0, lambda: reactor.stop())
       reactor.run()
       self.failUnless(common.checkPortFree(port))
       self.failIf(common.checkRemotePort('127.0.0.1', port))
       self.failIf(common.checkRemotePort('localhost', port))
       self.failUnlessEqual(common.getFirstFreePort(port), port)

    def _print(self, p):
        print p, p.getHost()
        
class TestProcess(unittest.TestCase):
    def testTermPid(self):
        ret = os.fork()
        if ret == 0:
            # child
            time.sleep(4)
            os._exit(0)
        else:
            # parent
            self.failUnless(common.checkPidRunning(ret))
            self.failUnless(common.termPid(ret))
            os.waitpid(ret, 0)
            # now that it's gone, it should fail
            self.failIf(common.checkPidRunning(ret))
            self.failIf(common.termPid(ret))
            
    def testKillPid(self):
        ret = os.fork()
        if ret == 0:
            # child
            common.waitForTerm()
            os._exit(0)
        else:
            # parent
            self.failUnless(common.killPid(ret))
            os.waitpid(ret, 0)
            # now that it's gone, it should fail
            self.failIf(common.killPid(ret))

    def testKillPid(self):
        pid = os.getpid()

        ret = os.fork()
        if ret == 0:
            # child
            time.sleep(0.5)
            self.failUnless(common.termPid(pid))
            os._exit(0)
        else:
            # parent
            common.waitForTerm()
        
if __name__ == '__main__':
    unittest.main()
