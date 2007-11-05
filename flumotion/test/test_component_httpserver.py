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

from twisted.trial import unittest

import common

import os
import tempfile

from twisted.python import failure
from twisted.internet import defer
from twisted.web import client, error

from flumotion.common import log
from flumotion.component.misc.httpfile import httpfile

class MountTest(log.Loggable, unittest.TestCase):
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
        d.addCallback(lambda r: client.getPage(self.getURL('/B/C')))
        d.addCallback(lambda r: self.assertEquals(r, 'test file C'))
        # getting a non-existing resource should give web.error.Error
        d.addCallback(lambda r: client.getPage(self.getURL('/B/D')))
        d.addErrback(lambda f: f.trap(error.Error))
        return d

    def testDirMountRoot(self):
        properties = {
            u'mount-point': '/',
            u'path': self.path,
            u'port': 0,
        }
        self.makeComponent(properties)

        d = client.getPage(self.getURL('/A'))
        d.addCallback(lambda r: self.assertEquals(r, 'test file A'))
        d.addCallback(lambda r: client.getPage(self.getURL('/B/C')))
        d.addCallback(lambda r: self.assertEquals(r, 'test file C'))
        # getting a non-existing resource should give web.error.Error
        d.addCallback(lambda r: client.getPage(self.getURL('/B/D')))
        d.addErrback(lambda f: f.trap(error.Error))
        return d

    def testDirMountOnDemand(self):
        properties = {
            u'mount-point': '/ondemand',
            u'path': self.path,
            u'port': 0,
        }
        self.makeComponent(properties)

        d = client.getPage(self.getURL('/ondemand/A'))
        d.addCallback(lambda r: self.assertEquals(r, 'test file A'))
        d.addCallback(lambda r: client.getPage(self.getURL('/ondemand/B/C')))
        d.addCallback(lambda r: self.assertEquals(r, 'test file C'))
        # getting a non-existing resource should give web.error.Error
        d.addCallback(lambda r: client.getPage(self.getURL('/A')))
        d.addErrback(lambda f: f.trap(error.Error))
        d.addCallback(lambda r: client.getPage(self.getURL('/ondemand/B/D')))
        d.addErrback(lambda f: f.trap(error.Error))
        return d

    def testFileMountEmpty(self):
        properties = {
            u'mount-point': '',
            u'path': os.path.join(self.path, 'A'),
            u'port': 0,
        }
        self.makeComponent(properties)

        d = defer.Deferred()
        # FIXME: what if just the server URL is requested ?
        #d.addCallback(lambda r: client.getPage(self.getURL('')))
        #d.addCallback(lambda r: self.assertEquals(r, 'test file A'))
        d.addCallback(lambda r: client.getPage(self.getURL('/')))
        d.addCallback(lambda r: self.assertEquals(r, 'test file A'))
        # getting a non-existing resource should give web.error.Error
        d.addCallback(lambda r: client.getPage(self.getURL('/B/D')))
        d.addErrback(lambda f: f.trap(error.Error))
        d.callback(None)
        return d

    def testFileMountOnDemand(self):
        properties = {
            u'mount-point': '/ondemand',
            u'path': os.path.join(self.path, 'A'),
            u'port': 0,
        }
        self.makeComponent(properties)

        d = client.getPage(self.getURL('/ondemand'))
        d.addCallback(lambda r: self.assertEquals(r, 'test file A'))
        # getting a non-existing resource should give web.error.Error
        d.addCallback(lambda r: client.getPage(self.getURL('/A')))
        d.addErrback(lambda f: f.trap(error.Error))
        d.addCallback(lambda r: client.getPage(self.getURL('/ondemand/B/D')))
        d.addErrback(lambda f: f.trap(error.Error))
        return d

if __name__ == '__main__':
    unittest.main()
