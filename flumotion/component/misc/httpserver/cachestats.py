# -*- Mode: Python; test-case-name: -*-
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

import time

from twisted.internet import reactor

from flumotion.common import log


# Filter out requests that read less than a block for average values
MIN_REQUEST_SIZE = 64 * 1024 + 1
# Statistics update period
STATS_UPDATE_PERIOD = 10

CACHE_MISS = 0
CACHE_HIT = 1
TEMP_HIT = 2


class RequestStatistics(object):

    def __init__(self, cacheStats):
        self._stats = cacheStats
        self._outdated = False
        self._size = 0L
        self._status = None
        self.bytesReadFromSource = 0L
        self.bytesReadFromCache = 0L

    def getBytesRead(self):
        return self.bytesReadFromSource + self.bytesReadFromCache
    bytesRead = property(getBytesRead)

    def getCacheReadRatio(self):
        total = self.bytesRead
        if total == 0:
            return 0.0
        return float(self.bytesReadFromCache) / total
    cacheReadRatio = property(getCacheReadRatio)

    def onStarted(self, size, cacheStatus):
        cs = self._stats
        self._size = size
        if cacheStatus == CACHE_HIT:
            self._status = "cache-hit"
            cs.cacheHitCount += 1
        elif cacheStatus == TEMP_HIT:
            cs.cacheHitCount += 1
            cs.tempHitCount += 1
            self._status = "temp-hit"
        elif cacheStatus == CACHE_MISS:
            cs.cacheMissCount += 1
            if self._outdated:
                self._status = "cache-outdate"
            else:
                self._status = "cache-miss"
        cs._set("cache-hit-count", cs.cacheHitCount)
        cs._set("temp-hit-count", cs.tempHitCount)
        cs._set("cache-miss-count", cs.cacheMissCount)

    def onCacheOutdated(self):
        self._outdated = True
        cs = self._stats
        cs.cacheOutdateCount += 1
        cs._set("cache-outdate-count", cs.cacheOutdateCount)

    def onBytesRead(self, fromSource, fromCache, correction):
        cs = self._stats
        self.bytesReadFromSource += fromSource + correction
        self.bytesReadFromCache += fromCache - correction
        cs.bytesReadFromSource += fromSource + correction
        cs.bytesReadFromCache += fromCache - correction

    def onClosed(self):
        pass

    def getLogFields(self):
        """
        Provide the following log fields:
            cache-status:  value can be 'cache-miss', 'cache-outdate',
                           'cache-hit', or 'temp-hit'
            cache-read:    how many bytes where read from the cache for
                           this resource. the difference from resource-read
                           was read from the source file (network file system?)

        The proportion read from cache and from source are adjusted
        to take into account the file copy. It's done by remembering
        how many bytes are copied at session level.
        """
        return {"cache-status": self._status,
                "cache-read": self.bytesReadFromCache}


