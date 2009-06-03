# -*- Mode: Python; test-case-name: flumotion.test.test_porter -*-
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

from flumotion.common import testsuite
from flumotion.component.misc.porter import porter


class FakeTransport:
    connected = True
    _fileno = 5

    def __init__(self, protocol):
        self.written = ''
        self.protocol = protocol

    def loseConnection(self):
        self.connected = False
        self.protocol.connectionLost(None)

    def sendFileDescriptor(self, fd, data):
        pass

    def write(self, data):
        self.written += data

    def fileno(self):
        return self._fileno


class FakePorter:
    foundDestination = False

    def findDestination(self, path):
        self.foundDestination = True
        if path == '/existing':
            return FakeAvatar()

        return None


class FakeBroker:

    def __init__(self):
        self.transport = FakeTransport(self)


class FakeMind:

    def __init__(self):
        self.broker = FakeBroker()


class FakeAvatar:
    avatarId = 'testAvatar'

    def __init__(self):
        self.mind = FakeMind()

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


class TestHTTPPorterProtocolParser(testsuite.TestCase):

    def setUp(self):
        self.p = FakePorter()
        self.pp = porter.HTTPPorterProtocol(self.p)
        self.t = FakeTransport(self.pp)
        self.pp.transport = self.t

    def tearDown(self):
        self.t.loseConnection()

    def testSimpleParse(self):
        result = self.pp.parseLine('GET /test HTTP/1.0\r\n')
        self.assertEquals(result, '/test')

        result = self.pp.parseLine('GET /test HTTP/1.1\n')
        self.assertEquals(result, '/test')

        result = self.pp.parseLine('GET / HTTP/1.0\r\n')
        self.assertEquals(result, '/')

    def testParseWithHost(self):
        result = self.pp.parseLine(
            'GET http://some.server.somewhere/test HTTP/1.1\n')
        self.assertEquals(result, '/test')

        result = self.pp.parseLine(
            'GET http://some.server.somewhere:1234/ HTTP/1.1\n')
        self.assertEquals(result, '/')

    def testParseWithParams(self):
        result = self.pp.parseLine(
            'GET http://some.server.somewhere:1234/test?'
            'arg1=val1&arg2=val2 HTTP/1.1\n')
        self.assertEquals(result, '/test')

        result = self.pp.parseLine(
            'GET /test?arg1=val1&arg2=val2 HTTP/1.1\n')
        self.assertEquals(result, '/test')

        result = self.pp.parseLine(
            'GET /?arg1=val1&arg2=val2 HTTP/1.1\n')
        self.assertEquals(result, '/')
