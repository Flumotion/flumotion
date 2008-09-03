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

import errno
import os
import sha # hashlib is not available with python 2.4
import stat
import tempfile
import threading
import time

from twisted.internet import defer, reactor, abstract

from flumotion.common import log
from flumotion.component.misc.httpserver import cachestats
from flumotion.component.misc.httpserver import fileprovider
from flumotion.component.misc.httpserver import localpath
from flumotion.component.misc.httpserver.fileprovider import FileClosedError
from flumotion.component.misc.httpserver.fileprovider import FileError
from flumotion.component.misc.httpserver.fileprovider import NotFoundError


SEEK_SET = 0 # os.SEEK_SET is not defined in python 2.4
DEFAULT_CACHE_SIZE = 1024
DEFAULT_CLEANUP_THRESHOLD = 100
DEFAULT_CLEANUP_MAX_USAGE = 60
FILE_COPY_BUFFER_SIZE = abstract.FileDescriptor.bufferSize
TEMP_FILE_POSTFIX = ".tmp"
MAX_LOGNAME_SIZE = 30
ID_CACHE_MAX_SIZE = 1024


LOG_CATEGORY = "fileprovider-localcached"

_errorLookup = {errno.ENOENT: NotFoundError,
                errno.EISDIR: fileprovider.CannotOpenError,
                errno.EACCES: fileprovider.AccessError}


