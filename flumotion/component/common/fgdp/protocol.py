# -*- Mode: Python -*-
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

import base64
from random import Random

from twisted.internet import reactor
from twisted.internet.protocol import ReconnectingClientFactory, Factory
from twisted.protocols.basic import LineReceiver

from Crypto.Hash import SHA

from flumotion.common import log

__version__ = "$Rev$"

PROTOCOL_NAME = "FGDP"


class ProtocolException(Exception):
    error = ''

    def __init__(self, reason=''):
        self.reason = reason

    def __str__(self):
        return "%s: %s" % (self.error, self.reason)


class UnexpectedResponse(ProtocolException):
    "Received an unexpected response, in a wrong state"
    error = "Unexpected response"


class UnexpectedCommand(ProtocolException):
    "Received an unexpected command, in a wrong state"
    error = "Unexpected command"


class MalformedCommand(ProtocolException):
    "The command is badly formed"
    error = "Malformed command"


class MalformedResponse(ProtocolException):
    "The response is badly formed"
    error = "Malformed response"


class InvalidVersion(ProtocolException):
    "The version of the protocol is not valid"
    error = "Invalid version"


class AuthenticationFailed(ProtocolException):
    "Authentication is not valid and failed"
    error = "Invalid authentication"


class ErrorResponse(ProtocolException):
    "Got an error response"
    error = "Received error response"


class Command(object):
    '''
    Command for the FGDP procotol, sent by the client to the server

    @type command: str
    @type content: content
    @type version: tuple
    '''

    def __init__(self, command, content, version):
        self.command = command
        self.content = content
        self.version = version

    @staticmethod
    def parseCommand(commandString, versionCheck=None):
        '''
        Parses a command string

        @param commandString: string with the command
        @type  commandString: str
        @param versionCheck: version number to check
        @type  versionCheck: tuple

        @return: A newly created L{Command}
        @rtype: L{Command}
        @raise MalformedCommand: raised when the command is not valid
        '''
        try:
            command, line = commandString.split(' ', 1)
            content, protoVersion = line.rsplit(' ', 1)
            protocol, versionStr = protoVersion.split('/')
            version = tuple(map(int, versionStr.split('.')))
        except ValueError:
            raise MalformedCommand(commandString)
        if protocol != PROTOCOL_NAME:
            raise MalformedCommand(commandString)
        if versionCheck and version != versionCheck:
            raise InvalidVersion('version %s is not compatible with %s ' %
                                 (version, versionCheck))
        return Command(command, content, version)

    def __str__(self):
        return "%s %s %s/%s" % (self.command, self.content, PROTOCOL_NAME,
                                '.'.join(map(str, self.version)))

    def __eq__(self, obj):
        if not isinstance(obj, Command):
            return False
        return (str(self) == str(obj))


class Response(object):
    '''
    Response for the FGDP protocol, sent by the server to the client

    @type command:  str
    @type content:  str
    @type version:  tuple
    '''

    def __init__(self, response, content, version):
        self.response = response
        self.content = content
        self.version = version

    @staticmethod
    def parseResponse(responseString, versionCheck=None):
        '''
        Parses a response string

        @param responseString: string with the response
        @type  responseString: str
        @param versionCheck: version number to check
        @type  versionCheck: tuple

        @return: A newly created L{Response}
        @rtype: L{Response}
        @raise MalformedResponse: raised when the command is not valid
        '''
        try:
            protoVersion, line = responseString.split(' ', 1)
            protocol, versionStr = protoVersion.split('/')
            version = tuple(map(int, versionStr.split('.')))
            response, content = line.split(' ', 1)
        except ValueError:
            raise MalformedResponse(responseString)
        if protocol != PROTOCOL_NAME:
            raise MalformedResponse(responseString)
        if versionCheck and version != versionCheck:
            raise InvalidVersion('version %s is not compatible with %s ' %
                                 (version, versionCheck))
        return Response(response, content, version)

    def __str__(self):
        return "%s/%s %s %s" % (PROTOCOL_NAME,
                                '.'.join(map(str, self.version)),
                                self.response, self.content)

    def __eq__(self, obj):
        if not isinstance(obj, Response):
            return False
        return (str(self) == str(obj))


class FGDP_0_1(object):
    '''
    Definitions for the version 0.1 of the FGDP protocol.
    Future extensions of the protocol should subclass this class.
    '''

    LOGIN_COMMAND = 'LOGIN'
    AUTH_COMMAND = 'AUTH'

    OK_RESPONSE = 'OK'
    ERROR_RESPONSE = 'ERROR'
    CHALLENGE_RESPONSE = 'CHALLENGE'


