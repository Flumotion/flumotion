# -*- Mode: Python; test-case-name: flumotion.test.test_bundle -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# flumotion/test/test_bundle.py: regression test for flumotion.common.bundle
#
# Flumotion - a streaming media server
# Copyright (C) 2004 Fluendo (www.fluendo.com)

# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
# See "LICENSE.GPL" in the source distribution for more information.

# This program is also licensed under the Flumotion license.
# See "LICENSE.Flumotion" in the source distribution for more information.

from twisted.trial import unittest

from flumotion.common import bundle
import tempfile
import os
import StringIO
import zipfile
import md5
import time

class TestBundler(unittest.TestCase):
    # everything we need to set up the test environment
    def setUp(self):
        # create test file
        (handle, self.filename) = tempfile.mkstemp()
        os.write(handle, "this is a test file")
        os.close(handle)

        # create a bundle for it
        name = os.path.split(self.filename)[1]
        self.bundler = bundle.Bundler()
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
        assert newsum != sum
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
        assert not zip.testzip()
        data = zip.read(name)
        assert data
        assert md5sum == md5.new(data).hexdigest()

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
        handle = os.open(path, os.O_WRONLY)
        os.write(handle, "different bit of text")
        os.close(handle)
        b = self.bundler.bundle()
        newsum = b.md5sum

        assert newsum != sum
        os.unlink(path)

# we test the Unbundler using the Bundler, should be enough
class TestUnbundler(unittest.TestCase):

    def setUp(self):
        self.tempdir = tempfile.mkdtemp()

        # create test file
        (handle, self.filename) = tempfile.mkstemp()
        os.write(handle, "this is a test file")
        os.close(handle)

    def tearDown(self):
        os.system("rm -r %s" % self.tempdir)

    def testUnbundler(self):
        bundler = bundle.Bundler()
        bundler.add(self.filename)
        b = bundler.bundle()

        unbundler = bundle.Unbundler(self.tempdir)
        
        dir = unbundler.unbundle(b)

        # make sure it unpacked
        newfile = os.path.join(dir, self.filename)
        assert os.path.exists(newfile)

        # verify contents
        one = open(self.filename, "r").read()
        two = open(newfile, "r").read()
        assert one == two

    def testUnbundlerRelative(self):
        bundler = bundle.Bundler()
        bundler.add(self.filename, 'this/is/a/test.py')
        b = bundler.bundle()
        unbundler = bundle.Unbundler(self.tempdir)
        
        dir = unbundler.unbundle(b)

        # make sure it unpacked
        newfile = os.path.join(dir, 'this/is/a/test.py')
        assert os.path.exists(newfile)

        # verify contents
        one = open(self.filename, "r").read()
        two = open(newfile, "r").read()
        assert one == two
 
if __name__ == '__main__':
     unittest.main()
