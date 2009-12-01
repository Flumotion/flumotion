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

import errno
import os
import tempfile
import time
import stat

from twisted.internet import defer, threads, protocol, reactor

from flumotion.common import log, common, python, format, errors

from flumotion.component.misc.httpserver import fileprovider

LOG_CATEGORY = "cache-manager"

DEFAULT_CACHE_SIZE = 1000 * 1024 * 1024
DEFAULT_CACHE_DIR = "/tmp/httpserver"
DEFAULT_CLEANUP_ENABLED = True
DEFAULT_CLEANUP_HIGH_WATERMARK = 1.0
DEFAULT_CLEANUP_LOW_WATERMARK = 0.6
ID_CACHE_MAX_SIZE = 1024
TEMP_FILE_POSTFIX = ".tmp"


class CacheManager(object, log.Loggable):

    logCategory = LOG_CATEGORY

    def __init__(self, stats,
                 cacheDir = None,
                 cacheSize = None,
                 cleanupEnabled = None,
                 cleanupHighWatermark = None,
                 cleanupLowWatermark = None,
                 cacheRealm = None):

        if cacheDir is None:
            cacheDir = DEFAULT_CACHE_DIR
        if cacheSize is None:
            cacheSize = DEFAULT_CACHE_SIZE
        if cleanupEnabled is None:
            cleanupEnabled = DEFAULT_CLEANUP_ENABLED
        if cleanupHighWatermark is None:
            cleanupHighWatermark = DEFAULT_CLEANUP_HIGH_WATERMARK
        if cleanupLowWatermark is None:
            cleanupLowWatermark = DEFAULT_CLEANUP_LOW_WATERMARK

        self.stats = stats
        self._cacheDir = cacheDir
        self._cacheSize = cacheSize # in bytes
        self._cleanupEnabled = cleanupEnabled
        highWatermark = max(0.0, min(1.0, float(cleanupHighWatermark)))
        lowWatermark = max(0.0, min(1.0, float(cleanupLowWatermark)))

        self._cachePrefix = (cacheRealm and (cacheRealm + ":")) or ""

        self._identifiers = {} # {path: identifier}

        self.info("Cache Manager initialized")
        self.debug("Cache directory: '%s'", self._cacheDir)
        self.debug("Cache size: %d bytes", self._cacheSize)
        self.debug("Cache cleanup enabled: %s", self._cleanupEnabled)

        common.ensureDir(self._cacheDir, "cache")

        self._cacheUsage = None
        self._cacheUsageLastUpdate = None
        self._lastCacheTime = None

        self._cacheMaxUsage = self._cacheSize * highWatermark # in bytes
        self._cacheMinUsage = self._cacheSize * lowWatermark # in bytes

    def setUp(self):
        """
        Initialize the cache manager

        @return a defer
        @raise: OSError or FlumotionError
        """
        # Initialize cache usage
        return self.updateCacheUsage()

    def getIdentifier(self, path):
        """
        The returned identifier is a digest of the path encoded in hex string.
        The hash function used is SHA1.
        It caches the identifiers in a dictionary indexed by path and with
        a maximum number of entry specified by the constant ID_CACHE_MAX_SIZE.

        @return: an identifier for path.
        """
        ident = self._identifiers.get(path, None)
        if ident is None:
            hash = python.sha1()
            hash.update(self._cachePrefix + path)
            ident = hash.digest().encode("hex").strip('\n')
            # Prevent the cache from growing endlessly
            if len(self._identifiers) >= ID_CACHE_MAX_SIZE:
                self._identifiers.clear()
            self._identifiers[path] = ident
        return ident

    def getCachePath(self, path):
        """
        @return: the cached file path for a path.
        """
        ident = self.getIdentifier(path)
        return os.path.join(self._cacheDir, ident)

    def getTempPath(self, path):
        """
        @return: a temporary file path for a path.

        Don't use this function, it's provided for compatibility.
        Use newTempFile() instead.
        """
        ident = self.getIdentifier(path)
        return os.path.join(self._cacheDir, ident + TEMP_FILE_POSTFIX)

    def updateCacheUsageStatistics(self):
        self.stats.onEstimateCacheUsage(self._cacheUsage, self._cacheSize)

    def _updateCacheUsage(self, usage):
        self._cacheUsageLastUpdate = time.time()
        self._cacheUsage = usage
        self.updateCacheUsageStatistics()
        return usage

    def updateCacheUsage(self):
        """
        @return: a defered with the cache usage in bytes.
        @raise: OSError or FlumotionError
        """

        # Only calculate cache usage if the cache directory
        # modification time changed since the last time we looked at it.
        try:
            cacheTime = os.path.getmtime(self._cacheDir)
        except OSError, e:
            return defer.fail(e)

        if ((self._cacheUsage is None) or (self._lastCacheTime < cacheTime)):
            self._lastCacheTime = cacheTime

            du = ProcessOutputHelper()

            reactor.callWhenRunning(reactor.spawnProcess, du,
                                    "du", ["du", '-bs', self._cacheDir], {})
            d = du.getOutput()
            d.addCallback(lambda o: int(o.split('\t', 1)[0]))
            d.addCallback(self._updateCacheUsage)
            return d
        else:
            return defer.succeed(self._cacheUsage)

    def _rmfiles(self, files):
        try:
            for path in files:
                os.remove(path)
        except OSError, e:
            if e.errno != errno.ENOENT:
                # TODO: is warning() thread safe?
                self.warning("Error cleaning cached file: %s", str(e))

    def _setCacheUsage(self, _, usage):
        # Update the cache usage
        self._cacheUsage = usage
        self._cacheUsageLastUpdate = time.time()
        return usage

    def _cleanUp(self):
        # Update cleanup statistics
        self.stats.onCleanup()
        # List the cached files with file state
        try:
            listdir = os.listdir(self._cacheDir)
        except OSError, e:
            return defer.fail(e)

        files = []
        for f in listdir:
            f = os.path.join(self._cacheDir, f)
            # There's a possibility of getting an error on os.stat here.
            try:
                files.append((f, os.stat(f)))
            except OSError, e:
                if e.errno == errno.ENOENT:
                    pass
                else:
                    return defer.fail(e)

        # Calculate the cached file total size
        usage = sum([d[1].st_size for d in files])
        # Delete the cached file starting by the oldest accessed ones
        files.sort(key=lambda d: d[1].st_atime)
        rmlist = []
        for path, info in files:
            usage -= info.st_size
            rmlist.append(path)
            if usage <= self._cacheMinUsage:
                # We reach the cleanup limit
                self.debug('cleaned up, cache use is now %sbytes',
                    format.formatStorage(usage))
                break
        d = threads.deferToThread(self._rmfiles, rmlist)
        d.addBoth(self._setCacheUsage, usage)
        return d

    def _allocateCacheSpaceAfterCleanUp(self, usage, size):
        if (self._cacheUsage + size) >= self._cacheSize:
            # There is not enough space, allocation failed
            self.updateCacheUsageStatistics()
            self.debug('not enough space in cache, '
                       'cannot cache %d > %d' %
                       (self._cacheUsage + size, self._cacheSize))
            return None

        # There is enough space to allocate, allocation succeed
        self._cacheUsage += size
        self.updateCacheUsageStatistics()
        return (self._cacheUsageLastUpdate, size)

    def _allocateCacheSpace(self, usage, size):
        if usage + size < self._cacheMaxUsage:
            self._cacheUsage += size
            self.updateCacheUsageStatistics()
            return defer.succeed((self._cacheUsageLastUpdate, size))

        self.debug('cache usage will be %sbytes, need more cache',
            format.formatStorage(usage + size))

        if not self._cleanupEnabled:
            # No space available and cleanup disabled: allocation failed.
            self.debug('not allowed to clean up cache, '
                       'so cannot cache %d' % size)
            return defer.succeed(None)

        d = self._cleanUp()
        d.addCallback(self._allocateCacheSpaceAfterCleanUp, size)
        return d

    def allocateCacheSpace(self, size):
        """
        Try to reserve cache space.

        If there is not enough space and the cache cleanup is enabled,
        it will delete files from the cache starting with the ones
        with oldest access time until the cache usage drops below
        the fraction specified by the property cleanup-low-threshold.

        Returns a 'tag' that should be used to 'free' the cache space
        using releaseCacheSpace.
        This tag is needed to better estimate the cache usage,
        if the cache usage has been updated since cache space
        has been allocated, freeing up the space should not change
        the cache usage estimation.

        @param size: size to reserve, in bytes
        @type  size: int

        @return: an allocation tag or None if the allocation failed.
        @rtype:   defer to tuple
        """
        d = self.updateCacheUsage()
        d.addCallback(self._allocateCacheSpace, size)
        return d

    def releaseCacheSpace(self, tag):
        """
        Low-level function to release reserved cache space.
        """
        lastUpdate, size = tag
        if lastUpdate == self._cacheUsageLastUpdate:
            self._cacheUsage -= size
            self.updateCacheUsageStatistics()

    def openCacheFile(self, path):
        """
        @return: a defer to a CacheFile instance or None
        """
        try:
            return defer.succeed(CachedFile(self, path))
        except:
            return defer.succeed(None)

    def _newTempFile(self, tag, path, size, mtime=None):
        # if allocation fails
        if tag is None:
            return None

        try:
            return TempFile(self, path, tag, size, mtime)
        except OSError, e:
            return None

    def newTempFile(self, path, size, mtime=None):
        """
        @return: a defer to a TempFile instance or None
        """
        d = self.allocateCacheSpace(size)
        d.addCallback(self._newTempFile, path, size, mtime)
        return d