class CacheStatistics(object):

    _updater = None
    _callId = None

    def __init__(self):
        # For cache usage
        self._cacheUsage = 0
        self._cacheUsageRatio = 0.0
        # For cache statistics
        self.cacheHitCount = 0
        self.tempHitCount = 0
        self.cacheMissCount = 0
        self.cacheOutdateCount = 0
        self.cleanupCount = 0
        # For real file reading statistics
        self.bytesReadFromSource = 0L
        self.bytesReadFromCache = 0L
        # File copying statistics
        self.totalCopyCount = 0
        self.currentCopyCount = 0
        self.finishedCopyCount = 0
        self.cancelledCopyCount = 0
        self.bytesCopied = 0L
        self._copyRatios = 0.0

    def startUpdates(self, updater):
        self._updater = updater
        if updater and (self._callId is None):
            self._set("cache-usage-estimation", self._cacheUsage)
            self._set("cache-usage-ratio-estimation", self._cacheUsageRatio)
            self._set("cleanup-count", self.cleanupCount)
            self._set("last-cleanup-time", time.time())
            self._set("current-copy-count", self.currentCopyCount)
            self._set("finished-copy-count", self.finishedCopyCount)
            self._set("cancelled-copy-count", self.cancelledCopyCount)
            self._set("mean-copy-ratio", self.meanCopyRatio)
            self._set("mean-bytes-copied", self.meanBytesCopied)
            self._update()

    def stopUpdates(self):
        self._updater = None
        if self._callId is not None:
            self._callId.cancel()
            self._callId = None

    def getCacheReadRatio(self):
        total = self.bytesReadFromSource + self.bytesReadFromCache
        if total == 0:
            return 0
        return float(self.bytesReadFromCache) / total
    cacheReadRatio = property(getCacheReadRatio)

    def getMeanBytesCopied(self):
        if self.finishedCopyCount == 0:
            return 0
        return self.bytesCopied / self.finishedCopyCount
    meanBytesCopied = property(getMeanBytesCopied)

    def getMeanCopyRatio(self):
        if self.finishedCopyCount == 0:
            return 0
        return self._copyRatios / self.finishedCopyCount
    meanCopyRatio = property(getMeanCopyRatio)

    def onEstimateCacheUsage(self, usage, max):
        self._cacheUsage = usage
        self._cacheUsageRatio = float(usage) / max
        self._set("cache-usage-estimation", self._cacheUsage)
        self._set("cache-usage-ratio-estimation", self._cacheUsageRatio)

    def onCleanup(self):
        self.cleanupCount += 1
        self._set("cleanup-count", self.cleanupCount)
        self._set("last-cleanup-time", time.time())

    def onCopyStarted(self):
        self.currentCopyCount += 1
        self.totalCopyCount += 1
        self._set("current-copy-count", self.currentCopyCount)

    def onCopyCancelled(self, size, copied):
        self.currentCopyCount -= 1
        self.finishedCopyCount += 1
        self.cancelledCopyCount += 1
        self.bytesCopied += copied
        self._copyRatios += float(copied) / size
        self._set("current-copy-count", self.currentCopyCount)
        self._set("finished-copy-count", self.finishedCopyCount)
        self._set("cancelled-copy-count", self.cancelledCopyCount)
        self._set("mean-copy-ratio", self.meanCopyRatio)
        self._set("mean-bytes-copied", self.meanBytesCopied)

    def onCopyFinished(self, size):
        self.currentCopyCount -= 1
        self.finishedCopyCount += 1
        self.bytesCopied += size
        self._copyRatios += 1.0
        self._set("current-copy-count", self.currentCopyCount)
        self._set("finished-copy-count", self.finishedCopyCount)
        self._set("mean-copy-ratio", self.meanCopyRatio)
        self._set("mean-bytes-copied", self.meanBytesCopied)

    def _set(self, key, value):
        if self._updater is not None:
            self._updater.update(key, value)

    def _update(self):
        self._set("cache-read-ratio", self.cacheReadRatio)
        self._logStatsLine()
        self._callId = reactor.callLater(STATS_UPDATE_PERIOD, self._update)

    def _logStatsLine(self):
        """
        Statistic fields names:
            CRR: Cache Read Ratio
            CMC: Cache Miss Count
            CHC: Cache Hit Count
            THC: Temp Hit Count
            COC: Cache Outdate Count
            CCC: Cache Cleanup Count
            CCU: Cache Current Usage
            CUR: Cache Usage Ratio
            PTC: coPy Total Count
            PCC: coPy Current Count
            PAC: coPy cAncellation Count
            MCS: Mean Copy Size
            MCR: Mean Copy Ratio
        """
        log.debug("stats-local-cache",
                  "CRR: %.4f; CMC: %d; CHC: %d; THC: %d; COC: %d; "
                  "CCC: %d; CCU: %d; CUR: %.5f; "
                  "PTC: %d; PCC: %d; PAC: %d; MCS: %d; MCR: %.4f",
                  self.cacheReadRatio, self.cacheMissCount,
                  self.cacheHitCount, self.tempHitCount,
                  self.cacheOutdateCount, self.cleanupCount,
                  self._cacheUsage, self._cacheUsageRatio,
                  self.totalCopyCount, self.currentCopyCount,
                  self.cancelledCopyCount, self.meanBytesCopied,
                  self.meanCopyRatio)
