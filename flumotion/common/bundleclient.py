# -*- Mode: Python; test-case-name: flumotion.test.test_bundleclient -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# Flumotion - a streaming media server
# Copyright (C) 2004,2005 Fluendo, S.L. (www.fluendo.com). All rights reserved.

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
Bundle fetching, caching, and importing utilities for clients using
bundled code and data
"""


from twisted.internet import error, defer
from twisted.python import rebuild

from flumotion.common import bundle, common, errors, log, package
from flumotion.configure import configure
from flumotion.twisted.defer import defer_generator_method


__all__ = ['BundleLoader']


class BundleLoader(log.Loggable):
    """
    foo
    """

    remote = None
    _unbundler = None

    def __init__(self, remote):
        self.remote = remote
        self._unbundler = bundle.Unbundler(configure.cachedir)

    def _callRemote(self, methodName, *args, **kwargs):
        """
        Call the given remote method on the manager-side Avatar.
        """
        if not self.remote:
            raise errors.ManagerNotConnectedError
        return self.remote.callRemote(methodName, *args, **kwargs)

    def getBundles(self, **kwargs):
        """
        Get and extract all bundles needed.
        Either one of bundleName, fileName or moduleName should be specified
        in **kwargs.

        @returns: a list of (bundleName, sum) tuples, in with lowest dependency
                  first.
        """
        # get sums for all bundles we need
        d = self._callRemote('getBundleSums', **kwargs)
        yield d

        # sums is a list of name, sum tuples, highest to lowest
        # figure out which bundles we're missing
        sums = d.value()
        self.debug('Got sums %r' % sums)
        toFetch = []
        import os
        for name, md5 in sums:
            path = os.path.join(configure.cachedir, name, md5)
            if os.path.exists(path):
                self.log(name + ' is up to date')
            else:
                self.log(name + ' needs fetching')
                toFetch.append(name)

        # ask for the missing bundles
        d = self._callRemote('getBundleZips', toFetch)
        yield d

        # unpack the new bundles
        result = d.value()
        for name in toFetch:
            if name not in result.keys():
                msg = "Missing bundle %s was not received" % name
                self.warning(msg)
                raise errors.NoBundleError(msg)

            b = bundle.Bundle(name)
            b.setZip(result[name])
            path = self._unbundler.unbundle(b)

        # register all package paths; to do so we need to reverse sums
        sums.reverse()
        for name, md5 in sums:
            self.log('registerPackagePath for %s' % name)
            path = os.path.join(configure.cachedir, name, md5)
            if not os.path.exists(path):
                self.warning("path %s for bundle %s does not exist",
                    path, name)
            else:
                package.getPackager().registerPackagePath(path, name)

        yield sums
    getBundles = defer_generator_method(getBundles)

    def loadModule(self, moduleName):
        """
        Load the module given by name.
        Sets up all necessary bundles to be able to load the module.

        @rtype:   L{twisted.internet.defer.Deferred}
        @returns: a deferred that will fire when the given module is loaded,
                  giving the loaded module.
        """
        
        # fool pychecker
        import os
        import sys

        self.debug('Loading module %s' % moduleName)

        # get sums for all bundles we need
        d = self.getBundles(moduleName=moduleName)
        yield d

        sums = d.value()
        self.debug('Got sums %r' % sums)

        # load up the module and return it
        __import__(moduleName, globals(), locals(), [])
        self.log('loaded module %s' % moduleName)
        yield sys.modules[moduleName]
    loadModule = defer_generator_method(loadModule)

    def getBundleByName(self, bundleName):
        """
        Get the given bundle locally.

        @rtype:   L{twisted.internet.defer.Deferred}
        @returns: a deferred that will fire when the given bundle is fetched,
                  giving the full local path where the bundle is extracted.
        """
        self.debug('Getting bundle %s' % bundleName)
        d = self.getBundles(bundleName=bundleName)
        yield d

        sums = d.value()
        name, md5 = sums[-1]
        import os
        path = os.path.join(configure.cachedir, name, md5)
        self.debug('Got bundle %s in %s' % (bundleName, path))
        yield path
    getBundleByName = defer_generator_method(getBundleByName)

    def getFile(self, fileName):
        """
        Do everything needed to get the given bundled file.

        Returns: a deferred returning the absolute path to a local copy
                 of the given file.
        """
        import os

        self.debug('Getting file %s' % fileName)
        d = self.getBundles(fileName=fileName)
        yield d

        sums = d.value()
        name, md5 = sums[-1]
        path = os.path.join(configure.cachedir, name, md5, fileName)
        if not os.path.exists(path):
            self.warning("path %s for file %s does not exist" % (
                path, fileName))

        yield path
    getFile = defer_generator_method(getFile)
        