class CachedFile:
    """
    Read only.

    See cachedprovider.py
    @raise: OSError
    """

    def __init__(self, cachemgr, resPath):
        cachedPath = cachemgr.getCachePath(resPath)
        file = open(cachedPath, 'rb')
        stat = os.fstat(file.fileno())

        cachemgr.log("Opened cached file %s [fd %d]",
                     cachedPath, file.fileno())

        self.name = cachedPath
        self.file = file
        self.stat = stat

    def unlink(self):
        """
        Delete the cached file from filesystem, unless the current
        file is more recent. However, this is not done atomically...
        """
        try:
            s = os.stat(self.name)
            if (s[stat.ST_MTIME] > self.stat[stat.ST_MTIME]):
                return
            os.unlink(self.name)
        except OSError, e:
            pass

    def __getattr__(self, name):
        file = self.__dict__['file']
        a = getattr(file, name)
        if type(a) != type(0):
            setattr(self, name, a)
        return a


class TempFile:
    """
    See cachedprovider.py
    """

    def __init__(self, cachemgr, resPath, tag, size, mtime=None):
        """
        @raise: OSError
        """
        self.tag = tag
        self.cachemgr = cachemgr
        self._completed = False
        self._finishPath = cachemgr.getCachePath(resPath)
        self.mtime = mtime
        self.file = None
        self.size = size

        fd, tempPath = tempfile.mkstemp(TEMP_FILE_POSTFIX,
                                        LOG_CATEGORY, cachemgr._cacheDir)
        cachemgr.log("Created temporary file '%s' [fd %d]",
                     tempPath, fd)
        self.file = os.fdopen(fd, "w+b")
        cachemgr.log("Truncating temporary file to size %d", size)
        self.file.truncate(size)
        self.stat = os.fstat(self.file.fileno())
        self.name = tempPath

    def __getattr__(self, name):
        file = self.__dict__['file']
        a = getattr(file, name)
        if type(a) != type(0):
            setattr(self, name, a)
        return a

    def setModificationTime(self, mtime=None):
        """
        Set file modification time.
        """
        if (mtime):
            self.mtime = mtime
        try:
            if self.mtime:
                mtime = self.mtime
                atime = int(time.time())
                self.cachemgr.log("Setting cache file "
                                  "modification time to %d", mtime)
                # FIXME: Should use futimes, but it's not wrapped by python
                os.utime(self.name, (atime, mtime))
        except OSError, e:
            if e.errno == errno.ENOENT:
                self.cachemgr.releaseCacheSpace(self.tag)
            else:
                self.cachemgr.warning(
                    "Failed to update modification time of temporary "
                    "file: %s", log.getExceptionMessage(e))

    def close(self):
        """
        @raise: OSError
        """
        if self.cachemgr is None:
            return

        try:
            if not self._completed:
                self.cachemgr.log("Temporary file canceled '%s' [fd %d]",
                                  self.name, self.fileno())
                self.cachemgr.releaseCacheSpace(self.tag)
                os.unlink(self.name)
        except OSError, e:
            pass

        self.file.close()
        self.setModificationTime()
        self.file = None
        self.cachemgr = None

    def write(self, str):
        """
        @raise: OSError
        @raise: IOError
        allocated size
        """
        if (self.file.tell() + len(str) > self.size):
            raise IOError("Cache size overrun (%d > %d)" %
                          (self.file.tell() + len(str), self.size))
        return self.file.write(str)

    def complete(self, checkSize=False):
        """
        Make the temporary file available as a cached file.
        Do NOT close the file, afterward the file can be used
        as a normal CachedFile instance.
        Do not raise exceptions on rename error.

        @raise: IOError if checkSize and tell() != size
        """
        if self.cachemgr is None:
            return
        if self._completed:
            return
        self._completed = True

        _, size = self.tag
        if (self.tell() != size and checkSize):
            raise IOError("Did not reach end of file")

        self.cachemgr.log("Temporary file completed '%s' [fd %d]",
                          self.name, self.fileno())
        try:
            if self.mtime is not None:
                mtime = os.path.getmtime(self._finishPath)
                if mtime > self.mtime:
                    self.cachemgr.log("Did not complete(), "
                                      "a more recent version exists already")
                    os.unlink(self.name)
                    self.name = self._finishPath
                    return
        except OSError, e:
            pass

        try:
            os.rename(self.name, self._finishPath)
        except OSError, e:
            if e.errno == errno.ENOENT:
                self.cachemgr.releaseCacheSpace(self.tag)
                self.cachemgr.warning(
                    "Failed to rename file '%s': %s" %
                    (self.name, str(e)))
                return

        self.setModificationTime()

        self.name = self._finishPath
        self.cachemgr.log("Temporary file renamed to '%s' [fd %d]",
                          self._finishPath, self.fileno())