class FileProviderLocalCachedPlug(fileprovider.FileProvider, log.Loggable):
    """

    WARNING: Currently does not work properly in combination with rate-control.

    I'm caching the files taken from a mounted
    network file system to a shared local directory.
    Multiple instances can share the same cache directory,
    but it's recommended to use slightly different values
    for the property cleanup-threshold.
    I'm using the directory access time to know when
    the cache usage changed and keep an estimation
    of the cache usage for statistics.

    I'm creating a unique thread to do the file copying block by block,
    for all files to be copied to the cache.
    Using a thread instead of a reactor.callLater 'loop' allow for
    higher copy throughput and do not slow down the mail loop when
    lots of files are copied at the same time.
    Simulations with real request logs show that using a thread
    gives better results than the equivalent asynchronous implementation.

    Properties:
        path: The absolute path of the root directory
              from which the files are served.
        cache-dir: The absolute path of the cache directory.
        cache-size: The maximum size of the cache in MByte.
        cleanup-enabled: If set to false and the cache is full,
                         the plug will not delete files to free
                         disk space. It will serve the files directly
                         form the network file system.
        cleanup-threshold: The cache usage percentage the will trigger
                           a cache cleanup to be done.
                           If more than one instance are sharing the same
                           cache directory, it's recommended to use
                           slightly different value for each instances.
        cleanup-max-usage: The maximum usage percentage after cleanup.
                           When doing a cleanup, older files will be deleted
                           until the cache usage drop below this percentage.
    """

    logCategory = LOG_CATEGORY

    def __init__(self, args):
        props = args['properties']
        self._sourceDir = props.get('path')
        self._cacheDir = props.get('cache-dir', "/tmp")
        cacheSizeInMB = int(props.get('cache-size', DEFAULT_CACHE_SIZE))
        self._cacheSize = cacheSizeInMB * 1024**2
        self._cleanupEnabled = props.get('cleanup-enabled', True)
        threshold = props.get('cleanup-threshold', DEFAULT_CLEANUP_THRESHOLD)
        self._cleanupThreshold = max(0, min(100, int(threshold)))
        maxUsage = props.get('cleanup-max-usage', DEFAULT_CLEANUP_MAX_USAGE)
        self._cleanupMaxUsage = max(0, min(100, int(maxUsage)))
        self._identifiers = {} # {path: identifier}
        self._sessions = {} # {CopySession: None}
        self._index = {} # {path: CopySession}

        self.info("Cached file provider initialized")
        self.debug("Source directory: '%s'", self._sourceDir)
        self.debug("Cache directory: '%s'", self._cacheDir)
        self.debug("Cache size: %d MB", self._cacheSize)
        self.debug("Cache cleanup enabled: %s", self._cleanupEnabled)

        self._cacheUsage = None
        self._cacheUsageLastUpdate = None
        self._lastCacheTime = None
        self._cacheMaxUsage = (self._cacheSize * self._cleanupThreshold) / 100
        self._cacheMinUsage = (self._cacheSize * self._cleanupMaxUsage) / 100
        self.stats = cachestats.CacheStatistics()

        # Initialize cache usage
        self.updateCacheUsage()

        # Startup copy thread
        self._event = threading.Event()
        self._thread = CopyThread(self)
        self._thread.start()

    def startStatsUpdates(self, updater):
        #FIXME: This is temporary. Should be done with plug UI.
        # Used for the UI to know which plug is used
        updater.update("provider-name", "fileprovider-localcached")
        self.stats.startUpdates(updater)

    def stopStatsUpdates(self):
        self.stats.stopUpdates()

    def getRootPath(self):
        if self._sourceDir is None:
            return None
        return LocalPath(self, self._sourceDir)


    ## Protected Methods ##

    def getLogName(self, path, id=None):
        """
        Returns a log name for a path, shortened to a maximum size
        specified by the global variable MAX_LOGNAME_SIZE.
        The log name will be the filename part of the path postfixed
        by the id in brackets if id is not None.
        """
        filename = os.path.basename(path)
        basename, postfix = os.path.splitext(filename)
        if id is not None:
            postfix += "[%s]" % id
        prefixMaxLen = MAX_LOGNAME_SIZE - len(postfix)
        if len(basename) > prefixMaxLen:
            basename = basename[:prefixMaxLen-1] + "*"
        return basename + postfix

    def getIdentifier(self, path):
        """
        Returns an identifier for a path.
        The identifier is a digest of the path encoded in hex string.
        The hash function used is SHA1.
        It caches the identifiers in a dictionary indexed by path and with
        a maximum number of entry specified by the constant ID_CACHE_MAX_SIZE.
        """
        ident = self._identifiers.get(path, None)
        if ident is None:
            hash = sha.sha()
            hash.update(path)
            ident = hash.digest().encode("hex").strip('\n')
            # Prevent the cache from growing endlessly
            if len(self._identifiers) >= ID_CACHE_MAX_SIZE:
                self._identifiers.clear()
            self._identifiers[path] = ident
        return ident

    def getCachePath(self, path):
        ident = self.getIdentifier(path)
        return os.path.join(self._cacheDir, ident)

    def getTempPath(self, path):
        ident = self.getIdentifier(path)
        return os.path.join(self._cacheDir, ident + TEMP_FILE_POSTFIX)

    def updateCacheUsageStatistics(self):
        self.stats.onEstimateCacheUsage(self._cacheUsage, self._cacheSize)

    def updateCacheUsage(self):
        # Only calculate cache usage if the cache directory
        # modification time changed since the last time we looked at it.
        cacheTime = os.path.getmtime(self._cacheDir)
        if ((self._cacheUsage is None) or (self._lastCacheTime < cacheTime)):
            self._lastCacheTime = cacheTime
            os.chdir(self._cacheDir)
            sizes = [os.path.getsize(f) for f in os.listdir('.')]
            self._cacheUsage = sum(sizes)
            self.updateCacheUsageStatistics()
            self._cacheUsageLastUpdate = time.time()
        return self._cacheUsage

    def allocateCacheSpace(self, size):
        """
        Try to reserve cache space.
        If there is not enough space and the cache cleanup is enabled,
        it will delete files from the cache starting with the ones
        with oldest access time until the cache usage drop below
        the percentage specified by the property cleanup-max-usage.
        Returns a 'tag' that should be used to 'free' the cache space.
        This tag is needed to better estimate the cache usage,
        if the cache usage has been updated since cache space
        has been allocated, freeing up the space should not change
        the cache usage estimation.
        @returns: an allocation tag or None if the allocation failed.
        @rtype:   tuple
        """
        usage = self.updateCacheUsage()
        if (usage + size) < self._cacheMaxUsage:
            self._cacheUsage += size
            self.updateCacheUsageStatistics()
            return (self._cacheUsageLastUpdate, size)
        if not self._cleanupEnabled:
            # No space available and cleanup disabled: allocation failed.
            return None
        # Update cleanup statistics
        self.stats.onCleanup()
        # List the cached files with file state
        os.chdir(self._cacheDir)
        files = [(f, os.stat(f)) for f in os.listdir('.')]
        # Calculate the cached file total size
        usage = sum([d[1].st_size for d in files])
        # Delete the cached file starting by the oldest accessed ones
        files.sort(key=lambda d: d[1].st_atime)
        for path, info in files:
            try:
                os.remove(path)
                usage -= info.st_size
            except OSError, e:
                if e.errno == errno.ENOENT:
                    # Already been deleted by another process,
                    # but subtract the size anyway
                    usage -= info.st_size
                else:
                    self.warning("Error cleaning cached file: %s", str(e))
            if usage <= self._cacheMinUsage:
                # We reach the cleanup limit
                break
        # Update the cache usage
        self._cacheUsage = usage
        self._cacheUsageLastUpdate = time.time()
        if (usage + size) < self._cacheSize:
            # There is enough space to allocate, allocation succeed
            self._cacheUsage += size
            self.updateCacheUsageStatistics()
            return (self._cacheUsageLastUpdate, size)
        # There is no enough space, allocation failed
        self.updateCacheUsageStatistics()
        return None

    def releaseCacheSpace(self, tag):
        lastUpdate, size = tag
        if lastUpdate == self._cacheUsageLastUpdate:
            self._cacheUsage -= size
            self.updateCacheUsageStatistics()

    def getCopySession(self, path):
        return self._index.get(path, None)

    def createCopySession(self, path, file, info):
        # First outdate existing session for the path
        self.outdateCopySession(path)
        # Then create a new one
        session = CopySession(self, path, file, info)
        self._index[path] = session
        return session

    def outdateCopySession(self, path):
        session = self._index.get(path, None)
        if session is not None:
            session.outdate()

    def removeCopySession(self, session):
        path = session.sourcePath
        if path in self._index:
            del self._index[path]
        self.disableSession(session)

    def activateSession(self, session):
        self.debug("Starting Copy Session '%s' (%d)",
                   session.logName, len(self._sessions))
        if session in self._sessions:
            return
        self._sessions[session] = None
        self._activateCopyLoop()

    def disableSession(self, session):
        self.debug("Stopping Copy Session '%s' (%d)",
                   session.logName, len(self._sessions))
        if session in self._sessions:
            del self._sessions[session]
        if not self._sessions:
            self._disableCopyLoop()

    def _activateCopyLoop(self):
        self._event.set()

    def _disableCopyLoop(self):
        self._event.clear()