class FGDPBaseProtocol(LineReceiver, log.Loggable):
    """
    Base class for the twisted side of the FGDP protocol
    """

    _transport = None
    _gstElement = None
    _fd = None
    _user = ''
    _password = ''

    def __init__(self, gstElement):
        self._gstElement = gstElement
        self._gstElement.protocol = self

    def startProtocol(self):
        """
        Subclasses must implement this method to start the protocol after a
        new connection has been made
        """
        raise NotImplemented('Subclasses must implement "startProtocol"')

    def stopProtocol(self, reason):
        """
        Subclasses must implement this method to stop the protocol after the
        connection has been closed

        @type reason: L{twsited.python.failure.Failure}
        """
        raise NotImplemented('Subclasses must implement "stopProtocol"')

    def lineReceived(self, line):
        """
        Subclasess must implement this method to process the messages of the
        line-based protocol

        @type line: str
        """
        raise NotImplemented('Subclasses must implement "lineReceived"')

    def makeConnection(self, transport):
        """
        Store a reference of the trasport and file descriptor of the
        used by the new connection
        """
        self._transport = transport
        self._fd = transport.fileno()
        self.connectionMade()

    def connectionMade(self):
        self.info("Connection made with peer, starting protocol")
        self.startProtocol()

    def connectionLost(self, reason):
        self.info("Connection lost with FGDP peer: %s",
                  reason.getErrorMessage())
        self.stopProtocol(reason)

    def loseConnection(self):
        """
        Loses the current connection and triggers the stop of the protocol.
        Once the authentication has finished, the file descriptor is not
        handled anymore by the twisted reactor. A disconnection in the
        gstreamer element handling the file descriptor should call this method
        to notify the protocol about it.
        """
        if self._transport is not None:
            self._transport.loseConnection()

    def _makeHash(self, values):
        sha = SHA.new()
        sha.update(':'.join(values))
        return sha.hexdigest()

    def _sendMessage(self, message, transport=None):
        transport = transport or self._transport
        self.debug('Sending message: "%s"', message)
        transport.write("%s\r\n" % message)

    def _disconnectFD(self, reason):
        if self._fd != None:
            self._gstElement.disconnectFd(self._fd)
        self._gstElement.emit('disconnected', reason.getErrorMessage())

    def _delegateFD(self):
        # Take out the fd from twisted reactor and pass it to element
        # using it
        # See http://twistedmatrix.com/trac/ticket/1796
        reactor.removeReader(self._transport)
        self._gstElement.connectFd(self._fd)
        self._gstElement.emit('connected')


class FGDPServer_0_1(FGDP_0_1, FGDPBaseProtocol):
    '''
    Implementation of the server-side FGDP protocol for version 0.1
    '''

    logCategory = 'fgdp-server'

    SERVER_STATE_DISCONNECTED = "disconnected"
    SERVER_STATE_AUTHENTICATE = "authenticate"
    SERVER_STATE_CONNECTED = "connected"

    _state = SERVER_STATE_DISCONNECTED
    _version = (0, 1)
    _challenge = ''
    _random = None

    def __init__(self, gstElement):
        self._user = gstElement.username
        self._password = gstElement.password
        self._random = Random()
        FGDPBaseProtocol.__init__(self, gstElement)

    def makeConnection(self, transport):
        # The protocol must refuse new connections if a client is already
        # connected.
        self.factory.clients += 1
        if self.factory.clients > 1:
            r = Response(self.ERROR_RESPONSE, "already connected",
                           self._version)
            self._sendMessage(r, transport)
            self.warning("Trying to make a new connection, but a client "
                         "is already connected.")
            transport.loseConnection()
            return
        FGDPBaseProtocol.makeConnection(self, transport)

    def startProtocol(self):
        pass

    def stopProtocol(self, reason):
        self.info("Stopping protocol session")
        self.connected = 0
        self.factory.clients -= 1
        self._state = self.SERVER_STATE_DISCONNECTED
        self._disconnectFD(reason)

    def lineReceived(self, line):
        # Parse command and check state
        try:
            command = Command.parseCommand(line)
            self._checkState(command)
        except (ErrorResponse, MalformedCommand, UnexpectedCommand), e:
            self._handleError(e)
            return
        # State DISCONNECTED
        if self._state == self.SERVER_STATE_DISCONNECTED:
            self._user = command.content
            self._challengeClient()
        # State AUTHENTICATE
        elif self._state == self.SERVER_STATE_AUTHENTICATE:
            try:
                self._checkAuthentication(command)
            except AuthenticationFailed, e:
                self._handleError(e)
                return
            self._startStreaming()

    def _checkState(self, command):
        if self._state == self.SERVER_STATE_DISCONNECTED and \
                command.command != self.LOGIN_COMMAND:
            raise UnexpectedCommand(command.command)
        if self._state == self.SERVER_STATE_AUTHENTICATE and \
                command.command != self.AUTH_COMMAND:
            raise UnexpectedCommand(command.command)
        if self._state == self.SERVER_STATE_CONNECTED:
            # FIXME: Non fatal error
            raise UnexpectedCommand(command.command)

    def _handleError(self, error):
        self.warning("%s", error)
        response = Response(ErrorResponse, "Server error: %s" % error,
                            self._version)
        self._sendMessage(response)
        self.loseConnection()

    def _challengeClient(self):
        self.info("Challenging client")
        self._state = self.SERVER_STATE_AUTHENTICATE
        self._challenge = base64.b64encode(
                            str(self._random.getrandbits(1024)))
        response = Response(self.CHALLENGE_RESPONSE, self._challenge,
                            self._version)
        self._sendMessage(response)

    def _startStreaming(self):
        self._state = self.SERVER_STATE_CONNECTED
        response = Response(self.OK_RESPONSE, 'Authenticated', self._version)
        self._sendMessage(response)
        self.info("Started streaming")
        self._delegateFD()

    def _checkAuthentication(self, command):
        digest = self._makeHash([self._user, self._password, self._challenge])
        if digest != command.content:
            raise AuthenticationFailed(
                    "could not verify the challenge response")
        return False


