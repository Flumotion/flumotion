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
from cStringIO import StringIO
import time

from twisted.internet import defer, reactor, abstract

from flumotion.common import log

from flumotion.component.misc.httpserver import fileprovider
from flumotion.component.misc.httpserver import ourmimetypes
from flumotion.component.misc.httpserver import cachestats
from flumotion.component.misc.httpserver.httpcached import common
from flumotion.component.misc.httpserver.httpcached import resource_manager

EXP_TABLE_CLEANUP_PERIOD = 30
MAX_RESUME_COUNT = 20

# A RemoteProducer will not be able to
# produce faster than 6.25 Mibit/s (6.55 Mbit/s)
PRODUCING_PERIOD = 0.08


class ConditionError(Exception):
    """
    Raised when a request used by a caching session
    was using a conditional retrieval and it fails.
    """

    def __init__(self, *args, **kwargs):
        self.code = kwargs.pop("code", None)
        Exception.__init__(self, *args, **kwargs)

    def __str__(self):
        return "<%s: %s>" % (type(self).__name__, repr(self.code))


class CachingStrategy(log.Loggable):
    """
    Base class for all caching strategies.

    Handles the cache lookup, cache expiration checks,
    statistics gathering and caching sessions managment.
    """

    logCategory = "base-caching"

    def __init__(self, cachemgr, reqmgr, ttl):
        self.cachemgr = cachemgr
        self.reqmgr = reqmgr
        self.ttl = ttl

        self._identifiers = {} # {IDENTIFIER: CachingSession}
        self._etimes = {} # {IDENTIFIER: EXPIRATION_TIME}

        self._cleanupCall = None

    def setup(self):
        self._startCleanupLoop()
        return self.reqmgr.setup()

    def cleanup(self):
        self._stopCleanupLoop()
        self.reqmgr.cleanup()
        for session in self._identifiers.values():
            session.cancel()
        return self

    def getSourceFor(self, url, stats):
        identifier = self.cachemgr.getIdentifier(url.path)
        session = self._identifiers.get(identifier, None)
        if session is not None and not session.checkModified:
            self.debug("Caching session found for '%s'", url)

            if (session.getState() in
                (CachingSession.DETACHED, CachingSession.CACHED)):
                stats.onStarted(session.size, cachestats.CACHE_HIT)
            elif (session.getState() in
                  (CachingSession.REQUESTING, CachingSession.BUFFERING,
                   CachingSession.CACHING)):
                stats.onStarted(session.size, cachestats.TEMP_HIT)
            else:
                stats.onStarted(session.size, cachestats.CACHE_MISS)

            # Wait to know session info like mtime and size
            d = session.waitInfo()
            d.addCallback(RemoteSource, stats)
            return d

        self.log("Looking for cached file for '%s'", url)
        d = defer.Deferred()
        d.addCallback(self.cachemgr.openCacheFile)
        d.addErrback(self._cachedFileError, url)
        d.addCallback(self._gotCachedFile, url, identifier, stats)

        d.callback(url.path)

        return d

    def requestData(self, url, offset=None, size=None, mtime=None):
        requester = BlockRequester(self.reqmgr, url, mtime)
        return requester.retrieve(offset, size)

    def getSessions(self):
        return self._identifiers.values()

    def keepCacheAlive(self, identifier, ttl=None):
        self._etimes[identifier] = time.time() + (ttl or self.ttl)

    ### To Be Overridden ###

    def _onCacheMiss(self, url, stats):
        raise NotImplementedError()

    def _onCacheOutdated(self, url, identifier, cachedFile, stats):
        raise NotImplementedError()

    ### Protected Methods ###

    def _startCleanupLoop(self):
        assert self._cleanupCall is None, "Already started"
        self._cleanupCall = reactor.callLater(EXP_TABLE_CLEANUP_PERIOD,
                                              self._cleanupLoop)

    def _stopCleanupLoop(self):
        if self._cleanupCall:
            self._cleanupCall.cancel()
            self._cleanupCall = None

    def _cleanupLoop(self):
        self._cleanupCall = None
        self._cleanupExpirationTable()
        self._startCleanupLoop()

    def _cleanupExpirationTable(self):
        now = time.time()
        expired = [i for i, e in self._etimes.items() if e < now]
        for ident in expired:
            del self._etimes[ident]

    def _onNewSession(self, session):
        identifier = session.identifier
        old = self._identifiers.get(identifier, None)
        if old is not None:
            old.cancel()
        self._identifiers[session.identifier] = session

    def _onSessionCanceled(self, session):
        if self._identifiers[session.identifier] == session:
            del self._identifiers[session.identifier]

    def _onResourceCached(self, session):
        self.keepCacheAlive(session.identifier)
        del self._identifiers[session.identifier]

    def _onResourceError(self, session, error):
        del self._identifiers[session.identifier]

    def _cachedFileError(self, failure, url):
        if failure.check(fileprovider.FileError):
            self.debug("Error looking for cached file for '%s'", url)
            return None
        return failure

    def _gotCachedFile(self, cachedFile, url, identifier, stats):
        if cachedFile is not None:
            self.log("Opened cached file '%s'", cachedFile.name)
            etime = self._etimes.get(identifier, None)
            session = self._identifiers.get(identifier, None)
            if (etime and (etime > time.time()) or
                (session and session.checkModified)):
                stats.onStarted(cachedFile.stat[stat.ST_SIZE],
                                cachestats.CACHE_HIT)
                return CachedSource(identifier, url, cachedFile, stats)
            self.debug("Cached file may have expired '%s'", cachedFile.name)
            return self._onCacheOutdated(url, identifier, cachedFile, stats)
        self.debug("Resource not cached '%s'", url)
        return self._onCacheMiss(url, stats)


