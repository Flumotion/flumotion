# -*- Mode: Python; test-case-name: flumotion.test.test_bundle -*-
# vi:si:et:sw=4:sts=4:ts=4

# Flumotion - a video streaming server
# Copyright (C) 2004 Fluendo
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Street #330, Boston, MA 02111-1307, USA.

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
        self.filename = __file__
        self.bundler = bundle.Bundler(self.filename)

    # create a bundle of one file and check whether we get the correct
    # md5sum
    def testBundlerOneSum(self):
        bundle = self.bundler.bundle()
        sum = bundle.md5sum

    # create a bundle of two files and check the md5sum changed
    def testBundlerTwoSum(self):
        bundle = self.bundler.bundle()
        sum = bundle.md5sum
        
        (handle, path) = tempfile.mkstemp()
        os.write(handle, "a bit of text to test")
        os.close(handle)
        self.bundler.add(path)

        bundle = self.bundler.bundle()
        newsum = bundle.md5sum
        assert newsum != sum
        os.unlink(path)

    # create a bundle of one file then unpack and check if it's the same
    def testBundlerOneFile(self):
        data = open(self.filename, "r").read()
        md5sum = md5.new(data).hexdigest()
        name = os.path.split(self.filename)[1]
        bundle = self.bundler.bundle()
        sum = bundle.md5sum
        zip = bundle.zip

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
        bundle = self.bundler.bundle()
        sum = bundle.md5sum

        # change the test file
        time.sleep(1) # ... or the timestamp doesn't change
        handle = os.open(path, os.O_WRONLY)
        os.write(handle, "different bit of text")
        os.close(handle)
        bundle = self.bundler.bundle()
        newsum = bundle.md5sum

        assert newsum != sum
        os.unlink(path)

# we test the Unbundler using the Bundler, should be enough
class TestUnbundler(unittest.TestCase):
    # everything we need to set up the test environment
    def setUp(self):
        self.filename = __file__
        self.bundler = bundle.Bundler(self.filename)
        self.bundle = self.bundler.bundle()

    def testUnbundler(self):
        path = tempfile.mkdtemp()
        unbundler = bundle.Unbundler(path)
        
        unbundler.unbundle(self.bundle)

        # make sure it unpacked
        newfile = os.path.join(path, self.filename)
        assert os.path.exists(newfile)

        # verify contents
        one = open(self.filename, "r").read()
        two = open(newfile, "r").read()
        assert one == two
        
if __name__ == '__main__':
     unittest.main()
