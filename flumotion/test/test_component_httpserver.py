# -*- test-case-name: flumotion.test.test_component_httpserver -*-
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

from twisted.internet import defer
from twisted.trial import unittest
from twisted.web import client, server, http, error
from twisted.web.resource import Resource
from twisted.web.static import Data

from flumotion.common import log
from flumotion.common import testsuite
from flumotion.component.misc.httpserver import httpfile, httpserver
from flumotion.component.misc.httpserver import localprovider
from flumotion.component.plugs.base import ComponentPlug
from flumotion.test import test_http


class MountTest(log.Loggable, testsuite.TestCase):

    def setUp(self):
        self.path = tempfile.mkdtemp(suffix=".flumotion.test")
        A = os.path.join(self.path, 'A')
        open(A, "w").write('test file A')
        B = os.path.join(self.path, 'B')
        os.mkdir(B)
        C = os.path.join(self.path, 'B', 'C')
        open(C, "w").write('test file C')
        self.component = None

    def tearDown(self):
        if self.component:
            self.component.stop()
        os.system('rm -r %s' % self.path)

    def makeComponent(self, properties):
        # start the component with the given properties
        config = {
            'feed': [],
            'name': 'http-server',
            'parent': 'default',
            'avatarId': '/default/http-server',
            'clock-master': None,
            'type': 'http-server',
            'plugs': {},
            'properties': properties,
        }
        self.component = httpserver.HTTPFileStreamer(config)

    def getURL(self, path):
        # path should start with /
        return 'http://localhost:%d%s' % (self.component.port, path)

    def testDirMountEmpty(self):
        properties = {
            u'mount-point': '',
            u'path': self.path,
            u'port': 0,
        }
        self.makeComponent(properties)

        d = client.getPage(self.getURL('/A'))
        d.addCallback(lambda r: self.assertEquals(r, 'test file A'))

        d2 = client.getPage(self.getURL('/B/C'))
        d2.addCallback(lambda r: self.assertEquals(r, 'test file C'))

        # getting a non-existing resource should give web.error.Error
        d3 = client.getPage(self.getURL('/B/D'))
        d3.addErrback(lambda f: f.trap(error.Error))
        return defer.DeferredList([d, d2, d3], fireOnOneErrback=True)

    def testDirMountRoot(self):
        properties = {
            u'mount-point': '/',
            u'path': self.path,
            u'port': 0,
        }
        self.makeComponent(properties)

        d = client.getPage(self.getURL('/A'))
        d.addCallback(lambda r: self.assertEquals(r, 'test file A'))

        d2 = client.getPage(self.getURL('/B/C'))
        d2.addCallback(lambda r: self.assertEquals(r, 'test file C'))

        # getting a non-existing resource should give web.error.Error
        d3 = client.getPage(self.getURL('/B/D'))
        d3.addErrback(lambda f: f.trap(error.Error))

        return defer.DeferredList([d, d2, d3], fireOnOneErrback=True)

    def testDirMountOnDemand(self):
        properties = {
            u'mount-point': '/ondemand',
            u'path': self.path,
            u'port': 0,
        }
        self.makeComponent(properties)

        d = client.getPage(self.getURL('/ondemand/A'))
        d.addCallback(lambda r: self.assertEquals(r, 'test file A'))
        d2 = client.getPage(self.getURL('/ondemand/B/C'))
        d2.addCallback(lambda r: self.assertEquals(r, 'test file C'))
        # getting a non-existing resource should give web.error.Error
        d3 = client.getPage(self.getURL('/A'))
        d3.addErrback(lambda f: f.trap(error.Error))
        d4 = client.getPage(self.getURL('/ondemand/B/D'))
        d4.addErrback(lambda f: f.trap(error.Error))

        return defer.DeferredList([d, d2, d3, d4], fireOnOneErrback=True)

    def testFileMountEmpty(self):
        properties = {
            u'mount-point': '',
            u'path': os.path.join(self.path, 'A'),
            u'port': 0,
        }
        self.makeComponent(properties)

        l = []
        d1 = client.getPage(self.getURL('/'))
        d1.addCallback(lambda r: self.assertEquals(r, 'test file A'))
        l.append(d1)

        # getting a non-existing resource should give web.error.Error
        d2 = client.getPage(self.getURL('/B/D'))
        d2.addErrback(lambda f: f.trap(error.Error))
        l.append(d2)

        # This is broken on twisted 2.0.1/2.2.0
        #d3 = client.getPage(self.getURL(''))
        #d3.addCallback(lambda r: self.assertEquals(r, 'test file A'))
        #l.append(d3)

        return defer.DeferredList(l, fireOnOneErrback=True)

    def testFileMountOnDemand(self):
        properties = {
            u'mount-point': '/ondemand',
            u'path': os.path.join(self.path, 'A'),
            u'port': 0,
        }
        self.makeComponent(properties)

        d1 = client.getPage(self.getURL('/ondemand'))
        d1.addCallback(lambda r: self.assertEquals(r, 'test file A'))
        # getting a non-existing resource should give web.error.Error
        d2 = client.getPage(self.getURL('/A'))
        d2.addErrback(lambda f: f.trap(error.Error))
        d3 = client.getPage(self.getURL('/ondemand/B/D'))
        d3.addErrback(lambda f: f.trap(error.Error))
        return defer.DeferredList([d1, d2, d3], fireOnOneErrback=True)