class LocalPath(localpath.LocalPath, log.Loggable):

    logCategory = LOG_CATEGORY

    def __init__(self, plug, path):
        localpath.LocalPath.__init__(self, path)
        self.logName = plug.getLogName(path)
        self.plug = plug

    def child(self, name):
        childpath = self._getChildPath(name)
        if not os.path.exists(childpath):
            # Delete the cached file and outdate the copying session
            self.plug.outdateCopySession(childpath)
            self._removeCachedFile(childpath)
            raise NotFoundError("Path '%s' not found" % childpath)
        return LocalPath(self.plug, childpath)

    def open(self):
        return CachedFile(self.plug, self.path, self.mimeType)


    ## Private Methods ##

    def _removeCachedFile(self, sourcePath):
        cachePath = self.plug.getCachePath(sourcePath)
        try:
            os.remove(cachePath)
            self.debug("Deleted cached file '%s'", cachePath)
        except OSError, e:
            if e.errno != errno.ENOENT:
                self.warning("Error deleting file: %s", str(e))


class CopyThread(threading.Thread, log.Loggable):

    logCategory = LOG_CATEGORY

    def __init__(self, plug):
        threading.Thread.__init__(self)
        self.plug = plug

    def run(self):
        while True:
            sessions = self.plug._sessions.keys()
            for session in sessions:
                try:
                    session.doServe()
                except Exception, e:
                    log.warning("Error during async file serving: %s",
                                log.getExceptionMessage(e))
                try:
                    session.doCopy()
                except Exception, e:
                    log.warning("Error during file copy: %s",
                                log.getExceptionMessage(e))
            self.plug._event.wait()


class CopySessionCanceled(Exception):
    pass


