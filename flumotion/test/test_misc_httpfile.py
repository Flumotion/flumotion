# -*- Mode: Python; test-case-name: flumotion.test.test_misc_httpfile -*-
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
import tempfile

import common

from twisted.internet import defer
from twisted.trial import unittest
from twisted.web import server, resource, http

from flumotion.component.misc.httpfile import file

from flumotion.test import test_http

from twisted.web import http

       
# FIXME: maybe merge into test_http's fake request ?
class FakeRequest(test_http.FakeRequest):
    def __init__(self, **kwargs):
        test_http.FakeRequest.__init__(self, **kwargs)
        self.finishDeferred = defer.Deferred()

    def getHeader(self, field):
        try:
            return self.headers[field]
        except KeyError:
            return None
            
    def setLastModified(self, last):
        pass

    def registerProducer(self, producer, streaming):
        self.producer = producer
        producer.resumeProducing()
    def unregisterProducer(self):
        pass

    def finish(self):
        self.finishDeferred.callback(None)

class FakeComponent:
    def startAuthentication(self, request):
        return defer.succeed(None)

class TestTextFile(unittest.TestCase):
    def setUp(self):
        fd, self.path = tempfile.mkstemp()
        os.write(fd, 'a text file')
        os.close(fd)
        self.component = FakeComponent()
        self.resource = file.File(self.path, self.component)

    def tearDown(self):
        os.unlink(self.path)

    def finishCallback(self, result, request, response, data, length=None):
        if not length:
            length = len(data)
        if response:
            self.assertEquals(request.response, response)
        self.assertEquals(request.data, data)
        self.assertEquals(int(request.getHeader('Content-Length') or '0'),
            length)

    def finishPartialCallback(self, result, request, data, start, end):
        self.finishCallback(result, request, http.PARTIAL_CONTENT, data)
        self.assertEquals(request.getHeader('Content-Range'),
            "bytes %d-%d/%d" % (start, end, 11))

    def testFull(self):
        fr = FakeRequest()
        self.assertEquals(self.resource.render(fr), server.NOT_DONE_YET)
        # FIXME: why don't we get OK but -1 as response ?
        fr.finishDeferred.addCallback(self.finishCallback, fr,
            None, 'a text file')
        return fr.finishDeferred

    def testWrongRange(self):
        fr = FakeRequest(headers={'range': '2-5'})
        self.assertEquals(self.resource.render(fr), server.NOT_DONE_YET)
        fr.finishDeferred.addCallback(self.finishCallback, fr,
            http.REQUESTED_RANGE_NOT_SATISFIABLE, '')
        return fr.finishDeferred

    def testWrongEmptyBytesRange(self):
        fr = FakeRequest(headers={'range': 'bytes=-'})
        self.assertEquals(self.resource.render(fr), server.NOT_DONE_YET)
        fr.finishDeferred.addCallback(self.finishCallback, fr,
            http.REQUESTED_RANGE_NOT_SATISFIABLE, '')
        return fr.finishDeferred

    def testWrongNoRange(self):
        fr = FakeRequest(headers={'range': 'bytes=5'})
        self.assertEquals(self.resource.render(fr), server.NOT_DONE_YET)
        fr.finishDeferred.addCallback(self.finishCallback, fr,
            http.REQUESTED_RANGE_NOT_SATISFIABLE, '')
        return fr.finishDeferred

    def testWrongTypeRange(self):
        fr = FakeRequest(headers={'range': 'seconds=5-10'})
        self.assertEquals(self.resource.render(fr), server.NOT_DONE_YET)
        fr.finishDeferred.addCallback(self.finishCallback, fr,
            http.REQUESTED_RANGE_NOT_SATISFIABLE, '')
        return fr.finishDeferred

    def testRange(self):
        fr = FakeRequest(headers={'range': 'bytes=2-5'})
        self.assertEquals(self.resource.render(fr), server.NOT_DONE_YET)
        fr.finishDeferred.addCallback(self.finishPartialCallback, fr,
            'text', 2, 5)
        return fr.finishDeferred

    def testRangeSet(self):
        fr = FakeRequest(headers={'range': 'bytes=2-5,6-10'})
        self.assertEquals(self.resource.render(fr), server.NOT_DONE_YET)
        fr.finishDeferred.addCallback(self.finishPartialCallback, fr,
            'text', 2, 5)
        return fr.finishDeferred

    # FIXME: this test hangs
    def notestRangeTooBig(self):
        # a too big range just gets the whole file
        fr = FakeRequest(headers={'range': 'bytes=0-100'})
        self.assertEquals(self.resource.render(fr), server.NOT_DONE_YET)
        fr.finishDeferred.addCallback(self.finishCallback, fr,
            http.PARTIAL_CONTENT, 'a text file')
        return fr.finishDeferred

    def testRangeStart(self):
        fr = FakeRequest(headers={'range': 'bytes=7-'})
        self.assertEquals(self.resource.render(fr), server.NOT_DONE_YET)
        fr.finishDeferred.addCallback(self.finishPartialCallback, fr,
            'file', 7, 10)
        return fr.finishDeferred

    def testRangeSuffix(self):
        fr = FakeRequest(headers={'range': 'bytes=-4'})
        self.assertEquals(self.resource.render(fr), server.NOT_DONE_YET)
        fr.finishDeferred.addCallback(self.finishPartialCallback, fr,
            'file', 7, 10)
        return fr.finishDeferred

    def testRangeSuffixTooBig(self):
        fr = FakeRequest(headers={'range': 'bytes=-100'})
        self.assertEquals(self.resource.render(fr), server.NOT_DONE_YET)
        fr.finishDeferred.addCallback(self.finishPartialCallback, fr,
            'a text file', 0, 10)
        return fr.finishDeferred

    def testRangeHead(self):
        fr = FakeRequest(method='HEAD', headers={'range': 'bytes=2-5'})
        self.assertEquals(self.resource.render(fr), server.NOT_DONE_YET)
        fr.finishDeferred.addCallback(self.finishCallback, fr,
            http.PARTIAL_CONTENT, '', 4)
        return fr.finishDeferred