class _Resource(Resource):

    def __init__(self, path):
        Resource.__init__(self)
        self.putChild(path, Data("baz", "text/html"))


class SimpleTestPlug(ComponentPlug):

    def start(self, component):
        component.setRootResource(_Resource(path='foobar'))


class SimpleTestPlug2(ComponentPlug):

    def start(self, component):
        component.setRootResource(_Resource(path='noogie'))

PLUGTYPE = 'flumotion.component.plugs.base.ComponentPlug'


class PlugTest(testsuite.TestCase):

    def setUp(self):
        self.component = None

    def tearDown(self):
        if self.component:
            self.component.stop()

    def _makeComponent(self, properties, plugs):
        # start the component with the given properties
        config = {
            'feed': [],
            'name': 'http-server',
            'parent': 'default',
            'avatarId': '/default/http-server',
            'clock-master': None,
            'type': 'http-server',
            'plugs': plugs,
            'properties': properties,
        }
        self.component = httpserver.HTTPFileStreamer(config)

    def _getURL(self, path):
        # path should start with /
        return 'http://localhost:%d%s' % (self.component.port, path)

    def _localPlug(self, plugname):
        return {
            PLUGTYPE:
            [{'entries': {'default':{
            'module-name': 'flumotion.test.test_component_httpserver',
              'function-name': plugname,
              }}}]
            }

    def testSetRootResource(self):
        properties = {
            u'mount-point': '/mount',
            u'port': 0,
        }

        plugs = self._localPlug('SimpleTestPlug')
        self._makeComponent(properties, plugs)

        d = client.getPage(self._getURL('/mount/foobar'))
        d.addCallback(lambda r: self.assertEquals(r, 'baz'))
        return d

    def testSetRootResourceMultiple(self):
        properties = {
            u'mount-point': '/mount',
            u'port': 0,
        }

        plugs = self._localPlug('SimpleTestPlug')
        plugs2 = self._localPlug('SimpleTestPlug2')
        plugs[PLUGTYPE].extend(plugs2[PLUGTYPE])
        self._makeComponent(properties, plugs)

        d1 = client.getPage(self._getURL('/mount/foobar'))
        d1.addCallback(lambda r: self.assertEquals(r, 'baz'))

        d2 = client.getPage(self._getURL('/mount/noogie'))
        d2.addCallback(lambda r: self.assertEquals(r, 'baz'))

        return defer.DeferredList([d1, d2], fireOnOneErrback=True)
    testSetRootResourceMultiple.skip = "This is a bug in the httpserver api"


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

    def setResponseRange(self, first, last, size):
        pass

    def registerProducer(self, producer, streaming):
        self.producer = producer
        producer.resumeProducing()

    def unregisterProducer(self):
        pass

    def finish(self):
        self.finishDeferred.callback(None)


