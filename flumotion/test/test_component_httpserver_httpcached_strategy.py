    # -*- Mode: Python; test-case-name: flumotion.test.test_common -*-
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

import os
import random
import StringIO
import time
import stat

import twisted
from twisted.internet import reactor, defer

from flumotion.common import python
from flumotion.common.testsuite import TestCase

from flumotion.component.misc.httpserver import fileprovider
from flumotion.component.misc.httpserver.httpcached import common
from flumotion.component.misc.httpserver.httpcached import http_utils
from flumotion.component.misc.httpserver.httpcached import strategy_base
from flumotion.component.misc.httpserver.httpcached import strategy_basic

BLOCK_SIZE = 64*1024
SUB_BLOCK_SIZE = BLOCK_SIZE // 3 + BLOCK_SIZE % 3
EXTRA_DATA = BLOCK_SIZE/2
DEFAULT_TTL = 5*60


class TestBasicCachingStrategy(TestCase):

    def setUp(self):
        self.cachemgr = None
        self.reqmgr = None
        self.stgy = None
        self.sessions = {}
        self.sources = {}

    def tearDown(self):
        # Just for errors not being cluttered by unclean reactor messages
        for source in self.sources.values():
            source.close()
        if self.cachemgr:
            self.cachemgr.reset()
        if self.reqmgr:
            self.reqmgr.reset()
        if self.stgy:
            return self.stgy.cleanup()

    def testNotFound(self):
        d = defer.Deferred()

        d.addCallback(self._setup, [], [])

        # The file is not cached neither exists as a resource
        # It should fail with a NotFoundError

        d.addCallback(self._checkSessions, 0)
        d.addCallback(self._getSource, "http://www.flumotion.net/dummy")
        d.addCallbacks(self._fail, self._checkError,
                       callbackArgs=("Success not expected", ),
                       errbackArgs=(fileprovider.NotFoundError, ))
        d.addCallback(self._checkSessions, 0)
        d.addCallback(self._checkFileCount, 0)
        d.addCallback(self._checkReqCount, 1)
        d.addCallback(self._checkReqsCode, 404)
        d.addCallback(self._checkReqsSize, 0)

        d.callback(None)
        return d

    def testCachedAndUpToDate(self):
        data = os.urandom(BLOCK_SIZE*4 + EXTRA_DATA)
        mtime = time.time()

        d = defer.Deferred()

        d.addCallback(self._setup,
                      [FileDef("/dummy", data, mtime)],
                      [ResDef("/dummy", data, mtime)], ttl=2)

        # The file is cached and the resource has not been modified.
        # But It should do a conditional request to check if the
        # file is outdated, then it should just get the file from cache.

        d.addCallback(self._checkSessions, 0)
        d.addCallback(self._getSource, "http://www.flumotion.net/dummy")
        d.addCallback(self._gotSource, "source")
        d.addCallback(self._isInstance, strategy_base.CachedSource)
        d.addCallback(self._checkSessions, 0)
        d.addCallback(self._readAllData)
        d.addCallback(self._checkData, data)
        d.addCallback(self._closeSource, "source")
        d.addCallback(self._checkFileCount, 1)
        d.addCallback(self._checkFilesClosed)
        d.addCallback(self._checkReqCount, 1) # Only the check request
        d.addCallback(self._checkReqsCode, common.STREAM_NOT_MODIFIED)
        d.addCallback(self._checkReqsSize, 0)

        # Reseting
        d.addCallback(self._reset)

        # The second time it shouldn't do a request to check for expiration

        d.addCallback(self._checkSessions, 0)
        d.addCallback(self._getSource, "http://www.flumotion.net/dummy")
        d.addCallback(self._gotSource, "source2")
        d.addCallback(self._isInstance, strategy_base.CachedSource)
        d.addCallback(self._checkSessions, 0)
        d.addCallback(self._readAllData)
        d.addCallback(self._checkData, data)
        d.addCallback(self._closeSource, "source2")
        d.addCallback(self._checkFileCount, 1)
        d.addCallback(self._checkFilesClosed)
        d.addCallback(self._checkReqCount, 0)

        # Reseting
        d.addCallback(self._reset)

        # Waiting for the TTL to expire
        d.addCallback(wait, 2)

        # Now it should check again if outdated

        d.addCallback(self._checkSessions, 0)
        d.addCallback(self._getSource, "http://www.flumotion.net/dummy")
        d.addCallback(self._gotSource, "source")
        d.addCallback(self._isInstance, strategy_base.CachedSource)
        d.addCallback(self._checkSessions, 0)
        d.addCallback(self._readAllData)
        d.addCallback(self._checkData, data)
        d.addCallback(self._closeSource, "source")
        d.addCallback(self._checkFileCount, 1)
        d.addCallback(self._checkFilesClosed)
        d.addCallback(self._checkReqCount, 1) # Only the check request
        d.addCallback(self._checkReqsCode, common.STREAM_NOT_MODIFIED)
        d.addCallback(self._checkReqsSize, 0)

        d.callback(None)
        return d

    def testNotCachedSimple(self):
        data = os.urandom(BLOCK_SIZE*4 + EXTRA_DATA)
        mtime = time.time()

        d = defer.Deferred()

        d.addCallback(self._setup, [], [ResDef("/dummy", data, mtime)])

        # The file is not cached and the resource exists.
        # We are waiting for the file to be cached before reading data.
        # It should just download the file
        # and then serve it from the temporary file.

        d.addCallback(self._checkSessions, 0)
        d.addCallback(self._getSource, "http://www.flumotion.net/dummy")
        d.addCallback(self._gotSource, "source", "session")
        d.addCallback(self._isInstance, strategy_base.RemoteSource)
        d.addCallback(self._checkSessions, 1)
        # Wait complete caching
        d.addCallback(self._waitFinished, "session")
        d.addCallback(self._checkSessions, 0)
        d.addCallback(self._readAllData)
        d.addCallback(self._checkData, data)
        d.addCallback(self._closeSource, "source")
        d.addCallback(self._checkFileCount, 1)
        d.addCallback(self._checkFilesClosed)
        d.addCallback(self._checkFilesCompleted)
        d.addCallback(self._checkReqCount, 1)
        d.addCallback(self._checkReqsCode, None) # No error
        d.addCallback(self._checkReqsSize, len(data))

        # Reseting
        d.addCallback(self._reset)

        # Now the file is cached, it should just serve it from cache.

        d.addCallback(self._checkSessions, 0)
        d.addCallback(self._getSource, "http://www.flumotion.net/dummy")
        d.addCallback(self._gotSource, "source2")
        d.addCallback(self._isInstance, strategy_base.CachedSource)
        d.addCallback(self._checkSessions, 0)
        d.addCallback(self._readAllData)
        d.addCallback(self._checkData, data)
        d.addCallback(self._closeSource, "source2")
        d.addCallback(self._checkFileCount, 1)
        d.addCallback(self._checkFilesClosed)
        d.addCallback(self._checkReqCount, 0)

        d.callback(None)
        return d

    def testNotCachedPipelining(self):
        data = os.urandom(BLOCK_SIZE*4 + EXTRA_DATA)
        mtime = time.time()

        d = defer.Deferred()

        d.addCallback(self._setup, [], [ResDef("/dummy", data, mtime)])

        # The file is not cached and the resource exists.
        # We artificially make the session transfer slow,
        # so it should serve the data using pipelining.

        # Make the transfer slow for the caching session
        d.addCallback(self._set, "reqmgr", "trans_delay", 0.2)

        d.addCallback(self._checkSessions, 0)
        d.addCallback(self._getSource, "http://www.flumotion.net/dummy")
        d.addCallback(self._gotSource, "source", "session")
        d.addCallback(self._isInstance, strategy_base.RemoteSource)
        d.addCallback(self._checkSessions, 1)
        # Restoring normal speed for pipelining
        d.addCallback(self._set, "reqmgr", "trans_delay", 0.01)
        d.addCallback(self._readAllData)
        d.addCallback(self._checkData, data)
        d.addCallback(self._closeSource, "source")
        d.addCallback(self._checkSessions, 1)
        # Wait complete caching (but data has already been read)
        d.addCallback(self._waitFinished, "session")
        d.addCallback(self._checkSessions, 0)
        d.addCallback(self._checkFileCount, 1)
        d.addCallback(self._checkFilesClosed)
        d.addCallback(self._checkFilesCompleted)

        # Requests for complete blocks
        fullBlocks = len(data) // BLOCK_SIZE
        # Request for last block
        partialBlocks = int(len(data) % BLOCK_SIZE > 0)
        expReqCount = (fullBlocks + partialBlocks
                       + 1) # request for caching
        expReqSizes = [len(data)] + [BLOCK_SIZE]*fullBlocks
        expReqSizes += partialBlocks and [len(data) % BLOCK_SIZE] or []
        expReqCodes = [None]*(fullBlocks + partialBlocks + 1)

        d.addCallback(self._checkReqCount, expReqCount)
        d.addCallback(self._checkReqsSize, expReqSizes)
        d.addCallback(self._checkReqsCode, expReqCodes)

        # Reseting
        d.addCallback(self._reset)

        # Now the file is cached, it should just serve it from cache.

        d.addCallback(self._checkSessions, 0)
        d.addCallback(self._getSource, "http://www.flumotion.net/dummy")
        d.addCallback(self._gotSource, "source2")
        d.addCallback(self._isInstance, strategy_base.CachedSource)
        d.addCallback(self._checkSessions, 0)
        d.addCallback(self._readAllData)
        d.addCallback(self._checkData, data)
        d.addCallback(self._closeSource, "source2")
        d.addCallback(self._checkFileCount, 1)
        d.addCallback(self._checkFilesClosed)
        d.addCallback(self._checkReqCount, 0)

        d.callback(None)
        return d

    def testNotCachedServerErrors(self):
        data = os.urandom(BLOCK_SIZE*4 + EXTRA_DATA)
        mtime = time.time()

        d = defer.Deferred()

        d.addCallback(self._setup, [], [ResDef("/dummy", data, mtime)])

        # The file is not cached and resource exists,
        # but we simulate the server errors.

        # Simulating unavailable server
        d.addCallback(self._set, "reqmgr", "available", False)
        d.addCallback(self._set, "reqmgr", "connTimeout", None)

        d.addCallback(self._checkSessions, 0)
        d.addCallback(self._getSource, "http://www.flumotion.net/dummy")
        d.addCallbacks(self._fail, self._checkError,
                       callbackArgs=("Success not expected", ),
                       errbackArgs=(fileprovider.FileError, ))
        d.addCallback(self._checkSessions, 0)
        d.addCallback(self._checkFileCount, 0)
        d.addCallback(self._checkReqCount, 1)
        d.addCallback(self._checkReqsCode, common.SERVER_UNAVAILABLE)

        # Reseting
        d.addCallback(self._reset)

        # Simulating connection timeout
        d.addCallback(self._set, "reqmgr", "available", True)
        d.addCallback(self._set, "reqmgr", "connTimeout", 0.5)

        d.addCallback(self._checkSessions, 0)
        d.addCallback(self._getSource, "http://www.flumotion.net/dummy")
        d.addCallbacks(self._fail, self._checkError,
                       callbackArgs=("Success not expected", ),
                       errbackArgs=(fileprovider.FileError, ))
        d.addCallback(self._checkSessions, 0)
        d.addCallback(self._checkFileCount, 0)
        d.addCallback(self._checkReqCount, 1)
        d.addCallback(self._checkReqsSize, 0)
        d.addCallback(self._checkReqsCode, common.SERVER_UNAVAILABLE)

        d.callback(None)
        return d

    def testCachedServerErrors(self):
        data = os.urandom(BLOCK_SIZE*4 + EXTRA_DATA)
        mtime = time.time()

        d = defer.Deferred()

        d.addCallback(self._setup,
                      [FileDef("/dummy", data, mtime)],
                      [ResDef("/dummy", data, mtime)])

        # The file is cached and resource exists,
        # but we simulate server errors.
        # It will try to check if the file is outdated and it will fail,
        # but it should serve from cache anyway.

        # Simulating unavailable server
        d.addCallback(self._set, "reqmgr", "available", False)
        d.addCallback(self._set, "reqmgr", "connTimeout", None)

        d.addCallback(self._checkSessions, 0)
        d.addCallback(self._getSource, "http://www.flumotion.net/dummy")
        d.addCallback(self._gotSource, "source")
        d.addCallback(self._isInstance, strategy_base.CachedSource)
        d.addCallback(self._checkSessions, 0)
        d.addCallback(self._readAllData)
        d.addCallback(self._checkData, data)
        d.addCallback(self._closeSource, "source")
        d.addCallback(self._checkFileCount, 1)
        d.addCallback(self._checkFilesClosed)
        d.addCallback(self._checkReqCount, 1)
        d.addCallback(self._checkReqsSize, 0)
        d.addCallback(self._checkReqsCode, common.SERVER_UNAVAILABLE)

        # Reseting
        d.addCallback(self._reset)

        # But then a small TTL should have been added to prevent
        # expiration check for each request when the server in no available.
        # So the next request will serve from cache without error.

        d.addCallback(self._checkSessions, 0)
        d.addCallback(self._getSource, "http://www.flumotion.net/dummy")
        d.addCallback(self._gotSource, "source")
        d.addCallback(self._isInstance, strategy_base.CachedSource)
        d.addCallback(self._checkSessions, 0)
        d.addCallback(self._readAllData)
        d.addCallback(self._checkData, data)
        d.addCallback(self._closeSource, "source")
        d.addCallback(self._checkFileCount, 1)
        d.addCallback(self._checkFilesClosed)
        d.addCallback(self._checkReqCount, 0)

        # Reseting
        d.addCallback(self._reset)

        # Waiting for the expiration TTL for errors
        d.addCallback(wait, strategy_basic.EXPIRE_CHECK_TTL)

        # Now it should do another expiration check
        # but serve from cache anyway too.

        # Simulating connection timeout
        d.addCallback(self._set, "reqmgr", "available", True)
        d.addCallback(self._set, "reqmgr", "connTimeout", 0.5)

        d.addCallback(self._checkSessions, 0)
        d.addCallback(self._getSource, "http://www.flumotion.net/dummy")
        d.addCallback(self._gotSource, "source")
        d.addCallback(self._isInstance, strategy_base.CachedSource)
        d.addCallback(self._checkSessions, 0)
        d.addCallback(self._readAllData)
        d.addCallback(self._checkData, data)
        d.addCallback(self._closeSource, "source")
        d.addCallback(self._checkFileCount, 1)
        d.addCallback(self._checkFilesClosed)
        d.addCallback(self._checkReqCount, 1)
        d.addCallback(self._checkReqsSize, 0)
        d.addCallback(self._checkReqsCode, common.SERVER_UNAVAILABLE)

        d.callback(None)
        return d

    def testCacheExpired(self):
        data1 = os.urandom(BLOCK_SIZE*4 + EXTRA_DATA + 1)
        mtime1 = time.time() - 200
        data2 = os.urandom(BLOCK_SIZE*4 + EXTRA_DATA + 2)
        mtime2 = time.time() - 100
        data3 = os.urandom(BLOCK_SIZE*4 + EXTRA_DATA + 3)
        mtime3 = time.time()

        cf = FileDef("/dummy", data1, mtime1)
        res = ResDef("/dummy", data2, mtime2)

        d = defer.Deferred()

        d.addCallback(self._setup, [cf], [res], ttl=2)

        # The file is cached but the resource has changed.
        # Because it's the first time the resource is requested
        # the strategy will check if it's outdated and
        # download it again.

        d.addCallback(self._checkSessions, 0)
        d.addCallback(self._getSource, "http://www.flumotion.net/dummy")
        d.addCallback(self._gotSource, "source", "session")
        d.addCallback(self._isInstance, strategy_base.RemoteSource)
        d.addCallback(self._checkSessions, 1)
        # Wait for caching being finished to prevent pipelining
        d.addCallback(self._waitFinished, "session")
        d.addCallback(self._readAllData)
        d.addCallback(self._checkData, data2)
        d.addCallback(self._closeSource, "source")
        d.addCallback(self._checkFileCount, 2) # 1 cached, then 1 temporary
        d.addCallback(self._checkFilesClosed)
        d.addCallback(self._checkReqCount, 1)
        d.addCallback(self._checkReqsSize, len(data2))
        d.addCallback(self._checkReqsCode, None)
        d.addCallback(self._checkSessions, 0)

        # Reseting
        d.addCallback(self._reset)

        # Then, even if the cached file is outdated, no request to the server
        # will be done before the TTL is reached

        d.addCallback(self._updateResource, res, data=data3, mtime=mtime3)

        d.addCallback(self._checkSessions, 0)
        d.addCallback(self._getSource, "http://www.flumotion.net/dummy")
        d.addCallback(self._gotSource, "source2")
        d.addCallback(self._isInstance, strategy_base.CachedSource)
        d.addCallback(self._checkSessions, 0)
        d.addCallback(self._readAllData)
        d.addCallback(self._checkData, data2)
        d.addCallback(self._closeSource, "source2")
        d.addCallback(self._checkFileCount, 1)
        d.addCallback(self._checkFilesClosed)
        d.addCallback(self._checkReqCount, 0)

        # Reseting
        d.addCallback(self._reset)

        # But if we wait for the expiration TTL, the resource
        # should be downloaded again.

        # Waiting for the TTL to expire
        d.addCallback(wait, 2)

        d.addCallback(self._checkSessions, 0)
        d.addCallback(self._getSource, "http://www.flumotion.net/dummy")
        d.addCallback(self._gotSource, "source3", "session3")
        d.addCallback(self._isInstance, strategy_base.RemoteSource)
        d.addCallback(self._checkSessions, 1)
        # Wait for caching being finished to prevent pipelining
        d.addCallback(self._waitFinished, "session3")
        d.addCallback(self._readAllData)
        d.addCallback(self._checkData, data3)
        d.addCallback(self._closeSource, "source3")
        d.addCallback(self._checkFileCount, 2) # 1 cached, then 1 temporary
        d.addCallback(self._checkFilesClosed)
        d.addCallback(self._checkReqCount, 1)
        d.addCallback(self._checkReqsSize, len(data3))
        d.addCallback(self._checkReqsCode, None)
        d.addCallback(self._checkSessions, 0)

        d.callback(None)
        return d

    def testErrorWhilePipelining(self):
        data = os.urandom(BLOCK_SIZE*4 + EXTRA_DATA)
        mtime = time.time()

        d = defer.Deferred()

        d.addCallback(self._setup, [], [ResDef("/dummy", data, mtime)])

        # The file is not cached and the resource exists.
        # We artificially make the session transfer slow,
        # so it should serve the data using pipelining.
        # Then we can make it fail :)

        # Another request should be started for the remaining

        # Make the transfer slow for the caching session
        d.addCallback(self._set, "reqmgr", "trans_delay", 0.2)

        d.addCallback(self._checkSessions, 0)
        d.addCallback(self._getSource, "http://www.flumotion.net/dummy")
        d.addCallback(self._gotSource, "source", "session")
        d.addCallback(self._isInstance, strategy_base.RemoteSource)
        d.addCallback(self._checkSessions, 1)

        # Restoring normal speed for pipelining,
        # and scheduling an error during the first pipelined block.
        d.addCallback(self._set, "reqmgr", "trans_delay", 0.001)
        d.addCallback(self._set, "reqmgr", "error_reset_countdown", 2)
        d.addCallback(self._set, "reqmgr", "block_error_countdown", 2)
        d.addCallback(self._set, "reqmgr", "block_error_code",
                      common.SERVER_DISCONNECTED)

        d.addCallback(self._readAllData)
        d.addCallback(self._checkData, data)
        d.addCallback(self._closeSource, "source")
        d.addCallback(self._checkSessions, 1)
        d.addCallback(self._checkFileCount, 1)
        d.addCallback(self._checkReqCount, 1 + 2 + 5)
        d.addCallback(self._checkReqsSize,
                      [None, SUB_BLOCK_SIZE, SUB_BLOCK_SIZE] # Failed two times
                      + [BLOCK_SIZE - SUB_BLOCK_SIZE*2]
                      + [BLOCK_SIZE]*3 + [EXTRA_DATA])
        d.addCallback(self._checkReqsCode,
                      [None] + [common.SERVER_DISCONNECTED]*2 + [None]*5)

        # Now open another source and fail after two pipelined block
        d.addCallback(self._set, "reqmgr", "block_error_countdown", None)
        d.addCallback(self._set, "reqmgr", "global_error_countdown", 3)
        d.addCallback(self._set, "reqmgr", "block_error_code",
                      common.SERVER_UNAVAILABLE)

        d.addCallback(self._checkSessions, 1)
        d.addCallback(self._getSource, "http://www.flumotion.net/dummy")
        d.addCallback(self._gotSource, "source2", "session2")
        d.addCallback(self._isInstance, strategy_base.RemoteSource)
        d.addCallback(self._checkSessions, 1)

        d.addCallback(self._readAllData)
        d.addCallbacks(self._fail, self._checkError,
                       callbackArgs=("Success not expected", ),
                       errbackArgs=(fileprovider.FileError, ))
        d.addCallback(self._closeSource, "source2") # Must be closed anyway
        d.addCallback(self._checkSessions, 1)
        d.addCallback(self._checkFileCount, 1)
        d.addCallback(self._checkReqCount, 1 + 2 + 5 + 3)
        d.addCallback(self._checkReqsSize,
                      [None, SUB_BLOCK_SIZE, SUB_BLOCK_SIZE] # Failed two times
                      + [BLOCK_SIZE - SUB_BLOCK_SIZE*2]
                      + [BLOCK_SIZE]*3 + [EXTRA_DATA]
                      + [BLOCK_SIZE, BLOCK_SIZE, 0])
        d.addCallback(self._checkReqsCode,
                      [None] + [common.SERVER_DISCONNECTED]*2 + [None]*5
                      + [None]*2+ [common.SERVER_UNAVAILABLE])

        # Now we just stop failing and a new source should work just fine.
        # But to track pipelining request, we wait for the session to receive
        # a full block of data (that will not be pipelined).
        d.addCallback(self._set, "reqmgr", "block_error_countdown", None)
        d.addCallback(self._set, "reqmgr", "global_error_countdown", None)
        d.addCallback(self._set, "reqmgr", "block_error_code", None)

        d.addCallback(self._waitForSessionSize, "session", BLOCK_SIZE)

        d.addCallback(self._checkSessions, 1)
        d.addCallback(self._getSource, "http://www.flumotion.net/dummy")
        d.addCallback(self._gotSource, "source3", "session3")
        d.addCallback(self._isInstance, strategy_base.RemoteSource)
        d.addCallback(self._checkSessions, 1)

        d.addCallback(self._readAllData)
        d.addCallback(self._checkData, data)
        d.addCallback(self._closeSource, "source3")
        d.addCallback(self._checkFileCount, 1)
        d.addCallback(self._checkReqCount,
                      1 + 2 + 5 + 3
                      + self._reqCountFor(data) - 1) # One block already cached
        d.addCallback(self._checkReqsSize,
                      [None, SUB_BLOCK_SIZE, SUB_BLOCK_SIZE] # Failed two times
                      + [BLOCK_SIZE - SUB_BLOCK_SIZE*2]
                      + [BLOCK_SIZE]*3 + [EXTRA_DATA]
                      + [BLOCK_SIZE, BLOCK_SIZE, 0]
                      + [BLOCK_SIZE]*((len(data) // BLOCK_SIZE) - 1)
                      + [len(data) - (len(data) // BLOCK_SIZE) * BLOCK_SIZE])
        d.addCallback(self._checkReqsCode,
                      [None] + [common.SERVER_DISCONNECTED]*2 + [None]*5
                      + [None]*2+ [common.SERVER_UNAVAILABLE]
                      + [None] * (self._reqCountFor(data) - 1))

        d.addCallback(self._checkSessions, 1)

        d.addCallback(self._waitFinished, "session")

        # Only check the session request size (it's the first one)
        d.addCallback(self._checkReqsSize, [len(data)])

        d.addCallback(self._checkSessions, 0)
        d.addCallback(self._checkFilesClosed)

        d.callback(None)
        return d

    def testOutdatedWhilePipelining(self):
        data1 = os.urandom(BLOCK_SIZE*4 + EXTRA_DATA + 1)
        mtime1 = time.time() - 100
        data2 = os.urandom(BLOCK_SIZE*4 + EXTRA_DATA + 2)
        mtime2 = time.time()

        res = ResDef("/dummy", data1, mtime1)

        d = defer.Deferred()

        d.addCallback(self._setup, [], [res])

        # The file is not cached and the resource exists.
        # We artificially make the session transfer slow,
        # so it should serve the data using pipelining.
        # Then we can touch the resource while cached.

        # Make the transfer slow for the caching session
        d.addCallback(self._set, "reqmgr", "trans_delay", 0.08)

        d.addCallback(self._checkSessions, 0)
        d.addCallback(self._getSource, "http://www.flumotion.net/dummy")
        d.addCallback(self._gotSource, "source", "session")
        d.addCallback(self._isInstance, strategy_base.RemoteSource)
        d.addCallback(self._checkSessions, 1)

        # Wait for one block to be cached, this way the first block
        # will be read locally, and only then the second block will trigger
        # the expiration error.
        d.addCallback(self._waitForSessionSize, "session", BLOCK_SIZE)

        # Update the resource
        d.addCallback(self._updateResource, res, data2, mtime2)

        d.addCallback(self._checkSessions, 1)
        d.addCallback(self._readAllData)
        d.addCallbacks(self._fail, self._checkError,
                       callbackArgs=("Success not expected", ),
                       errbackArgs=(fileprovider.FileOutOfDate, ))
        d.addCallback(self._checkSessions, 0)
        d.addCallback(self._closeSource, "source")
        d.addCallback(self._checkFileCount, 1)
        d.addCallback(self._checkFilesClosed)
        d.addCallback(self._checkFilesUnlinked)
        d.addCallback(self._checkReqCount, 1 + 1) # Session + Failed pipelining
        d.addCallback(self._checkReqsCode, [None, common.STREAM_MODIFIED])

        d.callback(None)
        return d

    def testRandomReadFromCache(self):
        data = os.urandom(BLOCK_SIZE*4 + EXTRA_DATA)
        mtime = time.time()
        output = StringIO.StringIO()

        d = defer.Deferred()

        # First we read block by block in a random order

        d.addCallback(self._setup,
                      [FileDef("/dummy", data, mtime)],
                      [ResDef("/dummy", data, mtime)])

        d.addCallback(self._checkSessions, 0)
        d.addCallback(self._getSource, "http://www.flumotion.net/dummy")
        d.addCallback(self._gotSource, "source")
        d.addCallback(self._isInstance, strategy_base.CachedSource)
        d.addCallback(self._checkSessions, 0)

        d.addCallback(self._copyData, output, BLOCK_SIZE*4, BLOCK_SIZE)
        d.addCallback(self._copyData, output, BLOCK_SIZE*2, BLOCK_SIZE)
        d.addCallback(self._copyData, output, BLOCK_SIZE*0, BLOCK_SIZE)
        d.addCallback(self._copyData, output, BLOCK_SIZE*3, BLOCK_SIZE)
        d.addCallback(self._copyData, output, BLOCK_SIZE*1, BLOCK_SIZE)
        d.addCallback(lambda _: output.getvalue()) # Retrieve the copied data

        d.addCallback(self._checkData, data)
        d.addCallback(self._closeSource, "source")
        d.addCallback(self._checkFileCount, 1)
        d.addCallback(self._checkFilesClosed)
        d.addCallback(self._checkReqCount, 1) # Only the check request
        d.addCallback(self._checkReqsCode, common.STREAM_NOT_MODIFIED)
        d.addCallback(self._checkReqsSize, 0)

        d.addCallback(lambda _: output.truncate(0))

        # Then we try with random overlapping blocks of various small sizes

        d.addCallback(self._checkSessions, 0)
        d.addCallback(self._getSource, "http://www.flumotion.net/dummy")
        d.addCallback(self._gotSource, "source2")
        d.addCallback(self._isInstance, strategy_base.CachedSource)
        d.addCallback(self._checkSessions, 0)

        # Prepare the reads
        random.seed(42)
        reads = []
        currOffset = 0
        while currOffset <= len(data):
            offset = max(0, currOffset - random.randint(17, 127))
            shift = currOffset - offset
            size = random.randint(127, 509)
            currOffset = max(currOffset, currOffset - shift + size)
            reads.append((offset, size))

        random.shuffle(reads)

        for offset, size in reads:
            d.addCallback(self._copyData, output, offset, size)
        d.addCallback(lambda _: output.getvalue()) # Retrieve the copied data

        d.addCallback(self._checkData, data)
        d.addCallback(self._closeSource, "source2")
        d.addCallback(self._checkFileCount, 2)
        d.addCallback(self._checkFilesClosed)
        d.addCallback(self._checkReqCount, 1) # No check the second time

        d.callback(None)
        return d

    def testRandomPipelinedRead(self):
        data = os.urandom(BLOCK_SIZE*4 + EXTRA_DATA)
        mtime = time.time()
        output = StringIO.StringIO()

        d = defer.Deferred()

        # First we read block by block in a random order

        d.addCallback(self._setup, [], [ResDef("/dummy", data, mtime)])

        # Make the transfer slow for the caching session
        d.addCallback(self._set, "reqmgr", "trans_delay", 0.1)

        d.addCallback(self._checkSessions, 0)
        d.addCallback(self._getSource, "http://www.flumotion.net/dummy")
        d.addCallback(self._gotSource, "source", "session")
        d.addCallback(self._isInstance, strategy_base.RemoteSource)
        d.addCallback(self._checkSessions, 1)

        # Restoring normal speed for pipelining,
        d.addCallback(self._set, "reqmgr", "trans_delay", 0.001)

        d.addCallback(self._copyData, output, BLOCK_SIZE*4, BLOCK_SIZE)
        d.addCallback(self._copyData, output, BLOCK_SIZE*2, BLOCK_SIZE)
        d.addCallback(self._copyData, output, BLOCK_SIZE*0, BLOCK_SIZE)
        d.addCallback(self._copyData, output, BLOCK_SIZE*3, BLOCK_SIZE)
        d.addCallback(self._copyData, output, BLOCK_SIZE*1, BLOCK_SIZE)
        d.addCallback(lambda _: output.getvalue()) # Retrieve the copied data

        d.addCallback(self._checkData, data)
        d.addCallback(self._closeSource, "source")
        d.addCallback(self._checkFileCount, 1)
        d.addCallback(self._checkReqCount, 1 + 5) # Session + 5 pipelining
        d.addCallback(self._checkReqsCode, [None]*6)
        d.addCallback(self._checkReqsSize,
                      [None] + [EXTRA_DATA] + [BLOCK_SIZE]*4)

        d.addCallback(lambda _: output.truncate(0))

        # Then we try with random overlapping blocks of various small sizes

        d.addCallback(self._checkSessions, 1)
        d.addCallback(self._getSource, "http://www.flumotion.net/dummy")
        d.addCallback(self._gotSource, "source2")
        d.addCallback(self._isInstance, strategy_base.RemoteSource)
        d.addCallback(self._checkSessions, 1)

        # Prepare the reads
        random.seed(42)
        reads = []
        currOffset = 0
        while currOffset <= len(data):
            offset = max(0, currOffset - random.randint(17, 127))
            shift = currOffset - offset
            size = random.randint(127, 509)
            currOffset = max(currOffset, currOffset - shift + size)
            reads.append((offset, size))

        random.shuffle(reads)

        for offset, size in reads:
            d.addCallback(self._copyData, output, offset, size)
        d.addCallback(lambda _: output.getvalue()) # Retrieve the copied data

        d.addCallback(self._checkData, data)
        d.addCallback(self._waitFinished, "session")
        d.addCallback(self._checkSessions, 0)
        d.addCallback(self._closeSource, "source2")
        d.addCallback(self._checkFileCount, 1)
        d.addCallback(self._checkFilesClosed)
        # We can't check the request count reliably enough

        d.callback(None)
        return d

    def testSimultaneousReadsFromCache(self):
        mtime = time.time()
        data1 = os.urandom(BLOCK_SIZE*64 + EXTRA_DATA)
        data2 = os.urandom(BLOCK_SIZE*64 + EXTRA_DATA)
        data3 = os.urandom(BLOCK_SIZE*8 + EXTRA_DATA)
        data4 = os.urandom(BLOCK_SIZE*8 + EXTRA_DATA)
        data5 = os.urandom(EXTRA_DATA)
        data6 = os.urandom(EXTRA_DATA)

        d = defer.Deferred()

        # We retrieve two times six cached resources at the same time.

        d.addCallback(self._setup,
                      [FileDef("/dummy1", data1, mtime),
                       FileDef("/dummy2", data2, mtime),
                       FileDef("/dummy3", data3, mtime),
                       FileDef("/dummy4", data4, mtime),
                       FileDef("/dummy5", data5, mtime),
                       FileDef("/dummy6", data6, mtime)],
                      [ResDef("/dummy1", data1, mtime),
                       ResDef("/dummy2", data2, mtime),
                       ResDef("/dummy3", data3, mtime),
                       ResDef("/dummy4", data4, mtime),
                       ResDef("/dummy5", data5, mtime),
                       ResDef("/dummy6", data6, mtime)])

        d.addCallback(self._getSource, "http://www.flumotion.net/dummy1")
        d.addCallback(self._gotSource, "source1a")
        d.addCallback(self._isInstance, strategy_base.CachedSource)
        d.addCallback(self._checkSessions, 0)
        d.addCallback(self._checkFileCount, 1)
        d.addCallback(self._checkReqCount, 1) # expiration check

        d.addCallback(self._getSource, "http://www.flumotion.net/dummy2")
        d.addCallback(self._gotSource, "source2a")
        d.addCallback(self._isInstance, strategy_base.CachedSource)
        d.addCallback(self._checkSessions, 0)
        d.addCallback(self._checkFileCount, 2)
        d.addCallback(self._checkReqCount, 2) # expiration check

        d.addCallback(self._getSource, "http://www.flumotion.net/dummy3")
        d.addCallback(self._gotSource, "source3a")
        d.addCallback(self._isInstance, strategy_base.CachedSource)
        d.addCallback(self._checkSessions, 0)
        d.addCallback(self._checkFileCount, 3)
        d.addCallback(self._checkReqCount, 3) # expiration check

        d.addCallback(self._getSource, "http://www.flumotion.net/dummy4")
        d.addCallback(self._gotSource, "source4a")
        d.addCallback(self._isInstance, strategy_base.CachedSource)
        d.addCallback(self._checkSessions, 0)
        d.addCallback(self._checkFileCount, 4)
        d.addCallback(self._checkReqCount, 4) # expiration check

        d.addCallback(self._getSource, "http://www.flumotion.net/dummy5")
        d.addCallback(self._gotSource, "source5a")
        d.addCallback(self._isInstance, strategy_base.CachedSource)
        d.addCallback(self._checkSessions, 0)
        d.addCallback(self._checkFileCount, 5)
        d.addCallback(self._checkReqCount, 5) # expiration check

        d.addCallback(self._getSource, "http://www.flumotion.net/dummy6")
        d.addCallback(self._gotSource, "source6a")
        d.addCallback(self._isInstance, strategy_base.CachedSource)
        d.addCallback(self._checkSessions, 0)
        d.addCallback(self._checkFileCount, 6)
        d.addCallback(self._checkReqCount, 6) # expiration check

        # Now we open more sources for the same resources

        d.addCallback(self._getSource, "http://www.flumotion.net/dummy1")
        d.addCallback(self._gotSource, "source1b")
        d.addCallback(self._isInstance, strategy_base.CachedSource)
        d.addCallback(self._checkSessions, 0)
        d.addCallback(self._checkFileCount, 7)
        d.addCallback(self._checkReqCount, 6)

        d.addCallback(self._getSource, "http://www.flumotion.net/dummy2")
        d.addCallback(self._gotSource, "source2b")
        d.addCallback(self._isInstance, strategy_base.CachedSource)
        d.addCallback(self._checkSessions, 0)
        d.addCallback(self._checkFileCount, 8)
        d.addCallback(self._checkReqCount, 6)

        d.addCallback(self._getSource, "http://www.flumotion.net/dummy3")
        d.addCallback(self._gotSource, "source3b")
        d.addCallback(self._isInstance, strategy_base.CachedSource)
        d.addCallback(self._checkSessions, 0)
        d.addCallback(self._checkFileCount, 9)
        d.addCallback(self._checkReqCount, 6)

        d.addCallback(self._getSource, "http://www.flumotion.net/dummy4")
        d.addCallback(self._gotSource, "source4b")
        d.addCallback(self._isInstance, strategy_base.CachedSource)
        d.addCallback(self._checkSessions, 0)
        d.addCallback(self._checkFileCount, 10)
        d.addCallback(self._checkReqCount, 6)

        d.addCallback(self._getSource, "http://www.flumotion.net/dummy5")
        d.addCallback(self._gotSource, "source5b")
        d.addCallback(self._isInstance, strategy_base.CachedSource)
        d.addCallback(self._checkSessions, 0)
        d.addCallback(self._checkFileCount, 11)
        d.addCallback(self._checkReqCount, 6)

        d.addCallback(self._getSource, "http://www.flumotion.net/dummy6")
        d.addCallback(self._gotSource, "source6b")
        d.addCallback(self._isInstance, strategy_base.CachedSource)
        d.addCallback(self._checkSessions, 0)
        d.addCallback(self._checkFileCount, 12)
        d.addCallback(self._checkReqCount, 6)

        def getSource(name):
            return self.sources[name]

        def readAndCheck(srcName, data):
            d = defer.Deferred()
            d.addCallback(getSource)
            d.addCallback(self._readAllData)
            d.addCallback(self._checkData, data)
            d.addCallback(self._closeSource, srcName)
            d.callback(srcName)
            return d

        def parallelReadAndCheck(result, items):
            deferrers = []
            for srcName, data in items:
                deferrers.append(readAndCheck(srcName, data))
            d = defer.DeferredList(deferrers, fireOnOneErrback=True)
            d.addCallback(lambda _: result)
            return d

        d.addCallback(parallelReadAndCheck,
                      [("source1a", data1),
                       ("source2a", data2),
                       ("source3a", data3),
                       ("source4a", data4),
                       ("source5a", data5),
                       ("source6a", data6),
                       ("source1b", data1),
                       ("source2b", data2),
                       ("source3b", data3),
                       ("source4b", data4),
                       ("source5b", data5),
                       ("source6b", data6)])

        d.addCallback(self._checkFileCount, 12)
        d.addCallback(self._checkFilesClosed)
        d.addCallback(self._checkReqCount, 6)

        d.callback(None)
        return d

    def testMultipleSessions(self):
        mtime = time.time()
        data1 = os.urandom(BLOCK_SIZE*64 + EXTRA_DATA)
        data2 = os.urandom(BLOCK_SIZE*64 + EXTRA_DATA)
        data3 = os.urandom(BLOCK_SIZE*8 + EXTRA_DATA)
        data4 = os.urandom(BLOCK_SIZE*8 + EXTRA_DATA)
        data5 = os.urandom(EXTRA_DATA)
        data6 = os.urandom(EXTRA_DATA)

        d = defer.Deferred()

        # We retrieve two times six resources at the same time,
        # so it's 6 simultaneous sessions and 10 sources
        # Half of the sessions are made to be slow
        # for the reading being pipelined.

        d.addCallback(self._setup, [],
                      [ResDef("/dummy1", data1, mtime),
                       ResDef("/dummy2", data2, mtime),
                       ResDef("/dummy3", data3, mtime),
                       ResDef("/dummy4", data4, mtime),
                       ResDef("/dummy5", data5, mtime),
                       ResDef("/dummy6", data6, mtime)])

        d.addCallback(self._checkSessions, 0)

        # First the big ones, to prevent sessions
        # from finishing before all are started
        # The first session out of each two is made to be slow
        # to ensure some reads are pipelined

        d.addCallback(self._set, "reqmgr", "trans_delay", 0.04)
        d.addCallback(self._getSource, "http://www.flumotion.net/dummy1")
        d.addCallback(self._gotSource, "source1a", "session1")
        d.addCallback(self._isInstance, strategy_base.RemoteSource)
        d.addCallback(self._checkSessions, 1)
        d.addCallback(self._checkFileCount, 1)
        d.addCallback(self._checkReqCount, 1)

        d.addCallback(self._set, "reqmgr", "trans_delay", 0.01)
        d.addCallback(self._getSource, "http://www.flumotion.net/dummy2")
        d.addCallback(self._gotSource, "source2a", "session2")
        d.addCallback(self._isInstance, strategy_base.RemoteSource)
        d.addCallback(self._checkSessions, 2)
        d.addCallback(self._checkFileCount, 2)
        d.addCallback(self._checkReqCount, 2)

        d.addCallback(self._set, "reqmgr", "trans_delay", 0.04)
        d.addCallback(self._getSource, "http://www.flumotion.net/dummy3")
        d.addCallback(self._gotSource, "source3a", "session3")
        d.addCallback(self._isInstance, strategy_base.RemoteSource)
        d.addCallback(self._checkSessions, 3)
        d.addCallback(self._checkFileCount, 3)
        d.addCallback(self._checkReqCount, 3)

        d.addCallback(self._set, "reqmgr", "trans_delay", 0.01)
        d.addCallback(self._getSource, "http://www.flumotion.net/dummy4")
        d.addCallback(self._gotSource, "source4a", "session4")
        d.addCallback(self._isInstance, strategy_base.RemoteSource)
        d.addCallback(self._checkSessions, 4)
        d.addCallback(self._checkFileCount, 4)
        d.addCallback(self._checkReqCount, 4)

        d.addCallback(self._set, "reqmgr", "trans_delay", 0.04)
        d.addCallback(self._getSource, "http://www.flumotion.net/dummy5")
        d.addCallback(self._gotSource, "source5a", "session5")
        d.addCallback(self._isInstance, strategy_base.RemoteSource)
        d.addCallback(self._checkSessions, 5)
        d.addCallback(self._checkFileCount, 5)
        d.addCallback(self._checkReqCount, 5)

        d.addCallback(self._set, "reqmgr", "trans_delay", 0.01)
        d.addCallback(self._getSource, "http://www.flumotion.net/dummy6")
        d.addCallback(self._gotSource, "source6a", "session6")
        d.addCallback(self._isInstance, strategy_base.RemoteSource)
        d.addCallback(self._checkSessions, 6)
        d.addCallback(self._checkFileCount, 6)
        d.addCallback(self._checkReqCount, 6)

        # Now we open more sources for the same resources

        d.addCallback(self._getSource, "http://www.flumotion.net/dummy1")
        d.addCallback(self._gotSource, "source1b")
        d.addCallback(self._isInstance, strategy_base.RemoteSource)
        d.addCallback(self._checkSessions, 6)
        d.addCallback(self._checkFileCount, 6)
        d.addCallback(self._checkReqCount, 6)

        d.addCallback(self._getSource, "http://www.flumotion.net/dummy2")
        d.addCallback(self._gotSource, "source2b")
        d.addCallback(self._isInstance, strategy_base.RemoteSource)
        d.addCallback(self._checkSessions, 6)
        d.addCallback(self._checkFileCount, 6)
        d.addCallback(self._checkReqCount, 6)

        d.addCallback(self._getSource, "http://www.flumotion.net/dummy3")
        d.addCallback(self._gotSource, "source3b")
        d.addCallback(self._isInstance, strategy_base.RemoteSource)
        d.addCallback(self._checkSessions, 6)
        d.addCallback(self._checkFileCount, 6)
        d.addCallback(self._checkReqCount, 6)

        d.addCallback(self._getSource, "http://www.flumotion.net/dummy4")
        d.addCallback(self._gotSource, "source4b")
        d.addCallback(self._isInstance, strategy_base.RemoteSource)
        d.addCallback(self._checkSessions, 6)
        d.addCallback(self._checkFileCount, 6)
        d.addCallback(self._checkReqCount, 6)

        d.addCallback(self._getSource, "http://www.flumotion.net/dummy5")
        d.addCallback(self._gotSource, "source5b")
        d.addCallback(self._isInstance, strategy_base.RemoteSource)
        d.addCallback(self._checkSessions, 6)
        d.addCallback(self._checkFileCount, 6)
        d.addCallback(self._checkReqCount, 6)

        d.addCallback(self._getSource, "http://www.flumotion.net/dummy6")
        d.addCallback(self._gotSource, "source6b")
        d.addCallback(self._isInstance, strategy_base.RemoteSource)
        d.addCallback(self._checkSessions, 6)
        d.addCallback(self._checkFileCount, 6)
        d.addCallback(self._checkReqCount, 6)

        def getSource(name):
            return self.sources[name]

        def readAndCheck(srcName, data):
            d = defer.Deferred()
            d.addCallback(getSource)
            d.addCallback(self._readAllData)
            d.addCallback(self._checkData, data)
            d.addCallback(self._closeSource, srcName)
            d.callback(srcName)
            return d

        def parallelReadAndCheck(result, items):
            deferrers = []
            for srcName, data in items:
                deferrers.append(readAndCheck(srcName, data))
            d = defer.DeferredList(deferrers, fireOnOneErrback=True)
            d.addCallback(lambda _: result)
            return d

        d.addCallback(parallelReadAndCheck,
                      [("source1a", data1),
                       ("source2a", data2),
                       ("source3a", data3),
                       ("source4a", data4),
                       ("source5a", data5),
                       ("source6a", data6),
                       ("source1b", data1),
                       ("source2b", data2),
                       ("source3b", data3),
                       ("source4b", data4),
                       ("source5b", data5),
                       ("source6b", data6)])

        d.addCallback(self._waitFinished, "session6")
        d.addCallback(self._waitFinished, "session5")
        d.addCallback(self._waitFinished, "session4")
        d.addCallback(self._waitFinished, "session3")
        d.addCallback(self._waitFinished, "session2")
        d.addCallback(self._waitFinished, "session1")
        d.addCallback(self._checkSessions, 0)

        d.addCallback(self._checkFileCount, 6)
        d.addCallback(self._checkFilesClosed)
        # We cannot check the request count because
        # the number of read pipelined is not reliable
        d.addCallback(self._checkReqsSize,
                      [len(data1), len(data2), len(data3),
                       len(data4), len(data5), len(data6)])

        d.callback(None)
        return d

    def testCacheAllocationFailure(self):
        data = os.urandom(BLOCK_SIZE*4 + EXTRA_DATA)
        mtime = time.time()

        d = defer.Deferred()

        d.addCallback(self._setup, [], [ResDef("/dummy", data, mtime)])

        # The file is not cached and the resource exists.
        # But we setup the dummy cache manager to fail temp file allocation.

        d.addCallback(self._set, "cachemgr", "can_cache", False)

        d.addCallback(self._checkSessions, 0)
        d.addCallback(self._getSource, "http://www.flumotion.net/dummy")
        d.addCallback(self._gotSource, "source", "session")
        d.addCallback(self._isInstance, strategy_base.RemoteSource)
        d.addCallback(self._checkSessions, 1)
        d.addCallback(self._checkReqCount, 1) # It tried to start caching

        d.addCallback(self._readAllData)
        d.addCallback(self._checkData, data)
        d.addCallback(self._closeSource, "source")
        # The session has been aborted,
        # it should finish when all sources are closed
        d.addCallback(self._checkSessions, 0)
        d.addCallback(self._checkFileCount, 0)
        d.addCallback(self._checkReqCount, 1 + 5)
        d.addCallback(self._checkReqsCode, [None]*6) # No error
        d.addCallback(self._checkReqsSize, [None]+[BLOCK_SIZE]*4+[EXTRA_DATA])

        d.callback(None)
        return d

    def testSessionRecovering(self):
        data = os.urandom(BLOCK_SIZE*4 + EXTRA_DATA)
        mtime = time.time()

        d = defer.Deferred()

        d.addCallback(self._setup, [], [ResDef("/dummy", data, mtime)])

        # The file is not cached and the resource exists.
        # When the session got a sub-block, the "server" is disconnected.
        # This will happen two times, then the session should recover.

        # We will fail after 2 sub-blocks (Only the session)
        d.addCallback(self._set, "reqmgr", "error_reset_countdown", 2)
        d.addCallback(self._set, "reqmgr", "block_error_countdown", 2)
        d.addCallback(self._set, "reqmgr", "block_error_code",
                      common.SERVER_DISCONNECTED)

        d.addCallback(self._checkSessions, 0)
        d.addCallback(self._getSource, "http://www.flumotion.net/dummy")
        d.addCallback(self._gotSource, "source", "session")
        d.addCallback(self._isInstance, strategy_base.RemoteSource)
        d.addCallback(self._checkSessions, 1)
        d.addCallback(self._checkReqCount, 1) # It tried to start caching

        # Wait a little
        d.addCallback(self._waitForSessionSize, "session", BLOCK_SIZE)

        # and slow down reading to prevent pipelining
        d.addCallback(self._readAllData, 0.05)
        d.addCallback(self._checkData, data)
        d.addCallback(self._closeSource, "source")
        d.addCallback(self._waitFinished, "session")
        d.addCallback(self._checkSessions, 0)
        d.addCallback(self._checkFileCount, 1)
        d.addCallback(self._checkFilesClosed)
        d.addCallback(self._checkReqCount, 3) # original + recovery * 2
        d.addCallback(self._checkReqsCode,
                      [common.SERVER_DISCONNECTED,
                       common.SERVER_DISCONNECTED, None])
        d.addCallback(self._checkReqsSize,
                      [SUB_BLOCK_SIZE]*2+[len(data)-SUB_BLOCK_SIZE*2])

        d.callback(None)
        return d

    def testExpirationWhileSessionRecovering(self):
        data1 = os.urandom(BLOCK_SIZE*4 + EXTRA_DATA + 10)
        mtime1 = time.time() - 100
        data2 = os.urandom(BLOCK_SIZE*4 + EXTRA_DATA + 20)
        mtime2 = time.time()

        res = ResDef("/dummy", data1, mtime1)

        d = defer.Deferred()

        d.addCallback(self._setup, [], [res])

        # The file is not cached and the resource exists.
        # When the session got a sub-block, the "server" is disconnected.
        # But then the resource is out of date.
        # The session and associated resources should just fail.

        # We will fail after 2 sub-blocks (Only the session)
        d.addCallback(self._set, "reqmgr", "error_reset_countdown", 1)
        d.addCallback(self._set, "reqmgr", "block_error_countdown", 2)
        d.addCallback(self._set, "reqmgr", "block_error_code",
                      common.SERVER_TIMEOUT)

        d.addCallback(self._checkSessions, 0)
        d.addCallback(self._getSource, "http://www.flumotion.net/dummy")
        d.addCallback(self._gotSource, "source", "session")
        d.addCallback(self._isInstance, strategy_base.RemoteSource)
        d.addCallback(self._checkSessions, 1)
        d.addCallback(self._checkReqCount, 1) # It tried to start to cache

        d.addCallback(self._updateResource, res, data=data2, mtime=mtime2)

        # Wait for the session to be finished or to fail
        d.addCallback(self._waitFinished, "session")

        d.addCallback(self._readAllData)
        d.addCallbacks(self._fail, self._checkError,
                       callbackArgs=("Success not expected", ),
                       errbackArgs=(fileprovider.FileOutOfDate, ))
        d.addCallback(self._checkSessions, 0)
        d.addCallback(self._checkFileCount, 1)
        d.addCallback(self._checkFilesClosed)
        d.addCallback(self._checkFilesUnlinked)
        d.addCallback(self._checkReqCount, 2)
        d.addCallback(self._checkReqsCode,
                      [common.SERVER_TIMEOUT, common.STREAM_MODIFIED])
        d.addCallback(self._checkReqsSize,
                      [SUB_BLOCK_SIZE, 0])

        d.callback(None)
        return d

    def _setup(self, _, files, resources, ttl=DEFAULT_TTL):
        self.cachemgr = DummyCacheMgr(*files)
        self.reqmgr = DummyReqMgr(*resources)
        self.stgy = strategy_basic.CachingStrategy(self.cachemgr,
                                                   self.reqmgr, ttl)
        return self.stgy.setup()

    def _getSource(self, _, urlstr):
        url = http_utils.Url.fromString(urlstr)
        return self.stgy.getSourceFor(url, DummyRequestStatistics())

    def _reset(self, result):
        self.cachemgr.reset()
        self.reqmgr.reset()
        return result

    def _gotSource(self, source, srcName=None, sessName=None):
        if srcName:
            old = self.sources.get(srcName, None)
            self.failIf(old is not None)
            self.sources[srcName] = source
            if sessName:
                old = self.sources.get(sessName, None)
                self.failIf(old is not None)
                sess = getattr(source, "session", None)
                self.sessions[sessName] = sess
        return source

    def _reqCountFor(self, data):
        fullBlocks = len(data) // BLOCK_SIZE
        partialBlocks = int(len(data) % BLOCK_SIZE > 0)
        return fullBlocks + partialBlocks

    def _updateResource(self, result, res, data=None, mtime=None):
        if data is not None:
            res.data = data
        if mtime is not None:
            res.mtime = mtime
        return result

    def _closeSource(self, result, srcName=None, sessName=None):
        if srcName and srcName in self.sources:
            src = self.sources[srcName]
            src.close()
            del self.sources[srcName]

    def _waitForSessionSize(self, result, sessName, size):
        sess = self.sessions[sessName]
        d = defer.Deferred()
        self._checkSessionSize(sess, size, d, result)
        return d

    def _checkSessionSize(self, sess, size, d, result):
        if sess._bytes >= size:
            d.callback(result)
        else:
            reactor.callLater(0.01, self._checkSessionSize,
                              sess, size, d, result)

    def _waitFinished(self, result, sessName):
        sess = self.sessions.get(sessName, None)
        if sess is not None:
            return sess.waitFinished()
        return result

    def _set(self, result, name, attr, val):
        obj = getattr(self, name)
        setattr(obj, attr, val)
        return result

    def _readAllData(self, source, delay=0.0001, acc=""):
        d = defer.Deferred()
        d.addCallback(source.read, BLOCK_SIZE)
        # Prevent deep recursion if read is not asynchronous
        d.addCallback(wait, delay)
        d.addCallback(self._gotData, source, delay, acc)
        d.callback(len(acc))
        return d

    def _gotData(self, data, source, delay, acc):
        if not data:
            return acc
        return self._readAllData(source, delay, acc + data)

    def _copyData(self, source, output, offset, size):
        d = defer.Deferred()
        d.addCallback(source.read, size)
        # Prevent deep recursion if read is not asynchronous
        d.addCallback(wait, 0.0001)
        d.addCallback(self._gotDataToCopy, source, offset, output)
        d.callback(offset)
        return d

    def _gotDataToCopy(self, data, source, offset, output):
        output.seek(offset)
        output.write(data)
        return source

    def _debug(self, data, prefix=">"*40):
        print prefix, data
        return data

    def _checkData(self, data, orig):
        self.failUnless(data == orig)
        return data

    def _isInstance(self, result, cls):
        self.assertEqual(type(result), cls)
        return result

    def _fail(self, _, msg):
        self.fail(msg)

    def _checkError(self, failure, expected):
        self.failUnless(failure.check(expected))
        return

    def _checkSessions(self, result, count):
        self.assertEqual(len(self.stgy.getSessions()), count)
        return result

    def _checkFilesClosed(self, result):
        for f in self.cachemgr.files:
            self.failIf(f.opened and not f.closed)
        return result

    def _checkFilesUnlinked(self, result):
        for f in self.cachemgr.files:
            self.failIf(f.opened and not f.unlinked)
        return result

    def _checkFilesCompleted(self, result):
        for f in self.cachemgr.files:
            self.failIf(f.opened and not f.completed)
        return result

    def _checkFileCount(self, result, count):
        self.assertEqual(len(self.cachemgr.files), count)
        return result

    def _checkReqCount(self, result, count):
        self.assertEqual(len(self.reqmgr.resources), count)
        return result

    def _checkReqsCode(self, result, code):
        if isinstance(code, list):
            for r in self.reqmgr.resources:
                if not code:
                    break
                self.assertEqual(r.code, code.pop(0))
        else:
            for r in self.reqmgr.resources:
                self.assertEqual(r.code, code)
        return result

    def _checkReqsSize(self, result, size):
        if isinstance(size, (tuple, list)):
            for r in self.reqmgr.resources:
                if not size:
                    break
                expected = size.pop(0)
                if expected is not None:
                    self.assertEqual(r.size, expected)
        else:
            for r in self.reqmgr.resources:
                self.assertEqual(r.size, size)
        return result



######################################################################
##### Utility Functions and Dummy Classes
######################################################################


def path2ident(path):
    hash = python.sha1()
    hash.update(path)
    return hash.digest().encode("hex").strip('\n')


def wait(result, timeout):
    d = defer.Deferred()
    reactor.callLater(timeout, d.callback, result)
    return d


def passthrough(result, fun, *args, **kwargs):
    fun(*args, **kwargs)
    return result


class DummyStat(object):

    def __init__(self, size, mtime, atime):
        self.st_mtime = float(mtime)
        self.st_atime = float(atime)
        self.st_size = size

    def __getitem__(self, item):
        if item == stat.ST_SIZE:
            return self.st_size
        if item == stat.ST_MTIME:
            return self.st_mtime
        if item == stat.ST_ATIME:
            return self.st_atime
        raise KeyError(item)


class DummyFile(object):

    def __init__(self, mgr, fdef, size=None, isTemp=False):
        self.mgr = mgr
        self.fdef = fdef
        self._isTemp = isTemp
        self.opened = False
        self.closed = False
        self.completed = False
        self.unlinked = False

        self.name = fdef.path

        data = fdef.data or ""
        if size:
            data = data + "\000"*(size - len(data))

        self.data = StringIO.StringIO(data)

        mtime = fdef.mtime or time.time()
        atime = fdef.atime or mtime
        self.stat = DummyStat(len(data), mtime, atime)

    def tell(self):
        return self.data.tell()

    def unlink(self):
        self.unlinked = True
        self.mgr._unlinked(self.fdef)

    def write(self, data):
        assert not self.closed, "File Closed"
        assert self.fdef.data is None, "Not writable"
        self.data.write(data)

    def read(self, size):
        assert not self.closed, "File Closed"
        return self.data.read(size)

    def seek(self, pos):
        assert not self.closed, "File Closed"
        self.data.seek(pos)

    def complete(self):
        assert not self.closed, "File Closed"
        assert not self.completed, "File Completed"
        assert self._isTemp, "Cannot complete non-temp files"
        self.completed = True
        self.fdef.data = self.data.getvalue()
        self.mgr._completed(self.fdef)

    def close(self):
        assert not self.closed, "File Closed"
        if self._isTemp and not self.completed:
            self.unlink()
        self.closed = True


class FileDef(object):

    def __init__(self, path, data, mtime=None, atime=None):
        self.identifier = path2ident(path)
        self.path = path
        self.data = data
        self.mtime = mtime or time.time()
        self.atime = atime or self.mtime


class DummyRequestStatistics(object):

    def __init__(self):
        pass

    def onStarted(self, size, cacheStatus):
        pass

    def onCacheOutdated(self):
        pass

    def onBytesRead(self, fromSource, fromCache, correction):
        pass

    def onClosed(self):
        pass


class DummyStatistics:

    def __init__(self):
        pass

    def onCopyStarted(self):
        pass

    def onCopyCancelled(self, size, copied):
        pass

    def onCopyFinished(self, size):
        pass


class DummyCacheMgr(object):

    can_cache = True
    open_cached_delay = 0.01
    new_temp_delay = 0.01

    def __init__(self, *files):
        self.defs = dict([(f.path, f) for f in files])
        self.files = []
        self.calls = {}
        self.stats = DummyStatistics()

    def reset(self):
        self.files = []
        for _key, dc in self.calls.items():
            dc.cancel()
        self.calls = {}

    def final_reset(self):
        self.reset()
        self.calls = None

    def getIdentifier(self, path):
        return path2ident(path)

    def openCacheFile(self, path):
        if self.calls is None:
            return
        if path in self.defs:
            f = DummyFile(self, self.defs[path])
            self.files.append(f)
            return self._delayed(self.open_cached_delay, f)
        return self._delayed(self.open_cached_delay, None)

    def newTempFile(self, path, size, mtime=None):
        if not self.can_cache:
            return self._delayed(self.new_temp_delay, None)
        if self.calls is None:
            return
        fdef = FileDef(path, None, mtime)
        f = DummyFile(self, fdef, isTemp=True)
        self.files.append(f)
        return self._delayed(self.new_temp_delay, f)

    def _completed(self, fdef):
        self.defs[fdef.path] = fdef

    def _unlinked(self, fdef):
        if fdef.path in self.defs:
            del self.defs[fdef.path]

    def _delayed(self, timeout, value):
        d = defer.Deferred()
        d.addCallback(self._set_open)
        self._call(timeout, os.urandom(64), d.callback, value)
        return d

    def _set_open(self, file):
        if file is not None:
            file.opened = True
        return file

    def _call(self, timeout, key, fun, *args, **kwargs):
        dc = reactor.callLater(timeout, self._called, key, fun, args, kwargs)
        self.calls[key] = dc

    def _called(self, key, fun, args, kwargs):
        if key in self.calls:
            del self.calls[key]
            fun(*args, **kwargs)


class DummyInfo(object):

    def __init__(self, length, start, size, mtime):
        self.expires = None
        self.mtime = mtime
        self.length = length
        self.start = start
        self.size = size


class ResDef(object):

    def __init__(self, path, data, mtime):
        self.path = path
        self.data = data
        self.mtime = mtime


class DummyReq(object):

    def __init__(self, mgr, code=None):
        self.reply_delay = mgr.reply_delay
        self.trans_delay = mgr.trans_delay
        self.trans_block = mgr.trans_block
        self.block_error_countdown = mgr.block_error_countdown
        self.block_error_code = mgr.block_error_code
        self.code = code
        self.size = 0
        self.canceled = False

        self.logName = "Dummy"

    def cancel(self):
        self.canceled = True


class DummyReqMgr(object):

    reply_delay = 0.001
    trans_delay = 0.001
    trans_block = SUB_BLOCK_SIZE
    available = True
    connTimeout = None
    error_reset_countdown = None
    global_error_countdown = None
    block_error_countdown = None
    block_error_code = None

    def __init__(self, *resources):
        self.defs = dict([(r.path, r) for r in resources])
        self.resources = []
        self.calls = {}

    def reset(self):
        self.resources = []
        for _key, dc in self.calls.items():
            dc.cancel()
        self.calls = {}

    def final_reset(self):
        self.reset()
        self.calls = None

    def retrieve(self, consumer, url, start=None, size=None,
                 ifModifiedSince=None, ifUnmodifiedSince=None):
        if self.calls is None:
            return

        req = DummyReq(self)

        if self.error_reset_countdown is not None:
            self.error_reset_countdown -= 1
            if self.error_reset_countdown <= 0:
                self.error_reset_countdown = None
                self.global_error_countdown = None
                self.block_error_countdown = None

        if self.global_error_countdown is not None:
            self.global_error_countdown -= 1
            if self.global_error_countdown <= 0:
                self._call(req.reply_delay, req, self._serverError,
                       consumer, req, self.block_error_code)
                self.resources.append(req)
                return req

        if not self.available:
            self._call(req.reply_delay, req, self._serverError,
                       consumer, req, common.SERVER_UNAVAILABLE)
            self.resources.append(req)
            return req

        if self.connTimeout:
            self._call(self.connTimeout, req, self._serverError,
                       consumer, req, common.SERVER_UNAVAILABLE)
            self.resources.append(req)
            return req

        if url.path not in self.defs:
            self._call(req.reply_delay, req,
                       self._notFoundError, consumer, req)
            self.resources.append(req)
            return req

        rdef = self.defs[url.path]

        if ifModifiedSince:
            if ifModifiedSince >= rdef.mtime:
                self._call(req.reply_delay, req, self._conditionFail,
                           consumer, req, common.STREAM_NOT_MODIFIED)
                self.resources.append(req)
                return req

        if ifUnmodifiedSince:
            if ifUnmodifiedSince < rdef.mtime:
                self._call(req.reply_delay, req, self._conditionFail,
                           consumer, req, common.STREAM_MODIFIED)
                self.resources.append(req)
                return req

        if (start or 0) >= len(rdef.data):
            self._call(req.reply_delay, req, self._serverError,
                       consumer, req, common.RANGE_NOT_SATISFIABLE)
            self.resources.append(req)
            return req

        if start is not None:
            if size is not None:
                data = rdef.data[start:start+size]
            else:
                data = rdef.data[start:]
        else:
            data = rdef.data

        info = DummyInfo(len(rdef.data), start, len(data), rdef.mtime)
        self._call(req.reply_delay, req, self._success,
                   consumer, req, info, data)
        self.resources.append(req)
        return req

    def _call(self, timeout, key, fun, *args, **kwargs):
        dc = reactor.callLater(timeout, self._called, key, fun, args, kwargs)
        self.calls[key] = dc

    def _called(self, key, fun, args, kwargs):
        del self.calls[key]
        fun(*args, **kwargs)

    def _canceled(self, req):
        return req.canceled or req not in self.resources

    def _success(self, consumer, req, info, data):
        if self._canceled(req):
            return
        consumer.onInfo(self, info)
        self._scheduleBlock(consumer, req, data)

    def _scheduleBlock(self, consumer, req, data):
        if self._canceled(req):
            return
        self._call(req.trans_delay, req,
                   self._sendBlock, consumer, req, data)

    def _sendBlock(self, consumer, req, data):
        if self._canceled(req):
            return

        if req.block_error_countdown is not None:
            req.block_error_countdown -= 1
            if req.block_error_countdown <= 0:
                self._serverError(consumer, req, req.block_error_code)
                return

        if data:
            block = data[:req.trans_block]
            data = data[req.trans_block:]
            req.size += len(block)
            consumer.onData(self, block)
            self._scheduleBlock(consumer, req, data)
        else:
            consumer.streamDone(req)

    def _serverError(self, consumer, req, code):
        if self._canceled(req):
            return
        req.code = code
        consumer.serverError(req, code, "Server Error")

    def _conditionFail(self, consumer, req, code):
        if self._canceled(req):
            return
        req.code = code
        consumer.conditionFail(req, code, "Condition Failed")

    def _notFoundError(self, consumer, req):
        if self._canceled(req):
            return
        req.code = 404
        consumer.streamNotAvailable(req, 404, "Not Found")

    def setup(self):
        pass

    def cleanup(self):
        pass