class CachedSource(resource_manager.DataSource):
    """
    Data source that read data directly from a localy cached file.
    """

    mimetypes = ourmimetypes.MimeTypes()

    def __init__(self, ident, url, cachedFile, stats):
        self.identifier = ident
        self.url = url
        self._file = cachedFile
        self.stats = stats

        self.mimeType = self.mimetypes.fromPath(url.path)
        self.mtime = cachedFile.stat[stat.ST_MTIME]
        self.size = cachedFile.stat[stat.ST_SIZE]

        self._current = cachedFile.tell()

    def produce(self, consumer, offset):
        # A producer for a cached file is not really convenient
        # because it's better used pulling than pushing.
        return None

    def read(self, offset, size):
        if offset != self._current:
            self._file.seek(offset)
        data = self._file.read(size)
        size = len(data)
        self.stats.onBytesRead(0, size, 0)
        self._current = offset + size
        return data

    def close(self):
        self.stats.onClosed()
        self._file.close()
        self._file = None


class BaseRemoteSource(resource_manager.DataSource):
    """
    Base class for resource not yet cached.
    It offers a push producer, it delegates read operations
    to the session and start a block pipelining if the session
    cannot serve the requested data.
    Updates the cache statistics.
    """

    strategy = None
    session = None
    stats = None

    def produce(self, consumer, offset):
        return RemoteProducer(consumer, self.session, offset, self.stats)

    def read(self, offset, size):
        if offset >= self.size:
            return "" # EOF
        data = self.session.read(offset, size)
        if data is not None:
            # Adjust the cache/source values to take copy into account
            # FIXME: ask sebastien if he is on crack or LSD
            size = len(data)
            diff = min(self.session._correction, size)
            self.session._correction -= diff
            self.stats.onBytesRead(0, size, diff) # from cache
            return data
        d = self.strategy.requestData(self.url, offset, size, self.mtime)
        d.addCallback(self._requestDataCb)
        d.addErrback(self._requestDataFailed)
        return d

    def _requestDataFailed(self, failure):
        if failure.check(fileprovider.FileOutOfDate):
            self.session.cancel()
        return failure

    def _requestDataCb(self, data):
        self.stats.onBytesRead(len(data), 0, 0) # from remote source
        return data


class RemoteSource(BaseRemoteSource):
    """
    Simple remote source.
    """

    def __init__(self, session, stats):
        self.session = session
        self.stats = stats

        self.strategy = session.strategy
        self.identifier = session.identifier
        self.url = session.url
        self.mimeType = session.mimeType
        self.mtime = session.mtime
        self.size = session.size

        session.addref()

    def close(self):
        self.stats.onClosed()
        self.session.delref()
        self.session = None