class ProcessOutputHelper(protocol.ProcessProtocol):
    """
    I am a helper to get only stdout from a process. See ChangeLog for
    the reasons why I exist, after several failing attemps from my
    creator.
    """

    def __init__(self):
        self.data = ""
        self.result = defer.Deferred()

    def getOutput(self):
        return self.result

    def connectionMade(self):
        self.transport.closeStdin()

    def outReceived(self, data):
        self.data = self.data + data

    def processEnded(self, status):
        self.result.callback(self.data)


def main(argv=None):
    # Functional tests
    import random

    CACHE_SIZE = 1 * 1024 * 1024
    MAX_CLEANUPS = 512

    class DummyStats:

        def __init__(self):
            self.oncleanup = 0

        def info():
            pass

        def onEstimateCacheUsage(self, usage, size):
            #print "Stat: " + str(usage / (1024))\
            #    + "k / " + str(size / (1024)) + "k"
            pass

        def onCleanup(self):
            self.oncleanup += 1
            print "OnCleanup"

    def makeTemp(tag, size, m, name):
        t = TempFile(m, name, tag, size)
        return t

    def completeAndClose(t):
        try:
            t.complete()
            t.close()
        except:
            print "Got a complete exception"

    def fillTestCache(manager):
        i = 0
        while (manager.stats.oncleanup < MAX_CLEANUPS):
            i += 1
            filesize = 4096 * random.randint(1, 30)
            d = manager.newTempFile(str(i), filesize)
            d.addCallback(completeAndClose)

    def releaseCacheSpace(tag, m):
        print "gotCacheSpace: ", tag
        m.releaseCacheSpace(tag)

    def checkUsage(usage, m, check):
        if (not check(m._cacheUsage)):
            print "Cache overrun!!! %d/%d" % (m._cacheUsage, m._cacheSize)

    def openCacheAndClose(_, m, name):
        d = m.openCacheFile(name)
        d.addCallback(lambda f: f.close())
        return d

    def checkMiss(_):
        if (_ == "cacheMiss"):
            return
        raise errors.FlumotionError("an error")

    def runTests():
        # low-level cache requests
        d = m.allocateCacheSpace(1024)
        d.addCallback(releaseCacheSpace, m)
        d.addCallback(checkUsage, m, lambda u: u == 0)

        d = m.allocateCacheSpace(CACHE_SIZE / 2)
        d.addCallback(makeTemp, CACHE_SIZE / 2, m, "test")
        d.addCallback(lambda t: t.close())
        d.addCallback(checkUsage, m, lambda u: u == 0)

        d = m.allocateCacheSpace(CACHE_SIZE / 2)
        d.addCallback(makeTemp, CACHE_SIZE / 2, m, "test2")
        d.addCallback(completeAndClose)
        d.addCallback(checkUsage, m, lambda u: u > 0)

        # check hit and miss
        m2 = CacheManager(DummyStats(), cachedir, CACHE_SIZE, True, 0.5, 0.3)
        d = m2.newTempFile("test3", 12000)
        d.addCallback(completeAndClose)
        d.addCallback(openCacheAndClose, m, "test3")

        d = openCacheAndClose(None, m, "test4_do_not_exists")
        d.addErrback(lambda _: "cacheMiss")
        d.addCallback(checkMiss)

        # multi-thread test, full of races :)
        threads.deferToThread(fillTestCache, m)
        threads.deferToThread(fillTestCache, m)
        threads.deferToThread(fillTestCache, m)

        # check usage
        m.updateCacheUsage().addCallback(checkUsage, m,
                                         lambda u: u < CACHE_SIZE * 1.10)


    cachedir = os.environ['HOME'] + "/tmp/cache"
    m = CacheManager(DummyStats(), cachedir, CACHE_SIZE, True, 0.0, 0.0)
    d = m.setUp()

    m.addCallback(lambda x: runTests())

    reactor.callLater(3, reactor.stop)
    reactor.run()
    return 0

if __name__ == '__main__':
    import sys
    status = main()
    sys.exit(status)