class CopySession(log.Loggable):
    """
    I'm serving a file at the same time I'm copying it
    from the network file system to the cache.
    If the client ask for data not yet copied, the source file
    read operation is delegated the the copy thread as an asynchronous
    operation because file seeking/reading is not thread safe.

    The copy session have to open two times the temporary file,
    one for read-only and one for write only,
    because closing a read/write file change the modification time.
    We want the modification time to be set to a known value
    when the copy is finished even keeping read access to the file.

    The session manage a reference counter to know how many TempFileDelegate
    instances are using the session to delegate read operations.
    This is done for two reasons:
        - To avoid circular references by have the session manage
          a list of delegate instances.
        - If not canceled, sessions should not be deleted
          when no delegates reference them anymore. So weakref cannot be used.
    """

    logCategory = LOG_CATEGORY

    def __init__(self, plug, sourcePath, sourceFile, sourceInfo):
        self.plug = plug
        self.logName = plug.getLogName(sourcePath, sourceFile.fileno())
        self.copying = None # Not yet started
        self.sourcePath = sourcePath
        self.tempPath = plug.getTempPath(sourcePath)
        self.cachePath = plug.getCachePath(sourcePath)
        # The size and modification time is not supposed to change over time
        self.mtime = sourceInfo[stat.ST_MTIME]
        self.size = sourceInfo[stat.ST_SIZE]
        self._sourceFile = sourceFile
        self._canceled = False # True when a session has been outdated
        self._wTempFile = None
        self._rTempFile = None
        self._allocTag = None # Tag used to identify cache allocations
        self._waitCancel = None
        # List of the pending read from source file
        self._pending = [] # [(position, size, defer),]
        self._refCount = 0
        self._copied = 0 # None when the file is fully copied
        self._correction = 0 # Used to take into account copies data for stats
        self._startCopying()

    def outdate(self):
        self.log("Copy session outdated")
        self._cancelSession()

    def read(self, position, size, stats):
        # If the temporary file is open for reading
        if self._rTempFile:
            # And the needed data is already downloaded
            # Safe to read because it's not used by the copy thread
            if (self._copied is None) or ((position + size) <= self._copied):
                try:
                    self._rTempFile.seek(position)
                    data = self._rTempFile.read(size)
                    # Adjust the cache/source values to take copy into account
                    size = len(data)
                    # It's safe to use and modify self._correction even if
                    # it's used by the copy thread because the copy thread
                    # only add and the main thread only subtract.
                    # The only thing that could append it's a less accurate
                    # correction...
                    diff = min(self._correction, size)
                    self._correction -= diff
                    stats.onBytesRead(0, size, diff)
                    return data
                except Exception, e:
                    self.warning("Failed to read from temporary file: %s",
                                 log.getExceptionMessage(e))
                    self._cancelSession()
        # If the source file is not open anymore, we can't continue
        if self._sourceFile is None:
            raise FileError("File caching error, cannot proceed")
        # Otherwise read the data directly from the source
        try:
            # It's safe to not use Lock, because simple type operations
            # are thread safe, and even if the copying state change
            # from True to False, _onCopyFinished will be called
            # later in the same thread and will process pending reads.
            if self.copying:
                # If we are currently copying the source file,
                # we defer the file read to the copying thread
                # because we can't read a file from two threads.
                d = defer.Deferred()

                def updateStats(data):
                    stats.onBytesRead(len(data), 0, 0)
                    return data

                d.addCallback(updateStats)
                self._pending.append((position, size, d))
                return d
            # Not copying, it's safe to read directly
            self._sourceFile.seek(position)
            data = self._sourceFile.read(size)
            stats.onBytesRead(len(data), 0, 0)
            return data
        except IOError, e:
            cls = _errorLookup.get(e.errno, FileError)
            raise cls("Failed to read source file: %s" % str(e))

    def incRef(self):
        self._refCount += 1

    def decRef(self):
        self._refCount -= 1
        # If there is only one client and the session has been canceled,
        # stop copying and and serve the source file directly
        if (self._refCount == 1) and self._canceled:
            # Cancel the copy and close the writing temporary file.
            self._cancelCopy(False, True)
        # We close if not still copying source file
        if (self._refCount == 0) and (self._wTempFile is None):
            self.close()

    def close(self):
        if self.plug is not None:
            self.log("Closing copy session")
            # Cancel the copy, close the source file and the writing temp file.
            self._cancelCopy(True, True)
            self._closeReadTempFile()
            self.plug.removeCopySession(self)
            self.plug = None

    def doServe(self):
        if not (self.copying and self._pending):
            # Nothing to do anymore.
            return False
        # We have pending source file read operations
        position, size, d = self._pending.pop(0)
        self._sourceFile.seek(position)
        data = self._sourceFile.read(size)
        # Call the deferred in the main thread
        reactor.callFromThread(d.callback, data)
        return len(self._pending) > 0

    def doCopy(self):
        # Called in the copy thread context.
        if not self.copying:
            # Nothing to do anymore.
            return False
        # Copy a buffer from the source file to the temporary writing file
        cont = True
        try:
            # It's safe to use self._copied, because it's only set
            # by the copy thread during copy.
            self._sourceFile.seek(self._copied)
            self._wTempFile.seek(self._copied)
            data = self._sourceFile.read(FILE_COPY_BUFFER_SIZE)
            self._wTempFile.write(data)
        except IOError, e:
            self.warning("Failed to copy source file: %s",
                         log.getExceptionMessage(e))
            # Abort copy and cancel the session
            self.copying = False
            reactor.callFromThread(self.plug.disableSession, self)
            reactor.callFromThread(self._cancelSession)
            # Do not continue
            cont = False
        else:
            size = len(data)
            self._copied += size
            self._correction += size
            if  size < FILE_COPY_BUFFER_SIZE:
                # Stop copying
                self.copying = False
                reactor.callFromThread(self.plug.disableSession, self)
                reactor.callFromThread(self._onCopyFinished)
                cont = False
        # Check for cancellation
        if self._waitCancel:
            # Copy has been canceled
            self.copying = False
            reactor.callFromThread(self.plug.disableSession, self)
            reactor.callFromThread(self._onCopyCanceled, *self._waitCancel)
            return False
        return cont


    ## Private Methods ##

    def _allocCacheSpace(self):
        # Retrieve a cache allocation tag, used to track the cache free space
        tag = self.plug.allocateCacheSpace(self.size)
        if tag is None:
            return False
        self._allocTag = tag
        return True

    def _releaseCacheSpace(self):
        if not (self._canceled or self._allocTag is None):
            self.plug.releaseCacheSpace(self._allocTag)
        self._allocTag = None

    def _cancelSession(self):#
        if not self._canceled:
            self.log("Canceling copy session")
            # Not a valid copy session anymore
            self._canceled = True
            # If there is no more than 1 client using the session,
            # stop copying and and serve the source file directly
            if self._refCount <= 1:
                # Cancel and close the temp write file.
                self._cancelCopy(False, True)

    def _startCopying(self):
        self.log("Start copy session")
        # First ensure there is not already a temporary file
        self._removeTempFile()
        # Reserve cache space, may trigger a cache cleanup
        if not self._allocCacheSpace():
            # No free space, proxying source file directly
            self._cancelSession()
            return
        self.plug.stats.onCopyStarted()
        # Then open a transient temporary files
        try:
            fd, transientPath = tempfile.mkstemp(".tmp", LOG_CATEGORY)
            self.log("Created transient file '%s'", transientPath)
            self._wTempFile = os.fdopen(fd, "wb")
            self.log("Opened temporary file for writing [fd %d]",
                     self._wTempFile.fileno())
            self._rTempFile = file(transientPath, "rb")
            self.log("Opened temporary file for reading [fd %d]",
                     self._rTempFile.fileno())
        except IOError, e:
            self.warning("Failed to open temporary file: %s",
                         log.getExceptionMessage(e))
            self._cancelSession()
            return
        # Truncate it to the source size
        try:
            self.log("Truncating temporary file to size %d", self.size)
            self._wTempFile.truncate(self.size)
        except IOError, e:
            self.warning("Failed to truncate temporary file: %s",
                         log.getExceptionMessage(e))
            self._cancelSession()
            return
        # And move it to the real temporary file path
        try:
            self.log("Renaming transient file to '%s'", self.tempPath)
            os.rename(transientPath, self.tempPath)
        except IOError, e:
            self.warning("Failed to rename transient temporary file: %s",
                         log.getExceptionMessage(e))
        # And start copying
        self.debug("Start caching '%s' [fd %d]",
                   self.sourcePath, self._sourceFile.fileno())
        # Activate the copy
        self.copying = True
        self.plug.activateSession(self)

    def _cancelCopy(self, closeSource, closeTempWrite):
        if self.copying:
            self.log("Canceling file copy")
            if self._waitCancel:
                # Already waiting for cancellation.
                return
            self.debug("Cancel caching '%s' [fd %d]",
                       self.sourcePath, self._sourceFile.fileno())
            # Disable the copy, we do not modify copying directly
            # to let the copying thread terminate current operations.
            # The file close operation are deferred.
            self._waitCancel = (closeSource, closeTempWrite)
            return
        # No pending copy, we can close the files
        if closeSource:
            self._closeSourceFile()
        if closeTempWrite:
            self._closeWriteTempFile()

    def _onCopyCanceled(self, closeSource, closeTempWrite):
        self.log("Copy session canceled")
        # Called when the copy thread really stopped to read/write
        self._waitCancel = None
        self.plug.stats.onCopyCanceled(self.size, self._copied)
        # Resolve all pending source read operations
        for position, size, d in self._pending:
            if self._sourceFile is None:
                d.errback(CopySessionCanceled())
            else:
                try:
                    self._sourceFile.seek(position)
                    data = self._sourceFile.read(size)
                    d.callback(data)
                except Exception, e:
                    self.warning("Failed to read from source file: %s",
                                 log.getExceptionMessage(e))
                    d.errback(e)
        self._pending = []
        # then we can safely close files
        if closeSource:
            self._closeSourceFile()
        if closeTempWrite:
            self._closeWriteTempFile()

    def _onCopyFinished(self):
        # Called when the copy thread really stopped to read/write
        self.debug("Finished caching '%s' [fd %d]",
                   self.sourcePath, self._sourceFile.fileno())
        self.plug.stats.onCopyFinished(self.size)
        # Set the copy as finished to prevent the temporary file
        # to be deleted when closed
        self._copied = None
        # Closing source and write files
        self._closeSourceFile()
        self._closeWriteTempFile()
        # Setting the modification time on the temporary file
        try:
            mtime = self.mtime
            atime = int(time.time())
            self.log("Setting temporary file modification time to %d", mtime)
            # FIXME: Should use futimes, but it's not wrapped by python
            os.utime(self.tempPath, (atime, mtime))
        except OSError, e:
            if e.errno == errno.ENOENT:
                # The file may have been deleted by another process
                self._releaseCacheSpace()
            else:
                self.warning("Failed to update modification time of temporary "
                             "file: %s", log.getExceptionMessage(e))
            self._cancelSession()
        try:
            self.log("Renaming temporary file to '%s'", self.cachePath)
            os.rename(self.tempPath, self.cachePath)
        except OSError, e:
            if e.errno == errno.ENOENT:
                self._releaseCacheSpace()
            else:
                self.warning("Failed to rename temporary file: %s",
                             log.getExceptionMessage(e))
            self._cancelSession()
        # Complete all pending source read operations with the temporary file.
        for position, size, d in self._pending:
            try:
                self._rTempFile.seek(position)
                data = self._rTempFile.read(size)
                d.callback(data)
            except Exception, e:
                self.warning("Failed to read from temporary file: %s",
                             log.getExceptionMessage(e))
                d.errback(e)
        self._pending = []
        if self._refCount == 0:
            # We were waiting for the file to be copied to close it.
            self.close()

    def _removeTempFile(self):
        try:
            os.remove(self.tempPath)
            self.log("Deleted temporary file '%s'", self.tempPath)
            # Inform the plug that cache space has been released
            self._releaseCacheSpace()
        except OSError, e:
            if e.errno == errno.ENOENT:
                if self._wTempFile is not None:
                    # Already deleted but inform the plug anyway
                    self._releaseCacheSpace()
            else:
                self.warning("Error deleting temporary file: %s",
                             log.getExceptionMessage(e))

    def _closeSourceFile(self):
        if self._sourceFile is not None:
            self.log("Closing source file [fd %d]", self._sourceFile.fileno())
            try:
                try:
                    self._sourceFile.close()
                finally:
                    self._sourceFile = None
            except IOError, e:
                self.warning("Failed to close source file: %s",
                             log.getExceptionMessage(e))

    def _closeReadTempFile(self):
        if self._rTempFile is not None:
            self.log("Closing temporary file for reading [fd %d]",
                     self._rTempFile.fileno())
            try:
                try:
                    self._rTempFile.close()
                finally:
                    self._rTempFile = None
            except IOError, e:
                self.warning("Failed to close temporary file for reading: %s",
                             log.getExceptionMessage(e))

    def _closeWriteTempFile(self):
        if self._wTempFile is not None:
            # If the copy is not finished, remove the temporary file
            if not self._canceled and self._copied is not None:
                self._removeTempFile()
            self.log("Closing temporary file for writing [fd %d]",
                     self._wTempFile.fileno())
            try:
                try:
                    self._wTempFile.close()
                finally:
                    self._wTempFile = None
            except Exception, e:
                self.warning("Failed to close temporary file for writing: %s",
                             log.getExceptionMessage(e))