class BaseCachingSession(object):
    """
    Base class of caching sessions.
    Just an interface to be implemented or inherited
    by all caching sessions.
    """

    strategy = None
    url = None
    size = 0
    mtime = None
    mimeType = None

    def read(self, offset, size):
        return None

    def cancel(self):
        raise NotImplementedError()

    def addref(self):
        raise NotImplementedError()

    def delref(self):
        raise NotImplementedError()


class CachingSession(BaseCachingSession, log.Loggable):
    """
    Caches a stream locally in a temporary file.
    The already cached data can be read from the session.

    Can be canceled, meaning the session is not valid anymore.

    Can be aborted, meaning the session will stop caching locally
    but is still valid.

    The caching operation can be started at any moment, but the
    session have to receive the stream info before it can be used
    with a RemoteSource instance.

    It can recover request failures up to MAX_RESUME_COUNT times.
    """

    logCategory = "caching-session"

    (PIPELINING,
     REQUESTING,
     BUFFERING,
     CACHING,
     CACHED,
     DETACHED,
     CLOSED,
     CANCELED,
     ABORTED,
     ERROR) = range(10)

    mimetypes = ourmimetypes.MimeTypes()

    def __init__(self, strategy, url, cache_stats, ifModifiedSince=None):
        self.strategy = strategy
        self.url = url
        self.identifier = strategy.cachemgr.getIdentifier(url.path)

        self.ifModifiedSince = ifModifiedSince
        self.cache_stats = cache_stats

        self._refcount = 0
        self._state = self.PIPELINING
        self._request = None

        self.checkModified = False

        self._infoDefers = []
        self._startedDefers = []
        self._finishedDefers = []
        self._errorValue = None

        self._file = None
        self._bytes = 0
        self._correction = 0

        self._resumes = MAX_RESUME_COUNT

        self.logName = common.log_id(self) # To be able to track the instance

        self.strategy._onNewSession(self)

        self.log("Caching session created for %s", url)

    def isActive(self):
        return (self._state < self.CLOSED) or (self._state == self.ABORTED)

    def getState(self):
        return self._state

    def cache(self):
        """
        Starts caching the remote resource locally.
        """
        if self._state != self.PIPELINING:
            return

        self._state = self.REQUESTING

        self.debug("Caching requested for %s", self.url)
        self.cache_stats.onCopyStarted()

        self._firstRetrieve()

    def waitInfo(self):
        if self._state < self.BUFFERING:
            d = defer.Deferred()
            self._infoDefers.append(d)
            return d
        if self._state <= self.CLOSED:
            return defer.succeed(self)
        return defer.fail(self._errorValue)

    def waitStarted(self):
        if self._state <= self.REQUESTING:
            d = defer.Deferred()
            self._startedDefers.append(d)
            return d
        if self._state <= self.CLOSED:
            return defer.succeed(self)
        return defer.fail(self._errorValue)

    def waitFinished(self):
        if self._state < self.DETACHED:
            d = defer.Deferred()
            self._finishedDefers.append(d)
            return d
        if self._state <= self.CLOSED:
            return defer.succeed(self)
        return defer.fail(self._errorValue)

    def read(self, offset, size):
        if self._state == self.CANCELED:
            raise fileprovider.FileOutOfDate("File out of date")
        if self._state == self.ABORTED:
            return None
        if self._state >= self.CLOSED:
            raise fileprovider.FileClosedError("Session Closed")

        if self._file is None:
            return None

        if min(self.size, offset + size) > self._bytes:
            return None

        self._file.seek(offset)
        return self._file.read(size)

    def cancel(self):
        """
        After calling this method the session cannot be used anymore.
        """
        if self._state < self.REQUESTING or self._state >= self.CACHED:
            return

        self.log("Canceling caching session for %s", self.url)

        self.strategy._onSessionCanceled(self)
        self.cache_stats.onCopyCancelled(self.size, self._bytes)

        self._close()

        error = fileprovider.FileOutOfDate("File out of date")
        self._fireError(error)

        if self._request:
            self.debug("Caching canceled for %s (%d/%d Bytes ~ %d %%)",
                       self.url, self._bytes, self.size,
                       self.size and int(self._bytes * 100 / self.size))
            self._request.cancel()
            self._request = None
        else:
            self.debug("Caching canceled before starting to cache")

        self._state = self.CANCELED

    def abort(self):
        """
        After calling this method the session will just stop caching
        and return None when trying to read. Used when pipelining is wanted.
        """
        if self._state < self.REQUESTING or self._state >= self.CACHED:
            return

        self.log("Aborting caching session for %s", self.url)

        self.strategy._onSessionCanceled(self)
        self.cache_stats.onCopyCancelled(self.size, self._bytes)

        self._close()

        error = fileprovider.FileError("Caching aborted")
        self._fireError(error)

        if self._request:
            self.debug("Caching aborted for %s", self.url)
            self._request.cancel()
            self._request = None
        else:
            self.debug("Caching aborted before starting to cache")

        self._state = self.ABORTED

    def addref(self):
        self._refcount += 1

    def delref(self):
        self._refcount -= 1
        if self._refcount == 0:
            if self._state == self.DETACHED:
                # not referenced, so no we can close the file
                self.log("Detached session not referenced anymore")
                self._close()

    def isref(self):
        return self._refcount > 0

    ### StreamConsumer ###

    def serverError(self, getter, code, message):
        self.warning("Session request error %s (%s) for %s using %s:%s",
                     message, code, self.url, getter.host, getter.port)
        if code in (common.SERVER_DISCONNECTED, common.SERVER_TIMEOUT):
            if self._resumes > 0:
                self._resumes -= 1
                if self._state > self.REQUESTING:
                    # We already have request info
                    offset = self._bytes
                    size = self.size - self._bytes
                    self.debug("Resuming retrieval from offset %d with "
                               "size %d of %s (%d tries left)", offset, size,
                               self.url, self._resumes)

                    self._resumeRetrieve(offset, size)
                    return
                else:
                    # We don't have any info, e must retry from scratch
                    self.debug("Resuming retrieval from start of %s "
                               "(%d tries left)", self.url, self._resumes)
                    self._firstRetrieve()
                    return
            self.debug("Too much resuming intents, stopping "
                       "after %d of %s bytes of %s",
                       self._bytes, self.size, self.url)
        self._close()
        self._error(fileprovider.UnavailableError(message))

    def conditionFail(self, getter, code, message):
        if code == common.STREAM_MODIFIED:
            # Modified file detected during recovery
            self.log("Modifications detected during recovery of %s", self.url)
            self.cancel()
            return
        self.log("Unexpected HTTP condition failed: %s", message)
        self._close()
        self._error(ConditionError(message, code=code))

    def streamNotAvailable(self, getter, code, message):
        self.log("Stream to be cached is not available: %s", message)
        self._close()
        if code == common.STREAM_NOTFOUND:
            self._error(fileprovider.NotFoundError(message))
        elif code == common.STREAM_FORBIDDEN:
            self._error(fileprovider.AccessError(message))
        else:
            self._error(fileprovider.FileError(message))

    def onInfo(self, getter, info):
        if self._state == self.BUFFERING:
            # We are resuming while waiting for a temporary file,
            # so we still don't want to accumulate data
            self._request.pause()
            return

        if self._state != self.REQUESTING:
            # Already canceled, or recovering from disconnection
            return

        if info.size != (info.length - self._bytes):
            self.log("Unexpected stream size: %s / %s bytes "
                     "(Already got %s bytes)",
                     info.size, info.length, self._bytes)
            self._close()
            msg = "Unexpected resource size: %d" % info.size
            self._error(fileprovider.FileError(msg))
            return

        self._state = self.BUFFERING

        self.mimeType = self.mimetypes.fromPath(self.url.path)
        self.mtime = info.mtime
        self.size = info.size

        self.log("Caching session with type %s, size %s, mtime %s for %s",
                 self.mimeType, self.size, self.mtime, self.url)

        self._file = StringIO() # To wait until we got the real one

        self.log("Requesting temporary file for %s", self.url)
        d = self.strategy.cachemgr.newTempFile(self.url.path, info.size,
                                               info.mtime)

        # But we don't want to accumulate data
        # but it is possible to receive a small amount of data
        # even after calling pause(), so we need buffering.
        self._request.pause()

        # We have got meta data, so callback
        self._fireInfo(self)
        self._fireStarted(self)

        self.debug("Start buffering %s", self.url)
        d.addCallback(self._gotTempFile)

    def _gotTempFile(self, tempFile):
        if self._state not in (self.BUFFERING, self.CACHED):
            # Already canceled
            if tempFile:
                tempFile.close()
            return

        if tempFile is None:
            self.warning("Temporary file creation failed, "
                         "aborting caching of %s", self.url)
            self.abort()
            return

        self.log("Got temporary file for %s", self.url)

        self.debug("Start caching %s", self.url)

        data = self._file.getvalue()
        self._file = tempFile
        tempFile.write(data)

        if self._request is not None:
            # We still have a request, so we want more data of it
            self._request.resume()

        if self._state == self.CACHED:
            # Already got all the data
            self._real_complete()
        else:
            self._state = self.CACHING

    def onData(self, getter, data):
        assert self._state in (self.BUFFERING, self.CACHING), "Not caching"
        self._file.seek(self._bytes)
        size = len(data)
        try:
            self._file.write(data)
        except Exception, e:
            self.warning("Error writing in temporary file: %s", e)
            self.debug("Got %s / %s bytes, would be %s with %s more",
                       self._bytes, self.size, self._bytes + size, size)
            self.abort()
        else:
            self._bytes += size
            self._correction += size

    def streamDone(self, getter):
        assert self._state in (self.BUFFERING, self.CACHING), "Not caching"
        self._request = None
        self._complete()

    def _error(self, error):
        assert self._state < self.CANCELED, "Wrong state for errors"

        self.log("Caching error for %s: %s", self.url, error)

        self._state = self.ERROR

        self.strategy._onResourceError(self, error)
        self.strategy = None
        self._request = None

        self._fireError(error)

    def _fireInfo(self, value):
        defers = list(self._infoDefers)
        # Prevent multiple deferred firing due to reentrence
        self._infoDefers = []
        for d in defers:
            d.callback(value)

    def _fireStarted(self, value):
        defers = list(self._startedDefers)
        # Prevent multiple deferred firing due to reentrence
        self._startedDefers = []
        for d in defers:
            d.callback(value)

    def _fireFinished(self, value):
        defers = list(self._finishedDefers)
        # Prevent multiple deferred firing due to reentrence
        self._finishedDefers = []
        for d in defers:
            d.callback(value)

    def _fireError(self, error):
        self._errorValue = error
        defers = list(self._infoDefers)
        defers.extend(self._startedDefers)
        defers.extend(self._finishedDefers)
        # Prevent multiple deferred firing due to reentrence
        self._infoDefers = []
        self._startedDefers = []
        self._finishedDefers = []
        for d in defers:
            d.errback(error)

    def _close(self):
        if self._state >= self.CLOSED:
            return

        self.log("Closing caching session for %s", self.url)

        if self._state >= self.BUFFERING:
            self._file.close()
            self._file = None

        self._state = self.CLOSED

    def _complete(self):
        assert self._state in (self.CACHING, self.BUFFERING), "Not caching"
        self.debug("Finished caching %s (%d Bytes)", self.url, self.size)

        oldstate = self._state
        self._state = self.CACHED

        if oldstate != self.BUFFERING:
            self._real_complete()

    def _real_complete(self):
        assert self._state == self.CACHED, "Not cached"
        self._state = self.DETACHED
        self.log("Caching session detached for %s", self.url)

        self._file.complete()

        self.strategy._onResourceCached(self)
        self.strategy = None

        if not self.isref():
            # Not referenced anymore by sources, so close the session
            self.log("Caching session not referenced, it can be closed")
            self._close()

        self.cache_stats.onCopyFinished(self.size)
        self._fireFinished(self)

    def _firstRetrieve(self):
        since = self.ifModifiedSince
        self._request = self.strategy.reqmgr.retrieve(self, self.url,
                                                      ifModifiedSince=since)
        self.log("Retrieving data using %s", self._request.logName)

    def _resumeRetrieve(self, offset, size):
        reqmgr = self.strategy.reqmgr
        req = reqmgr.retrieve(self, self.url,
                              ifUnmodifiedSince=self.mtime,
                              start=offset, size=size)
        self._request = req
        self.log("Retrieving data using %s", self._request.logName)


