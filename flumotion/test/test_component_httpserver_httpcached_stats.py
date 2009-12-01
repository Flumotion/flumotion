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
import shutil
import tempfile

import twisted
from twisted.internet import reactor, defer
from twisted.trial import unittest

import twisted.copyright
if twisted.copyright.version == "SVN-Trunk":
    SKIP_MSG = "Twisted 2.0.1 thread pool is broken for tests"
else:
    SKIP_MSG = None

from twisted.web import resource
from twisted.web.server import Site
from twisted.web.static import File

from flumotion.common.testsuite import TestCase
from flumotion.component.misc.httpserver.httpcached import file_provider
from flumotion.component.misc.httpserver import fileprovider

CACHE_SIZE = 1024 * 1024
twisted.internet.base.DelayedCall.debug = True


class DummyStats(object):

    def __init__(self):
        self.stats = {}

    def update(self, key, val):
        self.stats[key] = val


class TestHTTPCachedPlugStats(TestCase):

    skip = SKIP_MSG

    def setUp(self):
        from twisted.python import threadpool
        reactor.threadpool = threadpool.ThreadPool(0, 10)
        reactor.threadpool.start()

        class Hello(resource.Resource):
            isLeaf = True

            def render_GET(self, request):
                return "<html>Hello, world!</html>"

        self.src_path = tempfile.mkdtemp(suffix=".src")
        self.cache_path = tempfile.mkdtemp(suffix=".cache")
        self._resource = None

        self.createSrcFile("a", "content of a")

        src = File(self.src_path)
        src.putChild("hello", Hello())
        factory = Site(src)
        self.httpserver = reactor.listenTCP(0, factory)
        p = self.httpserver.getHost().port

        plugProps = {"properties": {"cache-size": CACHE_SIZE,
                                    "cache-dir": self.cache_path,
                                    "virtual-hostname": "localhost",
                                    "virtual-port": p}}

        self.plug = \
            file_provider.FileProviderHTTPCachedPlug(plugProps)

        self.stats = DummyStats()
        self.plug.startStatsUpdates(self.stats)

        return self.plug.start(None)

    def tearDown(self):
        d = self.plug.stop(None)

        def finish_cleanup(_):
            self.plug.stopStatsUpdates()
            self.httpserver.stopListening()
            shutil.rmtree(self.cache_path, ignore_errors=True)
            shutil.rmtree(self.src_path, ignore_errors=True)

            reactor.threadpool.stop()
            reactor.threadpool = None

        d.addCallback(finish_cleanup)
        return d

    def test404(self):
        d = self.plug.getRootPath().child("SuperMan").open()
        d.addCallback(lambda x: x.close())
        d.addErrback(lambda f: f.trap(fileprovider.NotFoundError))
        d.addCallback(lambda x:
            self.failIf('cache-hit-count' in self.stats.stats))
        d.addCallback(lambda x:
            self.failIf('cache-miss-count' in self.stats.stats))
        return d

    def testMissHit(self):
        d = self.plug.getRootPath().child("a").open()
        d.addCallback(lambda x: self.checkResourceContent(x, "content of a"))
        d.addCallback(lambda x: setattr(self, "_resource", x))
        d.addCallback(lambda x: self._resource.getLogFields())
        d.addCallback(lambda x: self.failIf(x['cache-status'] == 'cache-hit'))
        d.addCallback(lambda x: self._resource.close())
        d.addCallback(lambda x:
            self.assertEqual(self.stats.stats['cache-miss-count'], 1))
        d.addCallback(lambda x:
            self.assertEqual(self.stats.stats['cache-hit-count'], 0))
        d.addCallback(lambda x:
            self.assertEqual(self.stats.stats['temp-hit-count'], 0))

        d.addCallback(lambda x: self.plug.getRootPath().child("a").open())
        d.addCallback(lambda x: setattr(self, "_resource", x))
        d.addCallback(lambda x: self._resource.close())
        d.addCallback(lambda x:
            self.assertEqual(self.stats.stats['cache-miss-count'], 1))
        d.addCallback(lambda x:
            self.assertEqual(self.stats.stats['cache-hit-count'], 1))

        d.addCallback(lambda x: self.plug.getRootPath().child("a").open())
        d.addCallback(lambda x: setattr(self, "_resource", x))
        d.addCallback(lambda x: self._resource.close())
        d.addCallback(lambda x:
            self.assertEqual(self.stats.stats['cache-miss-count'], 1))
        d.addCallback(lambda x:
            self.assertEqual(self.stats.stats['cache-hit-count'], 2))

        return d

    ### Helper functions ###

    def createSrcFile(self, name, data):
        fname = os.path.join(self.src_path, name)
        testFile = open(fname, "w")
        testFile.write(data)
        testFile.close()

    def checkResourceContent(self, resource, content):
        d = resource.read(resource.getsize())
        d.addCallback(lambda d: self.failIf(d != content))
        d.addCallback(lambda _: resource)
        return d

    def cleanUpCache(self):
        shutil.rmtree(self.cache_path, ignore_errors=True)
        os.makedirs(self.cache_path)

    def bp(self, result):
        import pdb
        print str(result)
        pdb.set_trace()
        return result


def delay(ret, t):
    d = defer.Deferred()
    reactor.callLater(t, d.callback, ret)
    return d