class TempFileDelegate(log.Loggable):

    logCategory = LOG_CATEGORY

    def __init__(self, plug, session):
        self.logName = plug.getLogName(session.sourcePath)
        self.mtime = session.mtime
        self.size = session.size
        self._session = session
        self._reading = False
        self._position = 0
        session.incRef()

    def tell(self):
        return self._position

    def seek(self, offset):
        self._position = offset

    def read(self, size, stats):
        assert not self._reading, "Simultaneous read not supported"
        d = self._session.read(self._position, size, stats)
        if isinstance(d, defer.Deferred):
            self._reading = True
            return d.addCallback(self._cbGotData)
        self._position += len(d)
        return d

    def close(self):
        if self._session is not None:
            self._session.decRef()
            self._session = None


    ## Private Methods ##

    def _cbGotData(self, data):
        self._reading = False
        self._position += len(data)
        return data


class DirectFileDelegate(log.Loggable):

    logCategory = LOG_CATEGORY

    # Default values
    _file = None

    def __init__(self, plug, path, file, info):
        self.logName = plug.getLogName(path, file.fileno())
        self._file = file
        # The size and modification time is not supposed to change over time
        self.mtime = info[stat.ST_MTIME]
        self.size = info[stat.ST_SIZE]

    def tell(self):
        try:
            return self._file.tell()
        except IOError, e:
            cls = _errorLookup.get(e.errno, FileError)
            raise cls("Failed to tell position in file: %s" % str(e))

    def seek(self, offset):
        try:
            self._file.seek(offset, SEEK_SET)
        except IOError, e:
            cls = _errorLookup.get(e.errno, FileError)
            raise cls("Failed to seek in cached file: %s" % str(e))

    def read(self, size):
        try:
            return self._file.read(size)
        except IOError, e:
            cls = _errorLookup.get(e.errno, FileError)
            raise cls("Failed to read data from file: %s" % str(e))

    def close(self):
        if self._file is not None:
            try:
                try:
                    self._file.close()
                finally:
                    self._file = None
            except IOError, e:
                cls = _errorLookup.get(e.errno, FileError)
                raise cls("Failed to close file: %s" % str(e))