class FGDPClient_0_1(FGDP_0_1, FGDPBaseProtocol):
    '''
    Implementation of the client-side FGDP protocol for version 0.1
    '''

    logCategory = 'fgdp-client'

    CLIENT_STATE_DISCONNECTED = "disconnected"
    CLIENT_STATE_LOGIN = "login"
    CLIENT_STATE_AUTHENTICATING = "authenticate"
    CLIENT_STATE_CONNECTED = "connected"

    _version = (0, 1)
    _state = CLIENT_STATE_DISCONNECTED

    def __init__(self, gstElement):
        self._user = gstElement.username
        self._password = gstElement.password
        FGDPBaseProtocol.__init__(self, gstElement)

    def startProtocol(self):
        self.info("Starting protocol session")
        self._login()

    def stopProtocol(self, reason):
        self.info('Stopping protocol session')
        self._state = self.CLIENT_STATE_DISCONNECTED
        self._disconnectFD(reason)

    def lineReceived(self, line):
        # Parse response and check state
        try:
            response = Response.parseResponse(line)
            self._checkState(response)
        except (MalformedResponse, ErrorResponse, UnexpectedResponse), e:
            self.warning("%s", e)
            self.loseConnection()
            return
        # State LOGIN
        if self._state == self.CLIENT_STATE_LOGIN:
            self._authenticate(response)
        # State AUTHENTICATING
        elif self._state == self.CLIENT_STATE_AUTHENTICATING:
            self._startStreaming()

    def _checkState(self, response):
        if response.response == self.ERROR_RESPONSE:
            raise ErrorResponse(response.content)
        if self._state == self.CLIENT_STATE_LOGIN and \
                response.response != self.CHALLENGE_RESPONSE:
            raise UnexpectedResponse(response.content)
        if self._state == self.CLIENT_STATE_AUTHENTICATING and \
                response.response != self.OK_RESPONSE:
            raise UnexpectedResponse(response.content)
        if self._state == self.CLIENT_STATE_CONNECTED:
            raise UnexpectedResponse(response.content)

    def _login(self):
        self.info('Starting client login with user=%s, password=%s',
                  self._user, self._password)
        self._state = self.CLIENT_STATE_LOGIN
        command = Command(self.LOGIN_COMMAND, self._user, self._version)
        self._sendMessage(command)

    def _authenticate(self, response):
        self.info('Authenticating user with challenge %s', response.content)
        self._state = self.CLIENT_STATE_AUTHENTICATING
        res = self._makeHash([self._user, self._password, response.content])
        command = Command(self.AUTH_COMMAND, res, self._version)
        self._sendMessage(command)

    def _startStreaming(self):
        self.info("Starting streaming")
        self._state = self.CLIENT_STATE_CONNECTED
        self._delegateFD()


class FGDPClientFactory(ReconnectingClientFactory, log.Loggable):
    logCategory = 'fgdp-client'

    _supportedVersions = ['0.1']

    def __init__(self, gstElement):
        ReconnectingClientFactory.maxDelay = gstElement.maxDelay
        self.gstElement = gstElement
        self._setProtocol(gstElement.version)

    def _setProtocol(self, version):
        if version in self._supportedVersions:
            classname = 'FGDPClient_%s' % version.replace('.', '_')
            self.protocol = globals()[classname]

    def buildProtocol(self, addr):
        p = self.protocol(self.gstElement)
        p.factory = self
        return p

    def retry(self, connector=None):
        self.info("Trying reconnection with FGDP peer")
        return ReconnectingClientFactory.retry(self, connector)


class FGDPServerFactory(Factory):

    clients = 0
    _supportedVersions = ['0.1']

    def __init__(self, gstElement):
        self.gstElement = gstElement
        self._setProtocol(gstElement.version)

    def _setProtocol(self, version):
        if version in self._supportedVersions:
            classname = 'FGDPServer_%s' % version.replace('.', '_')
            self.protocol = globals()[classname]

    def buildProtocol(self, addr):
        p = self.protocol(self.gstElement)
        p.factory = self
        return p
