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

"""
bundles of files used to implement caching over the network
"""

import errno
import md5
import os
import zipfile
import tempfile
import StringIO

from flumotion.common import errors, dag
from flumotion.common.python import makedirs

__all__ = ['Bundle', 'Bundler', 'Unbundler', 'BundlerBasket']
__version__ = "$Rev$"


class BundledFile:
    """
    I represent one file as managed by a bundler.
    """

    def __init__(self, source, destination):
        self.source = source
        self.destination = destination
        self._last_md5sum = None
        self._last_timestamp = None
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
        # FIXME: looks bogus, shouldn't this check be != instead of <= ?
        if self._last_timestamp and timestamp <= self._last_timestamp:
            return False
        self._last_timestamp = timestamp

        # if the md5sum has changed, it has changed
        md5sum = self.md5sum()
        if self._last_md5sum != md5sum:
            self._last_md5sum = md5sum
            return True

        return False

    def pack(self, zip):
        self._last_timestamp = self.timestamp()
        self._last_md5sum = self.md5sum()
        zip.write(self.source, self.destination)
        self.zipped = True


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
        directory = self.unbundlePath(bundle)

        filelike = StringIO.StringIO(bundle.getZip())
        zipFile = zipfile.ZipFile(filelike, "r")
        zipFile.testzip()

        filepaths = zipFile.namelist()
        for filepath in filepaths:
            path = os.path.join(directory, filepath)
            parent = os.path.split(path)[0]
            try:
                makedirs(parent)
            except OSError, err:
                # Reraise error unless if it's an already existing
                if err.errno != errno.EEXIST or not os.path.isdir(parent):
                    raise
            data = zipFile.read(filepath)

            # atomically write to path, see #373
            fd, tempname = tempfile.mkstemp(dir=parent)
            handle = os.fdopen(fd, 'wb')
            handle.write(data)
            handle.close()

            # os.rename on Win32 is not deleting the target file
            # if it exists, so remove it before
            if os.path.exists(path):
                os.unlink(path)
            os.rename(tempname, path)
        return directory


class Bundler:
    """
    I bundle files into a bundle so they can be cached remotely easily.
    """

    def __init__(self, name):
        """
        Create a new bundle.
        """
        self._bundledFiles = {} # dictionary of BundledFile's indexed on path
        self.name = name
        self._bundle = Bundle(name)

    def add(self, source, destination = None):
        """
        Add files to the bundle.

        @param source: the path to the file to add to the bundle.
        @param destination: a relative path to store this file in the bundle.
        If unspecified, this will be stored in the top level.

        @returns: the path the file got stored as
        """
        if destination == None:
            destination = os.path.split(source)[1]
        self._bundledFiles[source] = BundledFile(source, destination)
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
        for bundledFile in self._bundledFiles.values():
            if bundledFile.hasChanged():
                update = True
                break

        if update:
            self._bundle.setZip(self._buildzip())

        return self._bundle

    # build the zip file containing the files registered in the bundle
    # and return the zip file data

    def _buildzip(self):
        filelike = StringIO.StringIO()
        zipFile = zipfile.ZipFile(filelike, "w")
        for bundledFile in self._bundledFiles.values():
            bundledFile.pack(zipFile)
        zipFile.close()
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

        self._graph = dag.DAG()

    def add(self, bundleName, source, destination=None):
        """
        Add files to the bundler basket for the given bundle.

        @param bundleName: the name of the bundle this file is a part of
        @param source: the path to the file to add to the bundle
        @param destination: a relative path to store this file in the bundle.
        If unspecified, this will be stored in the top level
        """
        # get the bundler and create it if need be
        if not bundleName in self._bundlers:
            bundler = Bundler(bundleName)
            self._bundlers[bundleName] = bundler
        else:
            bundler = self._bundlers[bundleName]

        # add the file to the bundle and register
        location = bundler.add(source, destination)
        if location in self._files:
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

            package = ".".join(package.split('/')) # win32 fixme
            if package in self._imports:
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
        if not self._graph.hasNode(depender):
            self._graph.addNode(depender)
        for dep in dependencies:
            if not self._graph.hasNode(dep):
                self._graph.addNode(dep)
            self._graph.addEdge(depender, dep)

    def getDependencies(self, bundlerName):
        """
        Return names of all the dependencies of this bundle, including this
        bundle itself.
        The dependencies are returned in a correct depending order.
        """
        if not bundlerName in self._bundlers:
            raise errors.NoBundleError('Unknown bundle %s' % bundlerName)
        elif not self._graph.hasNode(bundlerName):
            return [bundlerName]
        else:
            return [bundlerName] + self._graph.getOffspring(bundlerName)

    def getBundlerByName(self, bundlerName):
        """
        Return the bundle by name, or None if not found.
        """
        if bundlerName in self._bundlers:
            return self._bundlers[bundlerName]
        return None

    def getBundlerNameByImport(self, importString):
        """
        Return the bundler name by import statement, or None if not found.
        """
        if importString in self._imports:
            return self._imports[importString]
        return None

    def getBundlerNameByFile(self, filename):
        """
        Return the bundler name by filename, or None if not found.
        """
        if filename in self._files:
            return self._files[filename]
        return None

    def getBundlerNames(self):
        """
        Get all bundler names.

        @rtype: list of str
        @returns: a list of all bundler names in this basket.
        """
        return self._bundlers.keys()


class MergedBundler(Bundler):
    """
    I am a bundler, with the extension that I can also bundle other
    bundlers.

    The effect is that when you call bundle() on a me, you get one
    bundle with a union of all subbundlers' files, in addition to any
    loose files that you added to me.
    """

    def __init__(self, name='merged-bundle'):
        Bundler.__init__(self, name)
        self._subbundlers = {}

    def addBundler(self, bundler):
        """Add to me all of the files managed by another bundler.

        @param bundler: The bundler whose files you want in this
        bundler.
        @type  bundler: L{Bundler}
        """
        if bundler.name not in self._subbundlers:
            self._subbundlers[bundler.name] = bundler
            for bfile in bundler._files.values():
                self.add(bfile.source, bfile.destination)

    def getSubBundlers(self):
        """
        @returns: A list of all of the bundlers that have been added to
        me.
        """
        return self._subbundlers.values()
