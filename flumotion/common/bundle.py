# -*- Mode: Python; test-case-name: flumotion.test.test_bundle -*-
# vi:si:et:sw=4:sts=4:ts=4

# Flumotion - a video streaming server
# Copyright (C) 2004 Fluendo
#
# bundle.py: code to register sets of files for caching and transporting
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

"""
A class for a bundle of files used to implement caching over the network.
"""

import md5
import os
import zipfile
import StringIO

__all__ = ['Bundle']

# calculate the md5sum of the given file
# returns a 32 character string of hex characters
def _gen_md5sum(file):
    data = open(file.filename, "r").read()
    return md5.new(data).hexdigest()
    
# get the last changed timestamp of the given file
def _fetch_timestamp(file):
    return os.path.getmtime(file.filename)

class BundledFile:
    def __init__(self, filename, md5sum=None, timestamp=None):
        self.filename = filename
        self.md5sum = md5sum
        self.timestamp = timestamp
        self.zipped = False
        
class Bundle:
    """
    The bundle, which is a zip file with md5sum.
    """
    def __init__(self):
        self.zip = None
        self.md5sum = None

    def setZip(self, zip):
        """
        Set the bundle to the given data representation of the zip file.
        """
        self.zip = zip
        self.md5sum = md5.new(self.zip).hexdigest()

    def getZip(self):
        """
        Get the bundle's zip data.
        """
        return self.zip
        
class Unbundler:
    """
    I unbundle bundles by unpacking them in the given directory
    under directories with the bundle's md5sum.
    """
    def __init__(self, directory):
        self._undir = directory

    def unbundle(self, bundle):
        """
        Unbundle the given bundle.

        @type bundle: L{flumotion.common.bundle.Bundle}

        @rtype: string
        @rparam: the full path to the directory where it was unpacked
        """
        md5sum = bundle.md5sum
        print "THOMAS: unbundling bundle with md5sum %s" % md5sum
        dir = os.path.join(self._undir, md5sum)

        filelike = StringIO.StringIO(bundle.getZip())
        zip = zipfile.ZipFile(filelike, "r")
        zip.testzip()

        filepaths = zip.namelist()
        for filepath in filepaths:
            path = os.path.join(dir, filepath)
            parent = os.path.split(path)[0]
            try:
                os.makedirs(parent)
            except OSError, err:
                # Reraise error unless if it's an already existing
                if err.errno != errno.EEXIST or not os.path.isdir(parent):
                    raise
            data = zip.read(filepath)
            handle = open(path, 'wb')
            handle.write(data)
            handle.close()
        return dir
        
class Bundler:
    """
    A bundle of files useful to handle network caching of a set of files.
    """
    def __init__(self, *files):
        """
        Create a new bundle.

        @param files: list of files to register in the bundle.
        """
        self._files = {} # dictionary of files registered and md5sum/timestamp
        self._bundle = Bundle()
        
        self.add(*files)

    def add(self, *files):
        """
        Add files to the bundle.  The path will be stripped.
        """
        for filename in files:
            self._files[filename] = BundledFile(filename)
                
    def bundle(self):
        """
        Bundle the files registered with the bundler.

        @rtype: L{flumotion.common.bundle.Bundle}
        """
        # rescan files registered in the bundle, and check if we need to
        # rebuild the internal zip
        if not self._bundle.getZip():
            self._bundle.setZip(self._buildzip())
            return self._bundle

        update = False
        for file in self._files.values():
            if not file.zipped:
                update = True
            
            timestamp = _fetch_timestamp(file)
            if timestamp <= file.timestamp:
                continue
            file.timestamp = timestamp
                
            md5sum = _gen_md5sum(file)
            if file.md5sum != md5sum:
                file.md5sum = md5sum
                update = True
            
        if update:
            self._bundle.setZip(self._buildzip())

        return self._bundle
            
    # build the zip file containing the files registered in the bundle
    # and return the zip file data
    def _buildzip(self):
        filelike = StringIO.StringIO()
        zip = zipfile.ZipFile(filelike, "w")
        for file in self._files.keys():
            self._files[file].zipped = True
            name = os.path.split(file)[1]
            zip.write(file, name)
        zip.close()    
        data = filelike.getvalue()
        filelike.close()
        return data
    
