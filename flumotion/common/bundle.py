# -*- Mode: Python -*-
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
    A bundle of files useful to handle network caching of a set of files.
    """
    def __init__(self, *files):
        """
        Create a new bundle.

        @param files: list of files to register in the bundle.
        """
        self._files = {} # dictionary of files registered and md5sum/timestamp
        self._zip = None # contents of the zip file for this bundle
        self._md5sum = None # md5sum for the bundle
        
        self.add(*files)

    def add(self, *files):
        """
        Add files to the bundle.  The path will be stripped.
        """
        for filename in files:
            self._files[filename] = BundledFile(filename)
                
    def zip(self):
        """
        Return the contents of a zip file representing this bundle.
        """
        self._update()
        return self._zip

    def md5sum(self):
        """
        Return the 32 character hex md5sum of the zip file for this bundle.
        """
        self._update()
        return md5.new(self._zip).hexdigest()

    ### private methods
    
    # rescan files registered in the bundle, and check if we need to
    # rebuild the internal zip, returns True if it was updated
    def _update(self):
        if not self._zip:
            self._buildzip()
            return True

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
            self._buildzip()
            
        return update
            
    # build the zip file containing the files registered in the bundle
    def _buildzip(self):
        filelike = StringIO.StringIO()
        zip = zipfile.ZipFile(filelike, "w")
        for file in self._files.keys():
            self._files[file].zipped = True
            name = os.path.split(file)[1]
            zip.write(file, name)
        zip.close()    
        self._zip = filelike.getvalue()
        filelike.close()
    
