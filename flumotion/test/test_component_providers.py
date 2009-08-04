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
import shutil
import tempfile

from flumotion.common import testsuite
from flumotion.component.misc.httpserver import localpath
from flumotion.component.misc.httpserver import localprovider
from flumotion.component.misc.httpserver import cachedprovider
from flumotion.component.misc.httpserver.fileprovider \
    import InsecureError, NotFoundError, CannotOpenError


class LocalPath(testsuite.TestCase):

    def setUp(self):
        self.path = tempfile.mkdtemp(suffix=".flumotion.test")
        a = os.path.join(self.path, 'a')
        open(a, "w").write('test file a')
        B = os.path.join(self.path, 'B')
        os.mkdir(B)
        c = os.path.join(self.path, 'B', 'c')
        open(c, "w").write('test file c')

    def tearDown(self):
        shutil.rmtree(self.path, ignore_errors=True)

    def testExistingPath(self):
        local = localpath.LocalPath(self.path)
        self.assertIsInstance(local, localpath.LocalPath)

    def testChildExistingFile(self):
        child = localpath.LocalPath(self.path).child('a')
        self.assertIsInstance(child, localpath.LocalPath)

    def testChildExistingDir(self):
        child = localpath.LocalPath(self.path).child('B')
        self.assertIsInstance(child, localpath.LocalPath)

    def testChildTraversingDir(self):
        local = localpath.LocalPath(self.path)
        child = local.child('B').child('c')
        self.assertIsInstance(child, localpath.LocalPath)

    def testChildNonExistingFile(self):
        child = localpath.LocalPath(self.path).child('foo')
        self.assertIsInstance(child, localpath.LocalPath)

    def testChildTraversingNonExistingDir(self):
        local = localpath.LocalPath(self.path)
        child = local.child('foo').child('bar')
        self.assertIsInstance(child, localpath.LocalPath)

    def testChildInsecurePathTooDeep(self):
        local = localpath.LocalPath(self.path)
        self.assertRaises(InsecureError, local.child, 'B/c')

    def testChildInsecurePathTooDeepAndNonExisting(self):
        local = localpath.LocalPath(self.path)
        self.assertRaises(InsecureError, local.child, 'foo/bar')

    def testChildInsecurePathRoot(self):
        local = localpath.LocalPath(self.path)
        self.assertRaises(InsecureError, local.child, '/foo')

    def testChildInsecurePathUp(self):
        local = localpath.LocalPath(self.path)
        self.assertRaises(InsecureError, local.child, '..')


class LocalPathCachedProvider(testsuite.TestCase):

    def setUp(self):
        self.path = tempfile.mkdtemp(suffix=".flumotion.test")
        a = os.path.join(self.path, 'a')
        open(a, "w").write('test file a')
        B = os.path.join(self.path, 'B')
        os.mkdir(B)
        c = os.path.join(self.path, 'B', 'c')
        open(c, "w").write('test file c')

        plugProps = {"properties": {"path": self.path}}
        self.fileProviderPlug = \
            cachedprovider.FileProviderLocalCachedPlug(plugProps)

    def tearDown(self):
        shutil.rmtree(self.path, ignore_errors=True)

    def testExistingPath(self):
        local = self.fileProviderPlug.getRootPath()
        self.assertIsInstance(local, cachedprovider.LocalPath)

    def testChildExistingFile(self):
        child = self.fileProviderPlug.getRootPath().child('a')
        self.assertIsInstance(child, localpath.LocalPath)

    def testChildExistingDir(self):
        child = self.fileProviderPlug.getRootPath().child('B')
        self.assertIsInstance(child, localpath.LocalPath)

    def testChildTraversingDir(self):
        local = self.fileProviderPlug.getRootPath()
        child = local.child('B').child('c')
        self.assertIsInstance(child, localpath.LocalPath)

    def testChildNonExistingFile(self):
        child = self.fileProviderPlug.getRootPath().child('foo')
        self.assertIsInstance(child, localpath.LocalPath)

    def testChildTraversingNonExistingDir(self):
        local = self.fileProviderPlug.getRootPath()
        child = local.child('foo').child('bar')
        self.assertIsInstance(child, localpath.LocalPath)

    def testChildInsecurePathTooDeep(self):
        local = self.fileProviderPlug.getRootPath()
        self.assertRaises(InsecureError, local.child, 'B/c')

    def testChildInsecurePathTooDeepAndNonExisting(self):
        local = self.fileProviderPlug.getRootPath()
        self.assertRaises(InsecureError, local.child, 'foo/bar')

    def testChildInsecurePathRoot(self):
        local = self.fileProviderPlug.getRootPath()
        self.assertRaises(InsecureError, local.child, '/foo')

    def testChildInsecurePathUp(self):
        local = self.fileProviderPlug.getRootPath()
        self.assertRaises(InsecureError, local.child, '..')

    def testOpenExisting(self):
        child = self.fileProviderPlug.getRootPath().child('a')
        child.open()

    def testOpenTraversingExistingDir(self):
        local = self.fileProviderPlug.getRootPath()
        child = local.child('B').child('c')
        child.open()

    def testOpendir(self):
        local = self.fileProviderPlug.getRootPath()
        self.assertRaises(CannotOpenError, local.open)

    def testOpenNonExisting(self):
        local = self.fileProviderPlug.getRootPath()
        child = local.child('foo')
        self.assertRaises(NotFoundError, child.open)

    def testOpenTraversingNonExistingDir(self):
        local = self.fileProviderPlug.getRootPath()
        child = local.child('foo').child('bar')
        self.assertRaises(NotFoundError, child.open)


class LocalPathLocalProvider(testsuite.TestCase):

    def setUp(self):
        self.path = tempfile.mkdtemp(suffix=".flumotion.test")
        a = os.path.join(self.path, 'a')
        open(a, "w").write('test file a')
        B = os.path.join(self.path, 'B')
        os.mkdir(B)
        c = os.path.join(self.path, 'B', 'c')
        open(c, "w").write('test file c')
        self.local = localprovider.LocalPath(self.path)

    def tearDown(self):
        shutil.rmtree(self.path, ignore_errors=True)

    def testOpenExisting(self):
        child = self.local.child('a')
        child.open()

    def testOpenTraversingExistingDir(self):
        child = self.local.child('B').child('c')
        child.open()

    def testOpendir(self):
        self.assertRaises(CannotOpenError, self.local.open)

    def testOpenNonExisting(self):
        child = self.local.child('foo')
        self.assertRaises(NotFoundError, child.open)

    def testOpenTraversingNonExistingDir(self):
        child = self.local.child('foo').child('bar')
        self.assertRaises(NotFoundError, child.open)
