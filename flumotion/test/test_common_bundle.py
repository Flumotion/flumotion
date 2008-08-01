# -*- Mode: Python; test-case-name: flumotion.test.test_common_bundle -*-
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

from twisted.trial import unittest

from flumotion.common import testsuite

from flumotion.common import bundle
import tempfile
import os
import StringIO
import zipfile
import md5
import time


class TestBundler(testsuite.TestCase):
    # everything we need to set up the test environment

    def setUp(self):
        # create test file
        (handle, self.filename) = tempfile.mkstemp()
        os.write(handle, "this is a test file")
        os.close(handle)

        # create a bundle for it
        name = os.path.split(self.filename)[1]
        self.bundler = bundle.Bundler("test")
        self.bundler.add(self.filename, name)

    def tearDown(self):
        os.unlink(self.filename)

    # create a bundle of one file and check whether we get the correct
    # md5sum

    def testBundlerOneSum(self):
        b = self.bundler.bundle()
        sum = b.md5sum

    # create a bundle of two files and check the md5sum changed

    def testBundlerTwoSum(self):
        b = self.bundler.bundle()
        sum = b.md5sum

        (handle, path) = tempfile.mkstemp()
        os.write(handle, "a bit of text to test")
        os.close(handle)
        self.bundler.add(path)

        b = self.bundler.bundle()
        newsum = b.md5sum
        self.assertNotEquals(newsum, sum)
        os.unlink(path)

    # create a bundle of one file then unpack and check if it's the same

    def testBundlerOneFile(self):
        data = open(self.filename, "r").read()
        md5sum = md5.new(data).hexdigest()
        name = os.path.split(self.filename)[1]
        b = self.bundler.bundle()
        sum = b.md5sum
        zip = b.zip

        filelike = StringIO.StringIO(zip)
        zip = zipfile.ZipFile(filelike, "r")
        # None means no files were broken
        self.failIf(zip.testzip())
        data = zip.read(name)
        self.failUnless(data)
        self.assertEquals(md5sum, md5.new(data).hexdigest())

    # create a bundle of two files then update one of them and check
    # the md5sum changes

    def testBundlerTwoFiles(self):
        data = open(self.filename, "r").read()

        # create test file
        (handle, path) = tempfile.mkstemp()
        os.write(handle, "a bit of text to test")
        os.close(handle)
        self.bundler.add(path)
        b = self.bundler.bundle()

        sum = b.md5sum

        # change the test file
        time.sleep(1) # ... or the timestamp doesn't change

        # touch the file so the timestamp is updated, but file not changed
        os.system("touch %s" % path)
        b = self.bundler.bundle()

        time.sleep(1) # ... or the timestamp doesn't change
        handle = os.open(path, os.O_WRONLY)
        os.write(handle, "different bit of text")
        os.close(handle)
        b = self.bundler.bundle()
        newsum = b.md5sum

        self.assertNotEquals(newsum, sum)
        os.unlink(path)

# we test the Unbundler using the Bundler, should be enough


class TestUnbundler(testsuite.TestCase):

    def setUp(self):
        self.tempdir = tempfile.mkdtemp()

        # create test file
        (handle, self.filename) = tempfile.mkstemp()
        os.write(handle, "this is a test file")
        os.close(handle)

    def tearDown(self):
        os.system("rm -r %s" % self.tempdir)

    def testUnbundler(self):
        bundler = bundle.Bundler("test")
        bundler.add(self.filename)
        b = bundler.bundle()

        unbundler = bundle.Unbundler(self.tempdir)

        dir = unbundler.unbundle(b)

        # make sure it unpacked
        newfile = os.path.join(dir, self.filename)
        self.failUnless(os.path.exists(newfile))

        # verify contents
        one = open(self.filename, "r").read()
        two = open(newfile, "r").read()
        self.assertEquals(one, two)

    def testUnbundlerRelative(self):
        bundler = bundle.Bundler("test")
        bundler.add(self.filename, 'this/is/a/test.py')
        b = bundler.bundle()
        unbundler = bundle.Unbundler(self.tempdir)

        dir = unbundler.unbundle(b)

        # make sure it unpacked
        newfile = os.path.join(dir, 'this/is/a/test.py')
        self.failUnless(os.path.exists(newfile))

        # verify contents
        one = open(self.filename, "r").read()
        two = open(newfile, "r").read()
        self.assertEquals(one, two)


