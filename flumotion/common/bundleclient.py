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
        """
        # get sums for all bundles we need
        d = self._callRemote('getBundleSums', **kwargs)
        yield d

        # sums is a list of name, sum tuples
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
                self.log(name + ' needs updating')
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

        yield sums
    getBundles = defer_generator_method(getBundles)

    # FIXME: use getBundles and make sure basic admin client uses this
    def load_module(self, moduleName):
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
        d = self._callRemote('getBundleSums', moduleName=moduleName)
        yield d
        sums = d.value()
        self.debug('Got sums %r' % sums)

        # sums is a list of name, sum tuples
        # figure out which bundles we're missing
        toFetch = []
        for name, md5 in sums:
            path = os.path.join(configure.cachedir, name, md5)
            if os.path.exists(path):
                self.log(name + ' is up to date, registering package path')
                package.getPackager().registerPackagePath(path, name)
            else:
                self.log(name + ' needs updating')
                toFetch.append(name)

        d = self._callRemote('getBundleZips', toFetch)
        yield d
        result = d.value()

        self.debug('load_module: received %d zips' % len(result))
        for name in toFetch:
            if name not in result.keys():
                msg = "Missing bundle %s was not received" % name
                self.warning(msg)
                raise errors.NoBundleError(msg)

            b = bundle.Bundle(name)
            b.setZip(result[name])
            path = self._unbundler.unbundle(b)

            self.debug("registering bundle %s in path %s" % (name, path))
            package.getPackager().registerPackagePath(path, name)

        # load up the module and return it
        __import__(moduleName, globals(), locals(), [])
        self.log('loaded module %s' % moduleName)
        yield sys.modules[moduleName]
    load_module = defer_generator_method(load_module)

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
        name, md5 = sums[0]
        import os
        path = os.path.join(configure.cachedir, name, md5)
        self.debug('Got bundle %s in %s' % (bundleName, path))
        yield path
    getBundleByName = defer_generator_method(getBundleByName)