class RemoteProducer(common.StreamConsumer, log.Loggable):
    """
    Offers a IPushProducer interface to a caching session.
    It starts producing data from the specified point.

    If the data is already cached by the session,
    it produce data with a reactor loop reading the data
    from the session by block.

    If the data is not yet cached, it starts a request
    using the request manager and pipeline the data
    to the specified consumer.

    It can recover request failures up to MAX_RESUME_COUNT times.

    It's not used yet in the context of http-server.
    Until now, the simulations show that using a producer with
    long-lived HTTP requests instead of short lived block request
    is less efficient and produce bigger latency for the clients.
    At least when used with  HTTP proxies.
    """

    logCategory = "pipe-producer"

    def __init__(self, consumer, session, offset, stats):
        self.consumer = consumer
        self.offset = offset
        self.session = session
        self.stats = stats
        self.reqmgr = session.strategy.reqmgr

        self.logName = common.log_id(self) # To be able to track the instance

        self._pipelining = False
        self._paused = False
        self._request = None
        self._produced = 0
        self._resumes = MAX_RESUME_COUNT
        self._call = None

        session.addref()

        self.log("Starting producing data with session %s from %s",
                 self.session.logName, self.session.url)

        consumer.registerProducer(self, True) # Push producer
        self._produce()

    ### IPushProducer Methods ###

    def resumeProducing(self):
        if self.consumer is None:
            # Already stopped
            return

        self._paused = False

        if self._pipelining:
            # Doing pipelining
            if self._request:
                # Just resuming current request
                self._request.resume()
            else:
                # Start a new one
                self._pipeline()
        else:
            # Producing from session
            self._produce()

    def pauseProducing(self):
        if self.consumer is None:
            # Already stopped
            return

        self._paused = True

        if self._pipelining:
            # Doing pipelining
            if self._request:
                self._request.pause()
        else:
            # Producing from session
            self._stop()

    def stopProducing(self):
        self.log("Ask to stop producing %s", self.session.url)
        self._terminate()

    ### common.StreamConsumer Methods ###

    def serverError(self, getter, code, message):
        if self._request is None:
            # Already terminated
            return
        self._request = None

        if code in (common.SERVER_DISCONNECTED, common.SERVER_TIMEOUT):
            self.warning("Producer request error %s (%s) for %s "
                         "(%s tries left)", message, code,
                         self.session.url, self._resumes)

            if self._resumes > 0:
                self._resumes -= 1
                if self._paused:
                    self.log("Producer paused, waiting to recover pipelining "
                             "(%d tries left)", self._resumes)
                else:
                    self.log("Recovering pipelining (%d tries left)",
                             self._resumes)
                    self._pipeline()
                return

            self.debug("Too much resuming intents, stopping "
                       "after %d of %s", self._bytes, self.size)

        self._terminate()

    def conditionFail(self, getter, code, message):
        if self._request is None:
            # Already terminated
            return
        self._request = None
        self.warning("Modifications detected while producing %s",
                     self.session.url)
        self._terminate()

    def streamNotAvailable(self, getter, code, message):
        if self._request is None:
            # Already terminated
            return
        self._request = None
        self.warning("%s detected while producing %s",
                     message, self.session.url)
        self._terminate()

    def onData(self, getter, data):
        if self._request is None:
            # Already terminated
            return
        self._write(data)

    def streamDone(self, getter):
        if self._request is None:
            # Already terminated
            return
        self.log("Pipelining finished")
        self._terminate()

    ### Private Methods ###

    def _produce(self):
        self._call = None
        if self.consumer is None:
            # Already terminated
            return

        data = self.session.read(self.offset + self._produced,
                                 abstract.FileDescriptor.bufferSize)

        if data is None:
            # The session can't serve the data, start pipelining
            self._pipeline()
            return

        if data == "":
            # No more data
            self.log("All data served from session")
            self._terminate()
            return

        self._write(data)

        self._call = reactor.callLater(PRODUCING_PERIOD, self._produce)

    def _write(self, data):
        size = len(data)
        self._produced += size
        self.consumer.write(data)

    def _stop(self):
        if self._call is not None:
            self._call.cancel()
            self._call = None

    def _pipeline(self):
        if not self.session.isActive():
            self.log("Session %s not active anymore (%s), "
                     "aborting production of %s",
                     self.session.logName,
                     self.session._state,
                     self.session.url)
            self._terminate()
            return

        self._pipelining = True

        offset = self.offset + self._produced
        size = self.session.size - offset
        mtime = self.session.mtime

        if size == 0:
            self.log("No more data to be retrieved, pipelining finished")
            self._terminate()
            return

        self.debug("Producing %s bytes from offset %d of %s",
                   size, offset, self.session.url)

        self._request = self.reqmgr.retrieve(self, self.session.url,
                                             start=offset, size=size,
                                             ifUnmodifiedSince=mtime)
        self.log("Retrieving data using %s", self._request.logName)

    def _terminate(self):
        if self._request:
            # Doing pipelining
            self._request.cancel()
            self._request = None

        self._stop() # Stopping producing from session

        expected = self.session.size - self.offset
        if self._produced != expected:
            self.warning("Only produced %s of the %s bytes "
                         "starting at %s of %s",
                         self._produced, expected,
                         self.offset, self.session.url)
        else:
            self.log("Finished producing %s bytes starting at %s of %s",
                     self._produced, self.offset, self.session.url)

        self.consumer.unregisterProducer()
        self.consumer.finish()
        self.consumer = None

        self.session.delref()
        self.session = None


