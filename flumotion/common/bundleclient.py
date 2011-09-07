# -*- Mode: Python; test-case-name: flumotion.test.test_bundleclient -*-
# vi:si:et:sw=4:sts=4:ts=4

# Flumotion - a streaming media server
# Copyright (C) 2004,2005,2006,2007,2008,2009 Fluendo, S.L.
# Copyright (C) 2010,2011 Flumotion Services, S.A.
# All rights reserved.
#
# This file may be distributed and/or modified under the terms of
# the GNU Lesser General Public License version 2.1 as published by
# the Free Software Foundation.
# This file is distributed without any warranty; without even the implied
# warranty of merchantability or fitness for a particular purpose.
# See "LICENSE.LGPL" in the source distribution for more information.
#
# Headers in this file shall remain intact.

"""bundle interface for fetching, caching and importing
"""

import os
import sys

from flumotion.common import bundle, errors, log, package
from flumotion.configure import configure

__all__ = ['BundleLoader']
__version__ = "$Rev$"


class BundleLoader(log.Loggable):
    """
    I am an object that can get and set up bundles from a PB server.

    @cvar remote: a remote reference to an avatar on the PB server.
    """
    remote = None
    _unbundler = None

    def __init__(self, callRemote):
        """
        @type  callRemote: callable
        """
        self.callRemote = callRemote
        self._unbundler = bundle.Unbundler(configure.cachedir)

    def getBundles(self, **kwargs):
        # FIXME: later on, split out this method into getBundles which does
        # not call registerPackagePath, and setupBundles which calls getBundles
        # and register.  Then change getBundles calls to setupBundles.
        """
        Get, extract and register all bundles needed.
        Either one of bundleName, fileName or moduleName should be specified
        in **kwargs, which should be strings or lists of strings.

        @returns: a deferred firing a a list of (bundleName, bundlePath)
                  tuples, with lowest dependency first.
                  bundlePath is the directory to register
                  for this package.
        """

        def annotated(d, *extraVals):

            def annotatedReturn(ret):
                return (ret, ) + extraVals
            d.addCallback(annotatedReturn)
            return d

        def getZips(sums):
            # sums is a list of name, sum tuples, highest to lowest
            # figure out which bundles we're missing
            toFetch = []
            for name, md5 in sums:
                path = os.path.join(configure.cachedir, name, md5)
                if os.path.exists(path):
                    self.log('%s is up to date', name)
                else:
                    self.log('%s needs fetching', name)
                # FIXME: We cannot be completelly sure the bundle has the
                # correct content only by checking that the directory exists.
                # The worker/manager could have died during a download leaving
                # the package incomplete.
                toFetch.append(name)
            if toFetch:
                return annotated(self.callRemote('getBundleZips', toFetch),
                                 toFetch, sums)
            else:
                return {}, [], sums

        def unpackAndRegister((zips, toFetch, sums)):
            for name in toFetch:
                if name not in zips:
                    msg = "Missing bundle %s was not received"
                    self.warning(msg, name)
                    raise errors.NoBundleError(msg % name)

                b = bundle.Bundle(name)
                b.setZip(zips[name])
                path = self._unbundler.unbundle(b)

            # register all package paths; to do so we need to reverse sums
            sums.reverse()
            ret = []
            for name, md5 in sums:
                self.log('registerPackagePath for %s' % name)
                path = os.path.join(configure.cachedir, name, md5)
                if not os.path.exists(path):
                    self.warning("path %s for bundle %s does not exist",
                        path, name)
                else:
                    package.getPackager().registerPackagePath(path, name)
                ret.append((name, path))

            return ret

        # get sums for all bundles we need
        d = self.callRemote('getBundleSums', **kwargs)
        d.addCallback(getZips)
        d.addCallback(unpackAndRegister)
        return d

    def loadModule(self, moduleName):
        """
        Load the module given by name.
        Sets up all necessary bundles to be able to load the module.

        @rtype:   L{twisted.internet.defer.Deferred}
        @returns: a deferred that will fire when the given module is loaded,
                  giving the loaded module.
        """

        def gotBundles(bundles):
            self.debug('Got bundles %r', bundles)

            # load up the module and return it
            __import__(moduleName, globals(), locals(), [])
            self.log('loaded module %s', moduleName)
            return sys.modules[moduleName]

        self.debug('Loading module %s', moduleName)

        # get sums for all bundles we need
        d = self.getBundles(moduleName=moduleName)
        d.addCallback(gotBundles)
        return d

    def getBundleByName(self, bundleName):
        """
        Get the given bundle locally.

        @rtype:   L{twisted.internet.defer.Deferred}
        @returns: a deferred returning the absolute path under which the
                  bundle is extracted.
        """

        def gotBundles(bundles):
            name, path = bundles[-1]
            assert name == bundleName
            self.debug('Got bundle %s in %s', bundleName, path)
            return path


        self.debug('Getting bundle %s', bundleName)
        d = self.getBundles(bundleName=bundleName)
        d.addCallback(gotBundles)
        return d

    def getFile(self, fileName):
        """
        Do everything needed to get the given bundled file.

        @returns: a deferred returning the absolute path to a local copy
                  of the given file.
        """

        def gotBundles(bundles):
            name, bundlePath = bundles[-1]
            path = os.path.join(bundlePath, fileName)
            if not os.path.exists(path):
                self.warning("path %s for file %s does not exist",
                             path, fileName)
            return path

        self.debug('Getting file %s', fileName)
        d = self.getBundles(fileName=fileName)
        d.addCallback(gotBundles)
        return d
