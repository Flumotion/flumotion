# -*- Mode: Python; test-case-name: flumotion.test.test_common -*-
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

import os
import sys
import time
import tempfile

from twisted.trial import unittest
from twisted.spread import pb
from twisted.internet import reactor, address
from zope.interface import implements,Interface

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
    def testFractionalSecond(self):
        value = 1.1
        self.assertEquals(common.formatTime(value, fractional=2),
            "00:00:01.10")

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

class I1(Interface): pass
class I2(Interface): pass

class A:
    implements(I1)

class B:
    implements(I2)

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
        self.failUnless(common.version('abinary'))

    def test_versionTupleToString(self):
        self.assertEquals(common.versionTupleToString((1, )), "1")
        self.assertEquals(common.versionTupleToString((1, 2, )), "1.2")
        self.assertEquals(common.versionTupleToString((1, 2, 3, )), "1.2.3")
        self.assertEquals(common.versionTupleToString((1, 2, 3, 0,)), "1.2.3")
        self.assertEquals(common.versionTupleToString((1, 2, 3, 1,)), "1.2.3.1")

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
        self.assertEqual(common.componentId('Adam', 'Cain'), '/Adam/Cain')

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

class TestAddress(unittest.TestCase):
    def setUp(self):
        self.address = address.IPv4Address('TCP', 'localhost', '8000')

    def testGetHost(self):
        self.failUnlessEqual(common.addressGetHost(self.address), 'localhost')

    def testGetPort(self):
        self.failUnlessEqual(common.addressGetPort(self.address), '8000')

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

class TestObjRepr(unittest.TestCase):
    def testMe(self):
        self.assertEquals(common.objRepr(self),
            'flumotion.test.test_common.TestObjRepr')

class TestPathToModule(unittest.TestCase):
    def testPaths(self):
        tests = {
            'flumotion/common/common.py': 'flumotion.common.common',
            'flumotion/common/common.pyo': 'flumotion.common.common',
            'flumotion/common/__init__.pyc': 'flumotion.common',
            'flumotion/common': 'flumotion.common',
            'flumotion/configure/uninstalled.py.in': None,
        }

        for (path, module) in tests.items():
            self.assertEquals(common.pathToModuleName(path), module,
                "path %s did not give end module %s" % (path, module))

class TestCompareVersions(unittest.TestCase):
    def testBadVersion(self):
        self.assertRaises(ValueError, common.compareVersions, "no", "version")

    def testEquals(self):
        self.assertEquals(common.compareVersions("1.2.3", "1.2.3"), 0)
        self.assertEquals(common.compareVersions("1.2.3", "1.2.3.0"), 0)
        self.assertEquals(common.compareVersions("1.2.3.0", "1.2.3"), 0)

    def testSmaller(self):
        self.assertEquals(common.compareVersions("1", "2"), -1)
        self.assertEquals(common.compareVersions("1", "1.1"), -1)
        self.assertEquals(common.compareVersions("1.0", "1.1"), -1)
        self.assertEquals(common.compareVersions("1.2", "1.10"), -1)
        self.assertEquals(common.compareVersions("1.2.3.4", "1.2.3.5"), -1)
        self.assertEquals(common.compareVersions("1.2.3.4", "1.2.4.4"), -1)
        self.assertEquals(common.compareVersions("1.2.3.4", "1.3.3.4"), -1)

    def testBigger(self):
        self.assertEquals(common.compareVersions("2", "1"), 1)
        self.assertEquals(common.compareVersions("2.0", "1"), 1)
        self.assertEquals(common.compareVersions("2", "1.0"), 1)
        self.assertEquals(common.compareVersions("2.0", "1.0"), 1)
        self.assertEquals(common.compareVersions("2.1", "2.0"), 1)
        self.assertEquals(common.compareVersions("1.2.3.4", "1.2.3.3.0"), 1)

class InitA(common.InitMixin):
    def __init__(self):
        self.inited = []
        common.InitMixin.__init__(self, 3, 4, x=5, y=6)

class InitB(InitA):
    def init(self, *args, **kwargs):
        self.inited.append((InitB, args, kwargs))

class InitC(InitB):
    pass

class InitD(InitC):
    def init(self, *args, **kwargs):
        self.inited.append((InitD, args, kwargs))

class TestInitMixin(unittest.TestCase):
    def testInitA(self):
        self.assertEquals(InitA().inited, [])

    def testInitB(self):
        self.assertEquals(InitB().inited, [(InitB, (3, 4), {'x':5, 'y':6})])

    def testInitC(self):
        self.assertEquals(InitC().inited, [(InitB, (3, 4), {'x':5, 'y':6})])

    def testInitD(self):
        self.assertEquals(InitD().inited, [(InitB, (3, 4), {'x':5, 'y':6}),
                                           (InitD, (3, 4), {'x':5, 'y':6})])