class BlockRequester(common.StreamConsumer, log.Loggable):
    """
    Retrieves a block of data using a range request.
    A modification time can be specified for the retrieval to
    fail if the requested file modification time changed.

    The data is returned as a block by triggering the deferred
    returned by calling the retrieve method.

    It can recover request failures up to MAX_RESUME_COUNT times.
    """

    logCategory = "block-requester"

    def __init__(self, reqmgr, url, mtime=None):
        self.reqmgr = reqmgr
        self._url = url
        self._mtime = mtime
        self._data = None
        self._deferred = None
        self._offset = None
        self._size = None
        self._resumes = MAX_RESUME_COUNT

        self.logName = common.log_id(self) # To be able to track the instance

    def retrieve(self, offset, size):
        assert self._deferred is None, "Already retrieving"
        self._deferred = defer.Deferred()
        self._data = []
        self._offset = offset
        self._size = size
        self._curr = 0

        self._retrieve()

        return self._deferred

    def serverError(self, getter, code, message):
        assert self._deferred is not None, "Not retrieving anything"
        if code == common.RANGE_NOT_SATISFIABLE:
            # Simulate EOF
            self._deferred.callback("")
            self._cleanup()
            return
        if code in (common.SERVER_DISCONNECTED, common.SERVER_TIMEOUT):
            self.warning("Block request error: %s (%s)", message, code)
            if self._resumes > 0:
                self._resumes -= 1
                self.debug("Resuming block retrieval from offset %d "
                           "with size %d (%d tries left)",
                           self._offset, self._size, self._resumes)

                self._retrieve()
                return
            self.debug("Too much resuming intents, stopping "
                       "after %d of %d", self._offset, self._size)
        self._deferred.errback(fileprovider.FileError(message))
        self._cleanup()

    def conditionFail(self, getter, code, message):
        assert self._deferred is not None, "Not retrieving anything"
        self._deferred.errback(fileprovider.FileOutOfDate(message))
        self._cleanup()

    def streamNotAvailable(self, getter, code, message):
        assert self._deferred is not None, "Not retrieving anything"
        error = fileprovider.FileOutOfDate(message)
        self._deferred.errback(error)
        self._cleanup()

    def onData(self, getter, data):
        size = len(data)
        self._offset += size
        self._size -= size
        self._data.append(data)

    def streamDone(self, getter):
        data = "".join(self._data)
        self._deferred.callback(data)
        self._cleanup()

    def _retrieve(self):
        self.reqmgr.retrieve(self, self._url, start=self._offset,
                             size=self._size, ifUnmodifiedSince=self._mtime)

    def _cleanup(self):
        self._deferred = None
        self._data = None
