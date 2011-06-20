# -*- test-case-name: flumotion.test.test_component_common_gdp -*-
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

from twisted.python import failure

from flumotion.common import testsuite
from flumotion.component.common.fgdp import protocol
from flumotion.component.common.fgdp import fgdp

attr = testsuite.attr


class CommandTest(testsuite.TestCase):

    def testCommand(self):
        c = protocol.Command('TEST', 'test', (1, 0))
        self.assertEquals(c.command, 'TEST')
        self.assertEquals(c.content, 'test')
        self.assertEquals(c.version, (1, 0))
        self.assertEquals(str(c), 'TEST test FGDP/1.0')

    def testParseGoodCommand(self):
        c = protocol.Command.parseCommand('TEST test content FGDP/1.0')
        self.assertEquals(c.command, 'TEST')
        self.assertEquals(c.content, 'test content')
        self.assertEquals(c.version, (1, 0))
        self.assertEquals(str(c), 'TEST test content FGDP/1.0')

    def testParseBadCommand(self):
        self.failUnlessRaises(protocol.MalformedCommand,
                              protocol.Command.parseCommand,
                              'TEST testFGDP/1.0')
        self.failUnlessRaises(protocol.MalformedCommand,
                              protocol.Command.parseCommand,
                              'TESTtest FGDP/1.0')
        self.failUnlessRaises(protocol.MalformedCommand,
                              protocol.Command.parseCommand,
                              'TEST test FDP/1.0')
        self.failUnlessRaises(protocol.InvalidVersion,
                              protocol.Command.parseCommand,
                              'TEST test FGDP/1.1', (1, 0))


class ResponseTest(testsuite.TestCase):

    def testResonse(self):
        r = protocol.Response('TEST', 'test response', (1, 0))
        self.assertEquals(r.response, 'TEST')
        self.assertEquals(r.content, 'test response')
        self.assertEquals(r.version, (1, 0))
        self.assertEquals(str(r), 'FGDP/1.0 TEST test response')

    def testParseGoodResponse(self):
        r = protocol.Response.parseResponse('FGDP/1.0 TEST test response')
        self.assertEquals(r.response, 'TEST')
        self.assertEquals(r.content, 'test response')
        self.assertEquals(r.version, (1, 0))
        self.assertEquals(str(r), 'FGDP/1.0 TEST test response')

    def testParseBadResponse(self):
        self.failUnlessRaises(protocol.MalformedResponse,
                              protocol.Response.parseResponse,
                              'FGDP/1.0test TEST')
        self.failUnlessRaises(protocol.MalformedResponse,
                              protocol.Response.parseResponse,
                              'FGDP/1.0 TEST')
        self.failUnlessRaises(protocol.MalformedResponse,
                              protocol.Response.parseResponse,
                              'FDP/1.0 TEST test')
        self.failUnlessRaises(protocol.InvalidVersion,
                              protocol.Response.parseResponse,
                              'FGDP/1.1 TEST test', (1, 0))


class DummyTransport(object):
    lastWrite = ''
    protocol = None

    def write(self, write):
        self.lastWrite = write[:-2]

    def fileno(self):
        return 1

    def loseConnection(self):
        self.protocol.connectionLost(failure.Failure(""))
        pass


class DummyElement(fgdp.FGDPBase, fgdp.FDHandler):
    user = 'user'
    password = 'password'

    def __init__(self):
        fgdp.FDHandler.__init__(self, None)
        fgdp.FGDPBase.__init__(self)

    def connectFd(self, fd):
        pass

    def disconnectFd(self, fd):
        pass