class TestBundlerBasket(testsuite.TestCase):
    # everything we need to set up the test environment

    def setUp(self):
        # create test files
        self.tempdir = tempfile.mkdtemp()


        self.packagedir = os.path.join(self.tempdir, 'package')
        os.mkdir(self.packagedir)
        self.packagefile = os.path.join(self.packagedir, '__init__.py')
        handle = open(self.packagefile, 'w')
        handle.write("print 'I am a package'")
        handle.close()

        self.pythonfile = os.path.join(self.tempdir, 'test.py')
        handle = open(self.pythonfile, 'w')
        handle.write("print 'I am a bit of python'")
        handle.close()

        self.pythoncfile = os.path.join(self.tempdir, 'test.pyc')
        handle = open(self.pythoncfile, 'w')
        handle.write("XXXX I am fake bytecode")
        handle.close()

        self.textfile = os.path.join(self.tempdir, 'text')
        handle = open(self.textfile, 'w')
        handle.write("I am a bit of text")
        handle.close()

    def testBundlerBasketAdd(self):
        basket = bundle.BundlerBasket()
        basket.add('test', self.pythonfile)
        basket.add('test', self.textfile)

    def testBundlerBasketAddUnique(self):
        basket = bundle.BundlerBasket()
        basket.add('test', self.pythonfile)
        # FIXME: proper exceptions ?
        self.assertRaises(Exception, basket.add, 'test', self.pythonfile)
        self.assertRaises(Exception, basket.add, 'test', self.pythoncfile)

    def testBundlerBasketPackage(self):
        basket = bundle.BundlerBasket()
        basket.add('package', self.packagefile, 'package/__init__.py')
        bundlerName = basket.getBundlerNameByImport("package")
        bundler = basket.getBundlerByName(bundlerName)
        self.failUnless(bundler)
        bundlerName = basket.getBundlerNameByFile("package/__init__.py")
        bundler2 = basket.getBundlerByName(bundlerName)
        self.failUnless(bundler2)
        self.assertEquals(bundler, bundler2)

    def testBundlerBasketName(self):
        basket = bundle.BundlerBasket()
        basket.add('test', self.pythonfile, "test.py")
        bundler = basket.getBundlerByName("notexist")
        self.failIf(bundler)
        bundler = basket.getBundlerByName("test")
        self.failUnless(bundler)
        names = basket.getBundlerNames()
        self.assertEquals(names, ['test'])

    def testBundlerBasketFile(self):
        basket = bundle.BundlerBasket()
        basket.add('test', self.pythonfile, "test.py")
        bundlerName = basket.getBundlerNameByFile("notexist.py")
        self.failIf(bundlerName)
        bundler = basket.getBundlerByName(bundlerName)
        self.failIf(bundler)
        bundlerName = basket.getBundlerNameByFile("test.py")
        bundler = basket.getBundlerByName(bundlerName)
        self.failUnless(bundler)

    def testBundlerBasketImport(self):
        basket = bundle.BundlerBasket()
        basket.add('test', self.pythonfile, "test.py")
        bundlerName = basket.getBundlerNameByImport("notexist")
        self.failIf(bundlerName)
        bundler = basket.getBundlerByName(bundlerName)
        self.failIf(bundler)
        bundlerName = basket.getBundlerNameByImport("test")
        bundler = basket.getBundlerByName(bundlerName)
        self.failUnless(bundler)

    def testBundlerBasketDepend(self):
        basket = bundle.BundlerBasket()
        basket.depend('leg', 'foot')
        basket.depend('arm', 'hand')
        basket.depend('body', 'leg', 'arm')
        for i in 'leg', 'foot', 'arm', 'hand', 'body':
            basket._bundlers[i] = True
        deps = basket.getDependencies('body')
        deps.sort()
        list = ['leg', 'foot', 'arm', 'hand', 'body']
        list.sort()
        self.assertEquals(list, deps)

    def tearDown(self):
        os.unlink(self.packagefile)
        os.rmdir(self.packagedir)

        os.unlink(self.pythonfile)
        os.unlink(self.pythoncfile)
        os.unlink(self.textfile)
        os.rmdir(self.tempdir)

if __name__ == '__main__':
    unittest.main()
