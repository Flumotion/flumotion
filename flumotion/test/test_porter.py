# -*- Mode: Python; test-case-name: flumotion.test.test_porter -*-
# vi:si:et:sw=4:sts=4:ts=4

# Flumotion - a streaming media server
# Copyright (C) 2004,2005,2006,2007,2008,2009 Fluendo, S.L.
# Copyright (C) 2010,2011 Flumotion Services, S.A.
# All rights reserved.
#
# This file may be distributed and/or modified under the terms of
# the GNU Lesser General Public License version 2.1 as published by
# the Free Software Foundation.
# This file is distributed without any warranty; without even the implied
# warranty of merchantability or fitness for a particular purpose.
# See "LICENSE.LGPL" in the source distribution for more information.
#
# Headers in this file shall remain intact.

import cgi
import errno
import string
from urllib2 import urlparse

from flumotion.common import testsuite
from flumotion.component.misc.porter import porter


class FakeTransport:
    connected = True
    _fileno = 5

    def __init__(self, protocol, overloaded=False):
        self.written = ''
        self.protocol = protocol
        self.overloaded = overloaded

    def loseConnection(self):
        self.connected = False
        self.protocol.connectionLost(None)

    def sendFileDescriptor(self, fd, data):
        if self.overloaded:
            raise OSError(errno.EAGAIN, 'Resource temporarily unavailable')

    def write(self, data):
        self.written += data

    def fileno(self):
        return self._fileno


class FakePorter:
    foundDestination = False

    def findDestination(self, path):
        self.foundDestination = True
        if path == '/existing':
            return FakeAvatar(overloaded=False)
        elif path == '/overloaded':
            return FakeAvatar(overloaded=True)

        return None


class FakeBroker:

    def __init__(self, overloaded=False):
        self.transport = FakeTransport(self, overloaded)


class FakeMind:

    def __init__(self, overloaded=False):
        self.broker = FakeBroker(overloaded)


class FakeAvatar:
    avatarId = 'testAvatar'

    def __init__(self, overloaded=False):
        self.mind = FakeMind(overloaded)

    def isAttached(self):
        return True


class TestPorterProtocol(testsuite.TestCase):

    def setUp(self):
        self.p = FakePorter()
        self.pp = porter.HTTPPorterProtocol(self.p)
        self.t = FakeTransport(self.pp)
        self.pp.transport = self.t
        self.failUnless(self.t.connected)
        self.failIf(self.p.foundDestination)

    def testNoIdentifier(self):
        self.pp.dataReceived('first ')
        self.failUnless(self.t.connected)
        self.pp.dataReceived('line\n')
        self.failIf(self.t.connected)

    def testBreakDelimiter(self):
        self.pp.dataReceived('first line')
        self.failUnless(self.t.connected)
        self.pp.dataReceived('\r')
        self.pp.dataReceived('\n')
        self.failIf(self.t.connected)


class TestHTTPPorterProtocol(testsuite.TestCase):

    def setUp(self):
        self.p = FakePorter()
        self.pp = porter.HTTPPorterProtocol(self.p)
        self.t = FakeTransport(self.pp)
        self.pp.transport = self.t
        self.failUnless(self.t.connected)
        self.failIf(self.p.foundDestination)

    def testWrongLocation(self):
        self.pp.dataReceived('GET ')
        self.failUnless(self.t.connected)
        self.pp.dataReceived('http://localhost ')
        self.pp.dataReceived('HTTP/1.1\r\n')
        self.failIf(self.t.connected)
        self.failIf(self.p.foundDestination)

    def testRightLocationNotFound(self):
        self.pp.dataReceived('GET ')
        self.failUnless(self.t.connected)
        self.pp.dataReceived('http://localhost:8800/notfound ')
        self.pp.dataReceived('HTTP/1.1\r\n')
        self.failIf(self.t.connected)
        self.failUnless(self.p.foundDestination)
        self.failUnless(self.t.written)
        self.failIf(self.t.written.find('404') < 0)

    def testRightLocationFound(self):
        self.pp.dataReceived('GET ')
        self.failUnless(self.t.connected)
        self.pp.dataReceived('http://localhost:8800/existing ')
        self.pp.dataReceived('HTTP/1.1\r\n')
        self.failIf(self.t.connected)
        self.failUnless(self.p.foundDestination)
        self.failIf(self.t.written)

    def testErrorSendingFileDescriptors(self):
        self.pp.dataReceived('GET ')
        self.failUnless(self.t.connected)
        self.pp.dataReceived('http://localhost:8800/overloaded ')
        self.pp.dataReceived('HTTP/1.1\r\n')
        self.failIf(self.t.connected)
        self.failUnless(self.p.foundDestination)
        self.failUnless(self.t.written)
        self.failIf(self.t.written.find('503') < 0)