class FakeComponent:

    def __init__(self, path):
        plugProps = {"properties": {"path": path}}
        self._fileProviderPlug = localprovider.FileProviderLocalPlug(plugProps)

    def getRoot(self):
        return self._fileProviderPlug.getRootPath()

    def startAuthentication(self, request):
        return defer.succeed(None)


class TestTextFile(testsuite.TestCase):

    def setUp(self):
        fd, self.path = tempfile.mkstemp()
        os.write(fd, 'a text file')
        os.close(fd)
        self.component = FakeComponent(self.path)
        self.resource = httpfile.File(self.component.getRoot(), self.component)

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
        self.assertEquals(request.getHeader('content-type'),
            'application/octet-stream')

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


class TestDirectory(testsuite.TestCase):

    def setUp(self):
        self.path = tempfile.mkdtemp()
        h = open(os.path.join(self.path, 'test.flv'), 'w')
        h.write('a fake FLV file')
        h.close()
        self.component = FakeComponent(self.path)
        # a directory resource
        self.resource = httpfile.File(self.component.getRoot(), self.component,
            {'video/x-flv': httpfile.FLVFile})

    def tearDown(self):
        os.system('rm -r %s' % self.path)

    def testGetChild(self):
        fr = FakeRequest()
        r = self.resource.getChild('test.flv', fr)
        self.assertEquals(r.__class__, httpfile.FLVFile)

    def testFLV(self):
        fr = FakeRequest()
        self.assertEquals(self.resource.getChild('test.flv', fr).render(fr),
            server.NOT_DONE_YET)

        def finish(result):
            self.assertEquals(fr.getHeader('content-type'), 'video/x-flv')
            self.assertEquals(fr.data, 'a fake FLV file')
        fr.finishDeferred.addCallback(finish)

        return fr.finishDeferred

    def testFLVStart(self):
        fr = FakeRequest(args={'start': [2]})
        self.assertEquals(self.resource.getChild('test.flv', fr).render(fr),
            server.NOT_DONE_YET)

        def finish(result):
            self.assertEquals(fr.getHeader('content-type'), 'video/x-flv')
            expected = httpfile.FLVFile.header + 'fake FLV file'
            self.assertEquals(fr.data, expected)
            self.assertEquals(fr.getHeader('Content-Length'),
                str(len(expected)))
        fr.finishDeferred.addCallback(finish)

        return fr.finishDeferred

    def testFLVStartZero(self):
        fr = FakeRequest(args={'start': [0]})
        self.assertEquals(self.resource.getChild('test.flv', fr).render(fr),
            server.NOT_DONE_YET)

        def finish(result):
            self.assertEquals(fr.getHeader('content-type'), 'video/x-flv')
            self.assertEquals(fr.data, 'a fake FLV file')
        fr.finishDeferred.addCallback(finish)
        return fr.finishDeferred

    def testFLVRangeStart(self):
        # range should take precedence over start parameter
        fr = FakeRequest(headers={'range': 'bytes=7-'}, args={'start': [2]})
        self.assertEquals(self.resource.getChild('test.flv', fr).render(fr),
            server.NOT_DONE_YET)

        def finish(result):
            self.assertEquals(fr.getHeader('content-type'), 'video/x-flv')
            expected = 'FLV file'
            self.assertEquals(fr.data, expected)
            self.assertEquals(fr.getHeader('Content-Length'),
                str(len(expected)))
        fr.finishDeferred.addCallback(finish)
        return fr.finishDeferred


if __name__ == '__main__':
    unittest.main()
