# -*- Mode: Python; test-case-name: flumotion.test.test_http -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# Flumotion - a streaming media server
# Copyright (C) 2004,2005,2006,2007 Fluendo, S.L. (www.fluendo.com).
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

import os
import random
import shutil
import stat
import tempfile
import time

from twisted.internet import defer, threads, reactor
from twisted.trial import unittest

import twisted.copyright
if twisted.copyright.version == 'SVN-Trunk':
    SKIP_MSG = "Twisted 2.0.1 thread pool is broken for tests"
else:
    SKIP_MSG = None

from flumotion.common import testsuite, errors
from flumotion.component.misc.httpserver import cachemanager, fileprovider

CACHE_SIZE = 1 * 1024 * 1024
MAX_CLEANUPS = 64
MAX_PAGE_SIZE = 32 * 1024


class DummyStats:

    def __init__(self):
        self.oncleanup = 0
        self.onestimate = 0

    def info():
        pass

    def onEstimateCacheUsage(self, usage, size):
        self.onestimate += 1
        self.usage = usage
        self.size = size

    def onCleanup(self):
        self.oncleanup += 1


class TestCacheManager(testsuite.TestCase):

    skip = SKIP_MSG

    def setUp(self):
        from twisted.python import threadpool
        reactor.threadpool = threadpool.ThreadPool(0, 10)
        reactor.threadpool.start()

        self.path = tempfile.mkdtemp(suffix=".flumotion.test")
        self.stats = DummyStats()
        self._file = None

    def tearDown(self):
        shutil.rmtree(self.path, ignore_errors=True)

        reactor.threadpool.stop()
        reactor.threadpool = None

    def completeAndClose(self, t, m):
        try:
            t.complete()
        except:
            # we don't care whatever this might raises, we just want
            # to close the temp file. There are other tests to check
            # if complete() raises something unexpected.
            pass

        try:
            t.close()
        except:
            print "Got a close exception"
            raise

    def checkUsage(self, usage, m, size):
        self.failIf(abs(m._cacheUsage - size) > MAX_PAGE_SIZE)

    def _releaseCacheSpace(self, tag, m):
        self.checkUsage(None, m, 100 * 1024)
        m.releaseCacheSpace(tag)
        self.checkUsage(None, m, 0)

    def testLowLevel(self):

        def _makeTemp(tag, size, m, name):
            t = cachemanager.TempFile(m, name, tag, size)
            return t

        m = cachemanager.CacheManager(self.stats, self.path,
                                      CACHE_SIZE, True, 0.5, 0.3)

        # getIdentifier/Path
        self.assertEquals(type(m.getIdentifier("path")), type(""))
        self.assertEquals(m.getIdentifier("path"), m.getIdentifier("path"))
        self.failIfEquals(m.getIdentifier("path"), m.getIdentifier("path2"))

        self.assertEquals(type(m.getCachePath("path")), type(""))
        self.assertEquals(type(m.getTempPath("path")), type(""))

        # updateCacheUsage ~= 0
        d = m.updateCacheUsage()
        d.addCallback(self.checkUsage, m, 0)

        # allocate&release
        d.addCallback(lambda _: m.allocateCacheSpace(100 * 1024))
        d.addCallback(self._releaseCacheSpace, m)

        # updateCacheUsage ~= 0
        d.addCallback(lambda _: m.updateCacheUsage())
        d.addCallback(self.checkUsage, m, 0)

        # allocate > CACHE_SIZE
        d.addCallback(lambda _: m.allocateCacheSpace(CACHE_SIZE * 2))
        d.addCallback(lambda c: self.failUnless(c is None))
        d.addErrback(self.fail)

        # updateCacheUsage ~= 0
        d.addCallback(lambda _: m.updateCacheUsage())
        d.addCallback(self.checkUsage, m, 0)

        # close incomplete TempFile
        d.addCallback(lambda _: m.allocateCacheSpace(100 * 1024))
        d.addCallback(_makeTemp, 100 * 1024, m, "test")
        d.addCallback(lambda t: t.close())

        # updateCacheUsage ~= 0
        d.addCallback(lambda _: m.updateCacheUsage())
        d.addCallback(self.checkUsage, m, 0)

        # close complete TempFile
        d.addCallback(lambda _: m.allocateCacheSpace(100 * 1024))
        d.addCallback(_makeTemp, 100 * 1024, m, "test1")
        d.addCallback(self.completeAndClose, m)

        # updateCacheUsage ~= 100k
        d.addCallback(lambda _: m.updateCacheUsage())
        d.addCallback(self.checkUsage, m, 100 * 1024)

        return d

    def checkCacheHit(self, m, name):
        d = m.openCacheFile(name)
        d.addCallback(lambda f: f.close())
        d.addErrback(self.fail)
        return d

    def checkCacheMiss(self, m, name):
        d = m.openCacheFile(name)
        d.addCallback(lambda c: self.failUnless(c is None))
        return d

    def testHitMiss(self):
        m = cachemanager.CacheManager(self.stats, self.path,
                                      CACHE_SIZE, True, 0.5, 0.2)

        # updateCacheUsage ~= 0
        d = m.updateCacheUsage()
        d.addCallback(self.checkUsage, m, 0)

        d.addCallback(lambda _: self.checkCacheMiss(m, "test3"))
        d.addCallback(lambda _: self.checkCacheMiss(m, "test4"))

        d.addCallback(lambda _: m.newTempFile("test3",
                                              CACHE_SIZE - MAX_PAGE_SIZE))

        d.addCallback(lambda f: setattr(self, "_file", f))
        d.addCallback(lambda _: self.checkCacheMiss(m, "test3"))

        d.addCallback(lambda _: self._file)
        d.addCallback(self.completeAndClose, m)
        d.addErrback(self.fail)

        d.addCallback(lambda _: self.checkCacheHit(m, "test3"))
        d.addCallback(lambda _: self.checkCacheMiss(m, "test4"))

        d.addCallback(lambda _: m.newTempFile("test4",
                                              CACHE_SIZE - MAX_PAGE_SIZE))
        d.addCallback(self.completeAndClose, m)

        # The cache cleaning is done in a seperate thread...
        d.addCallback(lambda _: time.sleep(1))
        d.addCallback(lambda _: self.checkCacheMiss(m, "test3"))

        return d

    def fillTestCache(self, manager, size):
        d = defer.Deferred()
        i = 0
        while (size > 0):
            i += 1
            filesize = random.randint(MAX_PAGE_SIZE, MAX_PAGE_SIZE * 3)
            size -= filesize
            d.addCallback(lambda _: manager.newTempFile(str(i), filesize))
            d.addCallback(self.completeAndClose, manager)
        d.callback(None)
        return d

    def testCacheCleanUp(self):
        m = cachemanager.CacheManager(self.stats, self.path,
                                      CACHE_SIZE, True, 0.4, 0.2)

        self.failIf(m.stats.oncleanup != 0)

        d = self.fillTestCache(m, CACHE_SIZE * 4)

        # The cache cleaning is done in a seperate thread...
        d.addCallback(lambda _: time.sleep(1))
        d.addCallback(lambda _: m.updateCacheUsage())
        d.addCallback(lambda u: self.failIf(u > CACHE_SIZE / 2))
        d.addCallback(lambda _: self.failIf(m.stats.oncleanup < 5))

        return d

    def testConflict(self):

        def writeContent(f):
            f.write("content\n")
            return f

        m = cachemanager.CacheManager(self.stats, self.path,
                                      CACHE_SIZE, True, 0.4, 0.2)
        # create a cache for "file' with some content
        d = m.newTempFile("file", 1024)
        d.addCallback(writeContent)
        d.addCallback(lambda f: setattr(self, "_file", f))

        # create a second cache for "file'
        d.addCallback(lambda _: m.newTempFile("file", 1024))
        d.addCallback(writeContent)
        # and complete it now
        d.addCallback(self.completeAndClose, m)

        # then, complete first cache (conflict)
        d.addCallback(lambda _: self._file)
        d.addCallback(self.completeAndClose, m)
        d.addCallback(lambda f: setattr(self, "_file", None))

        # check that we get back our content after conflict
        d.addCallback(lambda _: m.openCacheFile("file"))
        d.addCallback(lambda f: setattr(self, "_file", f))
        d.addCallback(lambda _: self._file.readline())
        d.addCallback(lambda s: self.assertEqual(s, "content\n"))
        d.addCallback(lambda _: self._file.close())

        return d

    def testMTime(self):
        m = cachemanager.CacheManager(self.stats, self.path,
                                      CACHE_SIZE, True, 0.4, 0.2)
        d = m.newTempFile("test_mtime", 1024, 1256040206)
        d.addCallback(self.completeAndClose, m)

        d.addCallback(lambda _: m.openCacheFile("test_mtime"))
        d.addCallback(lambda f: f.stat[stat.ST_MTIME])
        d.addCallback(lambda t: self.assertEqual(t, 1256040206))
        return d

    def testConflictMTime(self):

        def writeContent(f, content):
            f.write(content)
            return f

        m = cachemanager.CacheManager(self.stats, self.path,
                                      CACHE_SIZE, True, 0.4, 0.2)
        # create a cache for "file' with some old content
        d = m.newTempFile("file", 1024, 1256040206)
        d.addCallback(writeContent, "old\n")
        d.addCallback(lambda f: setattr(self, "_file", f))

        # create a second cache for "file' with newer content
        d.addCallback(lambda _: m.newTempFile("file", 1024, 1256040207))
        d.addCallback(writeContent, "new\n")
        # and complete it now
        d.addCallback(self.completeAndClose, m)

        # then, complete first cache (conflict)
        d.addCallback(lambda _: self._file)
        d.addCallback(self.completeAndClose, m)
        d.addCallback(lambda f: setattr(self, "_file", None))

        # check that we get back our "new" content after conflict
        d.addCallback(lambda _: m.openCacheFile("file"))
        d.addCallback(lambda f: setattr(self, "_file", f))
        d.addCallback(lambda _: self._file.readline())
        d.addCallback(lambda s: self.assertEqual(s, "new\n"))
        d.addCallback(lambda _: self._file.close())

        return d

    def testFileSizeLimit(self):
        m = cachemanager.CacheManager(self.stats, self.path,
                                      CACHE_SIZE, True, 0.4, 0.2)

        d = m.newTempFile("test_limit", 5)
        d.addCallback(lambda f: f.write("123456"))
        d.addCallback(self.fail)
        d.addErrback(lambda f: f.trap(IOError))
        d.addCallback(lambda _: None)

        return d

    def checkCompleted(self, f):
        f.write("12345")
        f.complete(True)
        f.close()

    def checkIncomplete(self, f):
        self.failUnlessRaises(IOError, f.complete, True)
        f.close()

    def testCheckCompleted(self):
        m = cachemanager.CacheManager(self.stats, self.path,
                                      CACHE_SIZE, True, 0.4, 0.2)

        d = m.newTempFile("test_completed", 5)
        d.addCallback(self.checkCompleted)

        d.addCallback(lambda _: m.newTempFile("test_incomplete", 5))
        d.addCallback(self.checkIncomplete)

        return d

    def fillTestCache2(self, manager):
        i = 0
        while (manager.stats.oncleanup < MAX_CLEANUPS):
            i += 1
            filesize = 4096 * random.randint(1, 30)
            d = manager.newTempFile(str(i), filesize)
            d.addCallback(self.completeAndClose, manager)
            d.addErrback(lambda f: f.trap(fileprovider.FileError))

    def testNoCleanUp(self):
        m = cachemanager.CacheManager(self.stats, self.path,
                                      CACHE_SIZE * 1.1, False, 1.0, 0.2)

        d = m.newTempFile("FAT FILE", CACHE_SIZE / 2)
        d.addCallback(self.completeAndClose, m)

        d.addCallback(lambda _: m.newTempFile("FAT FILE TWIN", CACHE_SIZE / 2))
        d.addCallback(self.completeAndClose, m)

        d.addCallback(lambda _: m.newTempFile("FAT FILE BRO'", CACHE_SIZE / 2))
        d.addCallback(lambda t: self.failUnless(t is None))

        d.addCallback(lambda _: self.failIf(m.stats.oncleanup != 0))

        return d

    def testUnlink(self):
        m = cachemanager.CacheManager(self.stats, self.path,
                                      CACHE_SIZE, False, 0.5, 0.2)

        name = "unlink-me"
        path = m.getCachePath(name)

        d = m.newTempFile(name, 1024, 1256040206)
        # TODO: d.addCallback(lambda f: f.complete) is not enough to
        # pass the test, weirdo...
        d.addCallback(self.completeAndClose, m)

       # check that unlink actually works
        d.addCallback(lambda _: m.openCacheFile(name))
        d.addErrback(lambda _: self.fail)
        d.addCallback(lambda c: c.unlink())

        d.addCallback(lambda _: os.stat(path))
        d.addCallback(self.fail)
        d.addErrback(lambda f: f.trap(OSError))

        # now check that we keep more recent version
        d.addCallback(lambda _: m.newTempFile(name, 1024, 1256040206))
        d.addCallback(self.completeAndClose, m)

        d.addCallback(lambda _: m.openCacheFile(name))
        d.addCallback(lambda f: setattr(self, "_file", f))
        # cache a more recent version
        d.addCallback(lambda _: m.newTempFile(name, 1024, 1256040208))
        d.addCallback(self.completeAndClose, m)
        # try remove an outdated CachedFile
        d.addCallback(lambda _: self._file.unlink())

        # check file is still there
        d.addCallback(lambda _: os.stat(path))

        return d

    def testMultiThread(self):
        # FIXME: this test can deadlock....
        return

        m = cachemanager.CacheManager(self.stats, self.path,
                                      CACHE_SIZE, True, 0.4, 0.2)
        dl = []
        d = threads.deferToThread(self.fillTestCache2, m)
        dl.append(d)
        threads.deferToThread(self.fillTestCache2, m)
        dl.append(d)
        threads.deferToThread(self.fillTestCache2, m)
        dl.append(d)

        return defer.DeferredList(dl)
