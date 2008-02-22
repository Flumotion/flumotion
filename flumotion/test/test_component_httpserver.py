# -*- Mode: Python; test-case-name: flumotion.test.test_component_httpserver -*-
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
from twisted.web import client, error
from twisted.web.resource import Resource
from twisted.web.static import Data

from flumotion.common import log
from flumotion.common import testsuite
from flumotion.component.misc.httpfile import httpfile
from flumotion.component.plugs.base import ComponentPlug

__version__ = "$Rev$"


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
        self.component = httpfile.HTTPFileStreamer(config)

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

PLUGTYPE = 'flumotion.component.plugs.lifecycle.ComponentLifecycle'

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
        self.component = httpfile.HTTPFileStreamer(config)

    def _getURL(self, path):
        # path should start with /
        return 'http://localhost:%d%s' % (self.component.port, path)

    def _localPlug(self, plugname):
        return {
            PLUGTYPE:
            [{'entries': {'default':{ 'module-name': 'flumotion.test.test_component_httpserver',
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
    testSetRootResourceMultiple.skip = "This is a bug in the httpfile api"

if __name__ == '__main__':
    unittest.main()
