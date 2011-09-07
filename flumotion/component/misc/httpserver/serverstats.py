# -*- Mode: Python; test-case-name: -*-
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

import time

from twisted.internet import reactor

from flumotion.common import log


# Minimum size to take in account when calculating mean file read
MIN_REQUEST_SIZE = 64 * 1024 + 1
# Statistics update period
STATS_UPDATE_PERIOD = 10


class RequestStatistics(object):

    def __init__(self, serverStats):
        self._stats = serverStats
        self.bytesSent = 0L
        self._stats._onRequestStart(self)

    def onDataSent(self, size):
        self.bytesSent += size
        self._stats._onRequestDataSent(self, size)

    def onCompleted(self, size):
        self._stats._onRequestComplete(self, size)


class ServerStatistics(object):

    _updater = None
    _callId = None

    def __init__(self):
        now = time.time()
        self.startTime = now
        self.currentRequestCount = 0
        self.totalRequestCount = 0
        self.requestCountPeak = 0
        self.requestCountPeakTime = now
        self.finishedRequestCount = 0
        self.totalBytesSent = 0L

        # Updated by a call to the update method
        self.meanRequestCount = 0
        self.currentRequestRate = 0
        self.requestRatePeak = 0
        self.requestRatePeakTime = now
        self.meanRequestRate = 0.0
        self.currentBitrate = 0
        self.meanBitrate = 0
        self.bitratePeak = 0
        self.bitratePeakTime = now

        self._fileReadRatios = 0.0
        self._lastUpdateTime = now
        self._lastRequestCount = 0
        self._lastBytesSent = 0L

    def startUpdates(self, updater):
        self._updater = updater
        self._set("bitrate-peak-time", self.bitratePeakTime)
        self._set("request-rate-peak-time", self.requestRatePeakTime)
        self._set("request-count-peak-time", self.requestCountPeakTime)
        if self._callId is None:
            self._callId = reactor.callLater(STATS_UPDATE_PERIOD, self._update)

    def stopUpdates(self):
        self._updater = None
        if self._callId is not None:
            self._callId.cancel()
            self._callId = None

    def getMeanFileReadRatio(self):
        if self.finishedRequestCount > 0:
            return self._fileReadRatios / self.finishedRequestCount
        return 0.0
    meanFileReadRatio = property(getMeanFileReadRatio)

    def _update(self):
        now = time.time()
        updateDelta = now - self._lastUpdateTime
        # Update average concurrent request
        meanReqCount = self._updateAverage(self._lastUpdateTime, now,
                                           self.meanRequestCount,
                                           self.currentRequestCount)
        # Calculate Request rate
        countDiff = self.totalRequestCount - self._lastRequestCount
        newReqRate = float(countDiff) / updateDelta
        # Calculate average request rate
        meanReqRate = self._updateAverage(self._lastUpdateTime, now,
                                          self.currentRequestRate, newReqRate)
        # Calculate current bitrate
        bytesDiff = (self.totalBytesSent - self._lastBytesSent) * 8
        newBitrate = bytesDiff / updateDelta
        # calculate average bitrate
        meanBitrate = self._updateAverage(self._lastUpdateTime, now,
                                          self.currentBitrate, newBitrate)
        # Update Values
        self.meanRequestCount = meanReqCount
        self.currentRequestRate = newReqRate
        self.meanRequestRate = meanReqRate
        self.currentBitrate = newBitrate
        self.meanBitrate = meanBitrate

        # Update the statistics keys with the new values
        self._set("mean-request-count", meanReqCount)
        self._set("current-request-rate", newReqRate)
        self._set("mean-request-rate", meanReqRate)
        self._set("current-bitrate", newBitrate)
        self._set("mean-bitrate", meanBitrate)

        # Update request rate peak
        if newReqRate > self.requestRatePeak:
            self.requestRatePeak = newReqRate
            self.requestRatePeakTime = now
            # update statistic keys
            self._set("request-rate-peak", newReqRate)
            self._set("request-rate-peak-time", now)

        # Update bitrate peak
        if newBitrate > self.bitratePeak:
            self.bitratePeak = newBitrate
            self.bitratePeakTime = now
            # update statistic keys
            self._set("bitrate-peak", newBitrate)
            self._set("bitrate-peak-time", now)

        # Update bytes read statistic key too
        self._set("total-bytes-sent", self.totalBytesSent)

        self._lastRequestCount = self.totalRequestCount
        self._lastBytesSent = self.totalBytesSent
        self._lastUpdateTime = now
        # Log the stats
        self._logStatsLine()
        self._callId = reactor.callLater(STATS_UPDATE_PERIOD, self._update)

    def _set(self, key, value):
        if self._updater is not None:
            self._updater.update(key, value)

    def _onRequestStart(self, stats):
        # Update counters
        self.currentRequestCount += 1
        self.totalRequestCount += 1
        self._set("current-request-count", self.currentRequestCount)
        self._set("total-request-count", self.totalRequestCount)
        # Update concurrent request peak
        if self.currentRequestCount > self.requestCountPeak:
            now = time.time()
            self.requestCountPeak = self.currentRequestCount
            self.requestCountPeakTime = now
            self._set("request-count-peak", self.currentRequestCount)
            self._set("request-count-peak-time", now)

    def _onRequestDataSent(self, stats, size):
        self.totalBytesSent += size

    def _onRequestComplete(self, stats, size):
        self.currentRequestCount -= 1
        self.finishedRequestCount += 1
        self._set("current-request-count", self.currentRequestCount)
        if (size > 0) and (stats.bytesSent > MIN_REQUEST_SIZE):
            self._fileReadRatios += float(stats.bytesSent) / size
            self._set("mean-file-read-ratio", self.meanFileReadRatio)

    def _updateAverage(self, lastTime, newTime, lastValue, newValue):
        lastDelta = lastTime - self.startTime
        newDelta = newTime - lastTime
        if lastDelta > 0:
            delta = lastDelta + newDelta
            before = (lastValue * lastDelta) / delta
            after = (newValue * newDelta) / delta
            return before + after
        return lastValue

    def _logStatsLine(self):
        """
        Statistic fields names:
            TRC: Total Request Count
            CRC: Current Request Count
            CRR: Current Request Rate
            MRR: Mean Request Rate
            FRR: File Read Ratio
            MBR: Mean Bitrate
            CBR: Current Bitrate
        """
        log.debug("stats-http-server",
                  "TRC: %s; CRC: %d; CRR: %.2f; MRR: %.2f; "
                  "FRR: %.4f; MBR: %d; CBR: %d",
                  self.totalRequestCount, self.currentRequestCount,
                  self.currentRequestRate, self.meanRequestRate,
                  self.meanFileReadRatio, self.meanBitrate,
                  self.currentBitrate)