class Client_0_1_Test(testsuite.TestCase):

    v = (0, 1)

    def setUp(self):
        self.transport = DummyTransport()
        self.element = DummyElement()
        self.client = protocol.FGDPClient_0_1(self.element)
        self.client._transport = self.transport
        self.client._transport.protocol = self.client

    def testFullProtocol(self):
        # The client starts the protocol
        self.client._state = protocol.FGDPClient_0_1.CLIENT_STATE_LOGIN
        # The server answer with a CHALLENGE response
        r = protocol.Response(protocol.FGDP_0_1.CHALLENGE_RESPONSE, '1',
                              self.v)
        self.client.lineReceived(str(r))
        # The client replies with an AUTH command
        h = self.client._makeHash([self.client._user,
                                   self.client._password, '1'])
        c = protocol.Command(protocol.FGDP_0_1.AUTH_COMMAND, h, self.v)
        self.assertTrue(self.transport.lastWrite, str(c))
        # The server answer with an OK response
        r = protocol.Response(protocol.FGDP_0_1.OK_RESPONSE, 'OK', self.v)
        self.client.lineReceived(str(r))
        self.assertEquals(self.client._state,
                          protocol.FGDPClient_0_1.CLIENT_STATE_CONNECTED)

    def testErrorResponse(self):
        # The client starts the protocol
        self.client._state = protocol.FGDPClient_0_1.CLIENT_STATE_LOGIN
        # The server answer with an Error response
        r = protocol.Response(protocol.FGDP_0_1.ERROR_RESPONSE,
                              'already connected', self.v)
        self.client.lineReceived(str(r))
        self.assertEquals(self.client._state,
                          protocol.FGDPClient_0_1.CLIENT_STATE_DISCONNECTED)

    def testMalformedResponse(self):
        # The client starts the protocol
        self.client._state = protocol.FGDPClient_0_1.CLIENT_STATE_LOGIN
        # The server asnwer with an invalid response
        self.client.lineReceived("HTTP/1.1 200 OK")
        self.assertEquals(self.client._state,
                          protocol.FGDPClient_0_1.CLIENT_STATE_DISCONNECTED)

    def testResponseInBadState(self):
        # The client starts the protocol
        self.client._state = protocol.FGDPClient_0_1.CLIENT_STATE_LOGIN
        # We received an OK response, but we were waiting for a challenge
        r = protocol.Response(protocol.FGDP_0_1.OK_RESPONSE, 'OK', self.v)
        self.client.lineReceived(str(r))
        self.assertEquals(self.client._state,
                          protocol.FGDPClient_0_1.CLIENT_STATE_DISCONNECTED)

    def testStates(self):
        self.client._state = protocol.FGDPClient_0_1.CLIENT_STATE_LOGIN
        r = protocol.Response(protocol.FGDP_0_1.OK_RESPONSE, 'OK', self.v)
        self.failUnlessRaises(protocol.UnexpectedResponse,
                              self.client._checkState, r)
        self.client._state = \
                protocol.FGDPClient_0_1.CLIENT_STATE_AUTHENTICATING
        r = protocol.Response(protocol.FGDP_0_1.CHALLENGE_RESPONSE, '', self.v)
        self.failUnlessRaises(protocol.UnexpectedResponse,
                              self.client._checkState, r)
        self.client._state = protocol.FGDPClient_0_1.CLIENT_STATE_CONNECTED
        r = protocol.Response(protocol.FGDP_0_1.CHALLENGE_RESPONSE, '', self.v)
        self.failUnlessRaises(protocol.UnexpectedResponse,
                              self.client._checkState, r)


class Server_0_1_Test(testsuite.TestCase):
    v = (0, 1)

    def setUp(self):
        self.transport = DummyTransport()
        self.element = DummyElement()
        factory = protocol.FGDPServerFactory(self.element)
        self.server = factory.buildProtocol('')
        self.server._transport = self.transport
        self.server._transport.protocol = self.server

    def testFullProtocol_0_1(self):
        # The client start the protocol with a LOGIN command
        c = protocol.Command(protocol.FGDP_0_1.LOGIN_COMMAND, 'user', self.v)
        self.server.lineReceived(str(c))
        # The server is now in the AUTHENTICATE state
        self.server._state = protocol.FGDPServer_0_1.SERVER_STATE_AUTHENTICATE
        # The server replies with a CHALLENGE response
        r = protocol.Response(protocol.FGDP_0_1.CHALLENGE_RESPONSE,
                              self.server._challenge, self.v)
        self.assertTrue(self.transport.lastWrite, str(r))
        # The client replies with an AUTH command
        h = self.server._makeHash([self.server._user,
                                   self.server._password,
                                   self.server._challenge])
        c = protocol.Command(protocol.FGDP_0_1.AUTH_COMMAND, h, self.v)
        self.server.lineReceived(str(c))
        # The server replies with an OK response
        r = protocol.Response(protocol.FGDP_0_1.OK_RESPONSE, 'OK', self.v)
        self.assertTrue(self.transport.lastWrite, str(r))
        self.assertEquals(self.server._state,
                          protocol.FGDPServer_0_1.SERVER_STATE_CONNECTED)

    def testMalformedCommand(self):
        # The client sends an invalid command
        self.server.lineReceived("GET / HTTP/1.1")
        self.assertEquals(self.server._state,
                          protocol.FGDPClient_0_1.CLIENT_STATE_DISCONNECTED)

    def testCommandInBadState(self):
        # We received an OK response, but we were waiting for a challenge
        c = protocol.Command(protocol.FGDP_0_1.AUTH_COMMAND, 'user', self.v)
        self.server.lineReceived(str(c))
        self.assertEquals(self.server._state,
                          protocol.FGDPClient_0_1.CLIENT_STATE_DISCONNECTED)

    def testStates(self):
        self.server._state = protocol.FGDPServer_0_1.SERVER_STATE_DISCONNECTED
        c = protocol.Command(protocol.FGDP_0_1.AUTH_COMMAND, 'user', self.v)
        self.failUnlessRaises(protocol.UnexpectedCommand,
                              self.server._checkState, c)
        self.server._state = protocol.FGDPServer_0_1.SERVER_STATE_AUTHENTICATE
        c = protocol.Command(protocol.FGDP_0_1.LOGIN_COMMAND, 'login', self.v)
        self.failUnlessRaises(protocol.UnexpectedCommand,
                              self.server._checkState, c)
        self.server._state = protocol.FGDPServer_0_1.SERVER_STATE_CONNECTED
        c = protocol.Command(protocol.FGDP_0_1.LOGIN_COMMAND, 'login', self.v)
        self.failUnlessRaises(protocol.UnexpectedCommand,
                              self.server._checkState, c)