class TestHTTPPorterProtocolParser(testsuite.TestCase):

    def setUp(self):
        self.p = FakePorter()
        self.pp = porter.HTTPPorterProtocol(self.p)
        self.t = FakeTransport(self.pp)
        self.pp.transport = self.t
        self.param = self.pp.requestIdParameter

    def tearDown(self):
        self.t.loseConnection()

    def containsSameInfo(self, line, line2, extra={}):
        """
        Check if two HTTP request lines contain the same info.

        We define lines as containing same info, when they have the same
        scheme, protocol, path and the same query parameters and values.

        The extra argument should be a dictionary, that will be used to extend
        the parsed query parameters of the first line.
        """

        scheme, url, protocol = map(string.strip, line.split(' ', 2))
        scheme2, url2, protocol2 = map(string.strip, line2.split(' ', 2))
        if '?' in url:
            path, qs = url.split('?', 1)
        else:
            path, qs = url, ''
        if '?' in url2:
            path2, qs2 = url2.split('?', 1)
        else:
            path2, qs2 = url2, ''
        args = cgi.parse_qs(qs, True)
        args.update(extra)
        args2 = cgi.parse_qs(qs2, True)

        self.assertEquals(scheme, scheme2)
        self.assertEquals(protocol, protocol2)
        self.assertEquals(path, path2)
        self.assertEquals(args, args2)

    def testWrongLine(self):
        parsed = self.pp.parseLine('GET /test HTTP/666.0\r\n')
        self.assertIdentical(parsed, None)

    def testSimpleParse(self):
        parsed = self.pp.parseLine('GET /test HTTP/1.0\r\n')
        identifier = self.pp.extractIdentifier(parsed)
        self.assertEquals(identifier, '/test')

        parsed = self.pp.parseLine('GET /test HTTP/1.1\n')
        identifier = self.pp.extractIdentifier(parsed)
        self.assertEquals(identifier, '/test')

        parsed = self.pp.parseLine('GET / HTTP/1.0\r\n')
        identifier = self.pp.extractIdentifier(parsed)
        self.assertEquals(identifier, '/')

    def testParseWithHost(self):
        parsed = self.pp.parseLine(
            'GET http://some.server.somewhere/test HTTP/1.1\n')
        identifier = self.pp.extractIdentifier(parsed)
        self.assertEquals(identifier, '/test')

        parsed = self.pp.parseLine(
            'GET http://some.server.somewhere:1234/ HTTP/1.1\n')
        identifier = self.pp.extractIdentifier(parsed)
        self.assertEquals(identifier, '/')

    def testParseWithParams(self):
        parsed = self.pp.parseLine(
            'GET http://some.server.somewhere:1234/test?'
            'arg1=val1&arg2=val2 HTTP/1.1\n')
        identifier = self.pp.extractIdentifier(parsed)
        self.assertEquals(identifier, '/test')

        parsed = self.pp.parseLine(
            'GET /test?arg1=val1&arg2=val2 HTTP/1.1\n')
        identifier = self.pp.extractIdentifier(parsed)
        self.assertEquals(identifier, '/test')

        parsed = self.pp.parseLine(
            'GET /?arg1=val1&arg2=val2 HTTP/1.1\n')
        identifier = self.pp.extractIdentifier(parsed)
        self.assertEquals(identifier, '/')

    def testUnparse(self):
        lines = ['GET http://some.server.somewhere:1234/'
                 'test?arg1=val1&arg2=val2 HTTP/1.1\n',
                 'GET /?arg1=val1&arg2=val2 HTTP/1.0\n',
                 'GET /test/test2 HTTP/1.1\n',
                 'GET /test/test2?arg1=&arg2=val2 HTTP/1.1\n']

        for line in lines:
            parsed = self.pp.parseLine(line)
            unparsed = self.pp.unparseLine(parsed)
            self.containsSameInfo(line, unparsed)

    def testInjectRequestId(self):
        lines = ['GET http://some.server.somewhere:1234/'
                 'test?arg1=val1&arg2=val2 HTTP/1.1\n',
                 'GET /?arg1=val1&arg2=val2 HTTP/1.0\n',
                 'GET /test/test2 HTTP/1.1\n']

        for line in lines:
            parsed = self.pp.parseLine(line)
            injected = self.pp.injectRequestId(parsed, 'ID')
            unparsed = self.pp.unparseLine(injected)
            self.containsSameInfo(line, unparsed,
                                  {self.pp.requestIdParameter: ['ID']})
