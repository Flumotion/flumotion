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
bundled code
"""


from twisted.internet import error, defer
from twisted.python import rebuild

from flumotion.common import bundle, common, errors, log
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
        Call the given remote method on the manager-side AdminAvatar.
        """
        if not self.remote:
            raise errors.ManagerNotConnectedError
        return self.remote.callRemote(methodName, *args, **kwargs)

    def _fetchAndRegisterBundles(self, names):
        d = self._callRemote('getBundleZips', names)
        yield d
        result = d.value()

        self.debug('_fetchAndRegisterBundles: rec\'d %d zips' % len(result))
        for name in names:
            if name not in result.keys():
                msg = "Missing bundle %s was not received" % name
                self.warning(msg)
                raise errors.NoBundleError(msg)

            b = bundle.Bundle(name)
            b.setZip(result[name])
            path = self._unbundler.unbundle(b)

            self.debug("unpacked bundle %s to dir %s" % (name, path))
            common.registerPackagePath(path)
        yield names
    _fetchAndRegisterBundles = defer_generator_method(_fetchAndRegisterBundles)

    def load_module(self, moduleName):
        """
        Load the module given by name.
        Sets up all necessary bundles to be able to load the module.

        @rtype:   L{twisted.internet.defer.Deferred}
        @returns: a deferred that will fire when the given module is loaded.
        """
        
        # fool pychecker
        import os
        import sys

        d = self._callRemote('getBundleSums', moduleName)
        yield d
        sums = d.value()

        # sums is a list of name, sum tuples
        to_fetch = []
        to_load = []
        for name, md5 in sums:
            try:
                m = sys.modules[name]
                if m.__md5__ == md5:
                    # module is up to date, no need to do anything
                    self.log(name + ' is loaded and up to date')
                    continue
                else:
                    raise
            except:
                path = os.path.join(configure.cachedir, name, md5)
                if os.path.exists(path):
                    self.log(name + ' not loaded but the cache is valid')
                    common.registerPackagePath(path)
                    to_load.append(name)
                else:
                    self.log(name + ' not loaded and needs updating')
                    to_fetch.append((name,sum))

        d = self._fetchAndRegisterBundles([x[0] for x in to_fetch])
        yield d
        fetched = d.value()

        # load all the new modules, just in case some are only
        # loaded conditionally -- we need to attach the __md5__
        # values
        for name, md5 in sums:
            if name in fetched or name in to_load:
                if name in sys.modules:
                    self.log('rebuilding ' + name)
                    rebuild.rebuild(sys.modules[name])
                else:
                    self.log('__importing__ ' + name)
                    __import__(name, globals(), locals(), [])
                sys.modules[name].__md5__ = md5
        # make sure we have loaded the toplevel module
        __import__(moduleName, globals(), locals(), [])

        yield sys.modules[moduleName]
    load_module = defer_generator_method(load_module)
