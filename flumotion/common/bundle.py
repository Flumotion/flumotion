# -*- Mode: Python; test-case-name: flumotion.test.test_bundle -*-
# vi:si:et:sw=4:sts=4:ts=4
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

# Headers in this file shall remain intact.

"""
bundles of files used to implement caching over the network
"""

import md5
import os
import errno
import zipfile
import StringIO

__all__ = ['Bundle', 'Bundler', 'Unbundler', 'BundlerBasket']

class BundledFile:
    """
    I represent one file as managed by a bundler.
    """
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
        
        # if it wasn't zipped yet, it needs zipping, so we pretend it
        # was changed
        # FIXME: move this out here
        if not self.zipped:
            return True
        
        timestamp = self.timestamp()
        # if file still has an old timestamp, it hasn't changed
        if timestamp <= self._last_timestamp:
            return False
        self._last_timestamp = timestamp
            
        # if the md5sum has changed, it has changed
        md5sum = self.md5sum()
        if self._last_md5sum != md5sum:
            self._last_md5sum = md5sum
            return True

        return False
     
class Bundle:
    """
    I am a bundle of files, represented by a zip file and md5sum.
    """
    def __init__(self, name):
        self.zip = None
        self.md5sum = None
        self.name = name

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

    def unbundlePathByInfo(self, name, md5sum):
        """
        Return the full path where a bundle with the given name and md5sum
        would be unbundled to.
        """
        return os.path.join(self._undir, name, md5sum)

    def unbundlePath(self, bundle):
        """
        Return the full path where this bundle will/would be unbundled to.
        """
        return self.unbundlePathByInfo(bundle.name, bundle.md5sum)

    def unbundle(self, bundle):
        """
        Unbundle the given bundle.

        @type bundle: L{flumotion.common.bundle.Bundle}

        @rtype: string
        @returns: the full path to the directory where it was unpacked
        """
        dir = self.unbundlePath(bundle)

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
    def __init__(self, name):
        """
        Create a new bundle.
        """
        self._files = {} # dictionary of BundledFile's indexed on path
        self.name = name
        self._bundle = Bundle(name)
        
    def add(self, source, destination = None):
        """
        Add files to the bundle.
        
        @param source: the path to the file to add to the bundle.
        @param destination: a relative path to store this file in in the bundle.
        If unspecified, this will be stored in the top level.

        @returns: the path the file got stored as
        """
        if destination == None:
            destination = os.path.split(source)[1]
        self._files[source] = BundledFile(source, destination)
        return destination
                
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

class BundlerBasket:
    """
    I manage bundlers that are registered through me.
    """
    def __init__(self):
        """
        Create a new bundler basket.
        """
        self._bundlers = {} # bundler name -> bundle
        
        self._files = {}        # filename          -> bundle name
        self._imports = {}      # import statements -> bundle name

        self._dependencies = {} # bundler name -> bundle names it depends on
        
    def add(self, bundleName, source, destination = None):
        """
        Add files to the bundler basket for the given bundle.
        
        @param bundleName: the name of the bundle this file is a part of
        @param source: the path to the file to add to the bundle
        @param destination: a relative path to store this file in in the bundle.
        If unspecified, this will be stored in the top level
        """
        # get the bundler and create it if need be
        if not bundleName in self._bundlers.keys():
            bundler = Bundler(bundleName)
            self._bundlers[bundleName] = bundler
        else:
            bundler = self._bundlers[bundleName]

        # add the file to the bundle and register
        location = bundler.add(source, destination)
        if self._files.has_key(location):
            raise Exception("Cannot add %s to bundle %s, already in %s" % (
                location, bundleName, self._files[location]))
        self._files[location] = bundleName

        # add possible imports from this file
        package = None
        if location.endswith('.py'):
            package = location[:-3]
        elif location.endswith('.pyc'):
            package = location[:-4]

        if package:
            if package.endswith('__init__'):
                package = os.path.split(package)[0]
                
            package = ".".join(package.split(os.pathsep))
            if self._imports.has_key(package):
                raise Exception("Bundler %s already has import %s" % (
                    bundleName, package))
            self._imports[package] = bundleName

    def depend(self, depender, *dependencies):
        """
        Make the given bundle depend on the other given bundles.

        @type depender: string
        @type dependencies: list of strings
        """
        # note that a bundler doesn't necessarily need to be registered yet
        if not depender in self._dependencies:
            self._dependencies[depender] = []
        for dep in dependencies:
            self._dependencies[depender].append(dep)

    def getDependencies(self, bundlerName):
        """
        Return names of all the dependencies of this bundle, including this
        bundle itself.
        The dependencies are returned in a correct depending order.
        """
        # FIXME: do we need to scrub duplicates at all ?
        # It probably doesn't hurt that bad to include them more than once;
        # worst problem is returning a zip file more than once in a request
        deps = [bundlerName, ]
        if self._dependencies.has_key(bundlerName):
            for dep in self._dependencies[bundlerName]:
                deps += self.getDependencies(dep)
        return deps

    def getBundlerByName(self, bundlerName):
        """
        Return the bundle by name, or None if not found.
        """
        if self._bundlers.has_key(bundlerName):
            return self._bundlers[bundlerName]
        return None

    def getBundlerNameByImport(self, importString):
        """
        Return the bundler name by import statement, or None if not found.
        """
        if self._imports.has_key(importString):
            return self._imports[importString]
        return None

    def getBundlerNameByFile(self, filename):
        """
        Return the bundler name by filename, or None if not found.
        """
        if self._files.has_key(filename):
            return self._files[filename]
        return None
