# -*- Mode: Python; test-case-name: flumotion.test.test_bundle -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# flumotion/common/bundle.py: register file sets for caching and transporting
#
# Flumotion - a streaming media server
# Copyright (C) 2004 Fluendo, S.L. (www.fluendo.com). All rights reserved.

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

"""
A class for a bundle of files used to implement caching over the network.
"""

import md5
import os
import errno
import zipfile
import StringIO

__all__ = ['Bundle', 'Bundler', 'Unbundler']

class BundledFile:
    def __init__(self, source, destination):
        self.source = source
        self.destination = destination
        self._last_md5sum = self.md5sum()
        self._last_timestamp = self.timestamp()
        self.zipped = False

    def md5sum(self):
        """
        Calculate the md5sum of the given file.

        @returns: the md5 sum a 32 character string of hex characters.
        """
        data = open(self.source, "r").read()
        return md5.new(data).hexdigest()

    def timestamp(self):
        """
        @returns: the last modified timestamp for the file.
        """
        return os.path.getmtime(self.source)

    def hasChanged(self):
        """
        Check if the file has changed since it was last checked.

        @rtype: boolean
        """
        
        # if it wasn't zipped yet, it needs zipping
        # FIXME: move this out here
        if not self.zipped:
            return True
        
        timestamp = self.timestamp()
        if timestamp <= self._last_timestamp:
            return False
        self._last_timestamp = timestamp
            
        md5sum = self.md5sum()
        if self._last_md5sum != md5sum:
            self._last_md5sum = md5sum
            return True

        return False
     
class Bundle:
    """
    I am a bundle of files, represented by a zip file and md5sum.
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
        @returns: the full path to the directory where it was unpacked
        """
        md5sum = bundle.md5sum
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
    I bundle files into a bundle so they can be cached remotely easily.
    """
    def __init__(self):
        """
        Create a new bundle.
        """
        self._files = {} # dictionary of BundledFile's indexed on path
        self._bundle = Bundle()
        
    def add(self, source, destination = None):
        """
        Add files to the bundle.
        
        @param source: the path to the file to add to the bundle.
        @param destination: a relative path to store this file in in the bundle.
        If unspecified, this will be stored in the top level.
        """
        if destination == None:
            destination = os.path.split(source)[1]
        self._files[source] = BundledFile(source, destination)
                
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
            if file.hasChanged():
                update = True
           
        if update:
            self._bundle.setZip(self._buildzip())

        return self._bundle
            
    # build the zip file containing the files registered in the bundle
    # and return the zip file data
    def _buildzip(self):
        filelike = StringIO.StringIO()
        zip = zipfile.ZipFile(filelike, "w")
        for path in self._files.keys():
            bf = self._files[path]
            self._files[path].zipped = True
            zip.write(bf.source, bf.destination)
        zip.close()    
        data = filelike.getvalue()
        filelike.close()
        return data
    
