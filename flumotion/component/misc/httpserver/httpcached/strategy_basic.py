# -*- Mode: Python; test-case-name: flumotion.test.test_component_providers -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# Flumotion - a streaming media server
# Copyright (C) 2004,2005,2006,2007,2008 Fluendo, S.L. (www.fluendo.com).
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

import stat

from twisted.internet import defer

from flumotion.common import log

from flumotion.component.misc.httpserver import fileprovider
from flumotion.component.misc.httpserver import cachestats
from flumotion.component.misc.httpserver.httpcached import common
from flumotion.component.misc.httpserver.httpcached import strategy_base

LOG_CATEGORY = "basic-caching"

EXPIRE_CHECK_TTL = 3


class CachingStrategy(strategy_base.CachingStrategy):
    """
    Simplistic caching strategy where all requested streams
    are cached when requested.

    On each cache-miss, a caching session is created and started right away.

    When a cached file expire, a new session is created with the condition
    that it has been modified. If not the cached file is used
    and keep alive, if it succeed the cached file is deleted
    and a new caching session is created and started.

    Updates the caching statistics.
    """

    logCategory = LOG_CATEGORY

    def __init__(self, cachemgr, reqmgr, ttl):
        strategy_base.CachingStrategy.__init__(self, cachemgr, reqmgr, ttl)

    def _onCacheMiss(self, url, stats):
        session = strategy_base.CachingSession(self, url, self.cachemgr.stats)
        session.cache()
        d = session.waitStarted()
        d.addCallbacks(self._cbCreateSource, self._filterErrors,
                      callbackArgs=(stats, ))
        return d

    def _onCacheOutdated(self, url, identifier, cachedFile, stats):
        self.log("Checking if resource is outdated '%s'", url)
        mtime = cachedFile.stat.st_mtime
        sess = strategy_base.CachingSession(self, url,
            self.cachemgr.stats, ifModifiedSince=mtime)
        sess.cache()
        d = sess.waitStarted()
        args = (url, identifier, cachedFile, stats)
        d.addCallbacks(self._reallyOutdated, self._maybeNotOutdated,
                       callbackArgs=args, errbackArgs=args)
        return d

    def _reallyOutdated(self, session, url, identifier, cachedFile, stats):
        self.debug("Resource outdated, caching the new one for '%s'", url)
        cachedFile.unlink()
        cachedFile.close()
        stats.onCacheOutdated()
        stats.onStarted(session.size, cachestats.CACHE_MISS)
        return strategy_base.RemoteSource(session, stats)

    def _maybeNotOutdated(self, failure, url, identifier, cachedFile, stats):
        if failure.check(strategy_base.ConditionError):
            # Not outdated, so we refresh the TTL
            self.log("Resource not outdated, keep using "
                     "the cached one for '%s'", url)
            self.keepCacheAlive(identifier)
            stats.onStarted(cachedFile.stat[stat.ST_SIZE],
                            cachestats.CACHE_HIT)
            return strategy_base.CachedSource(identifier, url,
                                              cachedFile, stats)

        if failure.check(fileprovider.NotFoundError, fileprovider.AccessError):
            # The file has been deleted or its rights have been revoked
            self.debug("Resource deleted or forbidden, removing cached file")
            cachedFile.close()
            return failure

        if failure.check(fileprovider.FileError):
            self.warning("Cached file expiration check fail, "
                         "using cached file anyway: %s",
                         failure.getErrorMessage())
            # Use a fixed small ttl to prevent doing an expiration check
            # for all the files if the resource server is down.
            self.keepCacheAlive(identifier, EXPIRE_CHECK_TTL)
            stats.onStarted(cachedFile.stat[stat.ST_SIZE],
                            cachestats.CACHE_HIT)
            return strategy_base.CachedSource(identifier, url,
                                              cachedFile, stats)

        cachedFile.close()
        return failure

    def _filterErrors(self, failure):
        if failure.check(strategy_base.ConditionError):
            raise fileprovider.FileError(failure.getErrorMessage())
        return failure

    def _cbCreateSource(self, session, stats):
        stats.onStarted(session.size, cachestats.CACHE_MISS)
        return strategy_base.RemoteSource(session, stats)
