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
import tempfile

from flumotion.common import common
from flumotion.common import testsuite


class TestVersion(testsuite.TestCase):
    def testVersion(self):
        self.failUnless(common.version('abinary'))

    def test_versionTupleToString(self):
        self.assertEquals(common.versionTupleToString((1, )), "1")
        self.assertEquals(common.versionTupleToString((1, 2, )), "1.2")
        self.assertEquals(common.versionTupleToString((1, 2, 3, )), "1.2.3")
        self.assertEquals(common.versionTupleToString((1, 2, 3, 0, )), "1.2.3")
        self.assertEquals(common.versionTupleToString((1, 2, 3, 1, )),
                          "1.2.3.1")


class TestComponentPath(testsuite.TestCase):
    def testPath(self):
        self.assertEqual(common.componentId('Adam', 'Cain'), '/Adam/Cain')


class TestEnsureDir(testsuite.TestCase):
    def testNonExisting(self):
        self.tempdir = tempfile.mkdtemp()
        os.system("rm -r %s" % self.tempdir)
        common.ensureDir(self.tempdir, "a description")
        os.system("rm -r %s" % self.tempdir)
    def testExisting(self):
        self.tempdir = tempfile.mkdtemp()
        common.ensureDir(self.tempdir, "a description")
        os.system("rm -r %s" % self.tempdir)


class TestObjRepr(testsuite.TestCase):
    def testMe(self):
        self.assertEquals(common.objRepr(self),
            'flumotion.test.test_common.TestObjRepr')


class TestPathToModule(testsuite.TestCase):
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


class TestCompareVersions(testsuite.TestCase):
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


class TestInitMixin(testsuite.TestCase):
    def testInitA(self):
        self.assertEquals(InitA().inited, [])

    def testInitB(self):
        self.assertEquals(InitB().inited, [(InitB, (3, 4), {'x':5, 'y':6})])

    def testInitC(self):
        self.assertEquals(InitC().inited, [(InitB, (3, 4), {'x':5, 'y':6})])

    def testInitD(self):
        self.assertEquals(InitD().inited, [(InitB, (3, 4), {'x':5, 'y':6}),
                                           (InitD, (3, 4), {'x':5, 'y':6})])