class TestDirectory(unittest.TestCase):
    def setUp(self):
        self.path = tempfile.mkdtemp()
        h = open(os.path.join(self.path, 'test.flv'), 'w')
        h.write('a fake FLV file')
        h.close()
        self.component = FakeComponent()
        # a directory resource
        self.resource = file.File(self.path, self.component,
            { 'video/x-flv': file.FLVFile } )

    def tearDown(self):
        os.system('rm -r %s' % self.path)

    def testGetChild(self):
        fr = FakeRequest()
        r = self.resource.getChild('test.flv', fr)
        self.assertEquals(r.__class__, file.FLVFile)

    def testFLV(self):
        fr = FakeRequest()
        self.assertEquals(self.resource.getChild('test.flv', fr).render(fr),
            server.NOT_DONE_YET)
        def finish(result):
            self.assertEquals(fr.data, 'a fake FLV file')
        fr.finishDeferred.addCallback(finish)

        return fr.finishDeferred

    def testFLVStart(self):
        fr = FakeRequest(args={'start': [2]})
        self.assertEquals(self.resource.getChild('test.flv', fr).render(fr),
            server.NOT_DONE_YET)
        def finish(result):
            self.assertEquals(fr.data, file.FLVFile.header + 'fake FLV file')
        fr.finishDeferred.addCallback(finish)

        return fr.finishDeferred
        
    def testFLVStartZero(self):
        fr = FakeRequest(args={'start': [0]})
        self.assertEquals(self.resource.getChild('test.flv', fr).render(fr),
            server.NOT_DONE_YET)
        def finish(result):
            self.assertEquals(fr.data, 'a fake FLV file')
        fr.finishDeferred.addCallback(finish)

        return fr.finishDeferred