class CachedFileDelegate(DirectFileDelegate):

    def read(self, size, stats):
        data = DirectFileDelegate.read(self, size)
        stats.onBytesRead(0, len(data), 0)
        return data

    def close(self):
        if self._file is not None:
            self.log("Closing cached file [fd %d]", self._file.fileno())
            DirectFileDelegate.close(self)


class CachedFile(fileprovider.File, log.Loggable):

    logCategory = LOG_CATEGORY

    # Overriding parent class properties to become attribute
    mimeType = None

    # Default values
    _delegate = None

    def __init__(self, plug, path, mimeType):
        self.logName = plug.getLogName(path)
        self.plug = plug
        self._path = path
        self.mimeType = mimeType
        self.stats = cachestats.RequestStatistics(plug.stats)
        self._delegate = self._selectDelegate()

    def __str__(self):
        return "<CachedFile '%s'>" % self._path

    def getmtime(self):
        if self._delegate is None:
            raise FileClosedError("File closed")
        return self._delegate.mtime

    def getsize(self):
        if self._delegate is None:
            raise FileClosedError("File closed")
        return self._delegate.size

    def tell(self):
        if self._delegate is None:
            raise FileClosedError("File closed")
        return self._delegate.tell()

    def seek(self, offset):
        if self._delegate is None:
            raise FileClosedError("File closed")
        return self._delegate.seek(offset)

    def read(self, size):
        if self._delegate is None:
            raise FileClosedError("File closed")
        try:
            d = self._delegate.read(size, self.stats)
            if isinstance(d, defer.Deferred):
                return d
            return defer.succeed(d)
        except IOError, e:
            cls = _errorLookup.get(e.errno, FileError)
            return defer.fail(cls("Failed to read cached data: %s", str(e)))
        except:
            return defer.fail()

    def close(self):
        if self._delegate:
            self.stats.onClosed()
            self._delegate.close()
            self._delegate = None

    def __del__(self):
        self.close()

    def getLogFields(self):
        return self.stats.getLogFields()


    ## Private Methods ##

    def _open(self, path):
        """
        @rtype: (file, statinfo)
        """
        try:
            file = open(path, 'rb')
            fd = file.fileno()
        except IOError, e:
            cls = _errorLookup.get(e.errno, FileError)
            raise cls("Failed to open file '%s': %s" % (path, str(e)))
        try:
            info = os.fstat(fd)
        except OSError, e:
            cls = _errorLookup.get(e.errno, FileError)
            raise cls("Failed to stat file '%s': %s" % (path, str(e)))
        return file, info

    def _closeSourceFile(self, sourceFile):
        self.log("Closing source file [fd %d]", sourceFile.fileno())
        try:
            sourceFile.close()
        except Exception, e:
            self.warning("Failed to close source file: %s",
                         log.getExceptionMessage(e))

    def _selectDelegate(self):
        sourcePath = self._path
        cachedPath = self.plug.getCachePath(sourcePath)
        # Opening source file
        try:
            sourceFile, sourceInfo = self._open(sourcePath)
            self.log("Opened source file [fd %d]", sourceFile.fileno())
        except NotFoundError:
            self.debug("Source file not found")
            self.plug.outdateCopySession(sourcePath)
            self._removeCachedFile(cachedPath)
            raise
        # Update the log name
        self.logName = self.plug.getLogName(self._path, sourceFile.fileno())
        # Opening cached file
        try:
            cachedFile, cachedInfo = self._open(cachedPath)
            self.log("Opened cached file [fd %d]", cachedFile.fileno())
        except NotFoundError:
            self.debug("Did not found cached file '%s'", cachedPath)
            return self._tryTempFile(sourcePath, sourceFile, sourceInfo)
        except FileError, e:
            self.debug("Fail to open cached file: %s", str(e))
            self._removeCachedFile(cachedPath)
            return self._tryTempFile(sourcePath, sourceFile, sourceInfo)
        # Found a cached file, now check the modification time
        self.debug("Found cached file '%s'", cachedPath)
        sourceTime = sourceInfo[stat.ST_MTIME]
        cacheTime = cachedInfo[stat.ST_MTIME]
        if sourceTime != cacheTime:
            # Source file changed, remove file and start caching again
            self.debug("Cached file out-of-date (%d != %d)",
                       sourceTime, cacheTime)
            self.stats.onCacheOutdated()
            self.plug.outdateCopySession(sourcePath)
            self._removeCachedFile(cachedPath)
            return self._cacheFile(sourcePath, sourceFile, sourceInfo)
        self._closeSourceFile(sourceFile)
        # We have a valid cached file, just delegate to it.
        self.debug("Serving cached file '%s'", cachedPath)
        delegate = CachedFileDelegate(self.plug, cachedPath,
                                      cachedFile, cachedInfo)
        self.stats.onStarted(delegate.size, cachestats.CACHE_HIT)
        return delegate

    def _removeCachedFile(self, cachePath):
        try:
            os.remove(cachePath)
            self.debug("Deleted cached file '%s'", cachePath)
        except OSError, e:
            if e.errno != errno.ENOENT:
                self.warning("Error deleting cached file: %s", str(e))

    def _tryTempFile(self, sourcePath, sourceFile, sourceInfo):
        session = self.plug.getCopySession(sourcePath)
        if session is None:
            self.debug("No copy sessions found")
            return self._cacheFile(sourcePath, sourceFile, sourceInfo)
        self.debug("Copy session found")
        if sourceInfo[stat.ST_MTIME] != session.mtime:
            self.debug("Copy session out-of-date (%d != %d)",
                       sourceInfo[stat.ST_MTIME], session.mtime)
            self.stats.onCacheOutdated()
            session.outdate()
            return self._cacheFile(sourcePath, sourceFile, sourceInfo)
        self._closeSourceFile(sourceFile)
        # We have a valid session, just delegate to it.
        self.debug("Serving temporary file '%s'", session.tempPath)
        delegate = TempFileDelegate(self.plug, session)
        self.stats.onStarted(delegate.size, cachestats.TEMP_HIT)
        return delegate

    def _cacheFile(self, sourcePath, sourceFile, sourceInfo):
        session = self.plug.createCopySession(sourcePath, sourceFile,
                                              sourceInfo)
        self.debug("Serving temporary file '%s'", session.tempPath)
        delegate = TempFileDelegate(self.plug, session)
        self.stats.onStarted(delegate.size, cachestats.CACHE_MISS)
        return delegate
