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

import os
import random
import socket
import string
import time
from urllib2 import urlparse

from twisted.cred import portal
from twisted.internet import protocol, reactor, error, defer
from twisted.spread import pb
from zope.interface import implements

from flumotion.common import medium, log, messages, errors
from flumotion.common.i18n import N_, gettexter
from flumotion.component import component
from flumotion.component.component import moods
from flumotion.twisted import fdserver, checkers
from flumotion.twisted import reflect

__version__ = "$Rev$"
T_ = gettexter()


class PorterAvatar(pb.Avatar, log.Loggable):
    """
    An Avatar in the porter representing a streamer
    """

    def __init__(self, avatarId, porter, mind):
        self.avatarId = avatarId
        self.porter = porter

        # The underlying transport is now accessible as
        # self.mind.broker.transport, on which we can call sendFileDescriptor
        self.mind = mind

    def isAttached(self):
        return self.mind != None

    def logout(self):
        self.debug("porter client %s logging out", self.avatarId)
        self.mind = None

    def perspective_registerPath(self, path):
        self.log("Perspective called: registering path \"%s\"" % path)
        self.porter.registerPath(path, self)

    def perspective_deregisterPath(self, path):
        self.log("Perspective called: deregistering path \"%s\"" % path)
        self.porter.deregisterPath(path, self)

    def perspective_registerPrefix(self, prefix):
        self.log("Perspective called: registering default")
        self.porter.registerPrefix(prefix, self)

    def perspective_deregisterPrefix(self, prefix):
        self.log("Perspective called: deregistering default")
        self.porter.deregisterPrefix(prefix, self)

    def perspective_getPort(self):
        return self.porter._iptablesPort


class PorterRealm(log.Loggable):
    """
    A Realm within the Porter that creates Avatars for streamers logging into
    the porter.
    """
    implements(portal.IRealm)

    def __init__(self, porter):
        """
        @param porter: The porter that avatars created from here should use.
        @type  porter: L{Porter}
        """
        self.porter = porter

    def requestAvatar(self, avatarId, mind, *interfaces):
        self.log("Avatar requested for avatarId %s, mind %r, interfaces %r",
                 avatarId, mind, interfaces)
        if pb.IPerspective in interfaces:
            avatar = PorterAvatar(avatarId, self.porter, mind)
            return pb.IPerspective, avatar, avatar.logout
        else:
            raise NotImplementedError("no interface")


class PorterMedium(component.BaseComponentMedium):

    def remote_getPorterDetails(self):
        """
        Return the location, login username/password, and listening port
        and interface for the porter as a tuple (path, username,
        password, port, interface, external-interface).
        """
        return (self.comp._socketPath, self.comp._username,
                self.comp._password, self.comp._iptablesPort,
                self.comp._interface, self.comp._external_interface)


class Porter(component.BaseComponent, log.Loggable):
    """
    The porter optionally sits in front of a set of streamer components.
    The porter is what actually deals with incoming connections on a socket.
    It decides which streamer to direct the connection to, then passes the FD
    (along with some amount of already-read data) to the appropriate streamer.
    """

    componentMediumClass = PorterMedium

    def init(self):
        # We maintain a map of path -> avatar (the underlying transport is
        # accessible from the avatar, we need this for FD-passing)
        self._mappings = {}
        self._prefixes = {}

        self._socketlistener = None

        self._socketPath = None
        self._username = None
        self._password = None
        self._port = None
        self._iptablesPort = None
        self._porterProtocol = None

        self._interface = ''
        self._external_interface = ''

    def registerPath(self, path, avatar):
        """
        Register a path as being served by a streamer represented by this
        avatar. Will remove any previous registration at this path.

        @param path:   The path to register
        @type  path:   str
        @param avatar: The avatar representing the streamer to direct this path
                       to
        @type  avatar: L{PorterAvatar}
        """
        self.debug("Registering porter path \"%s\" to %r" % (path, avatar))
        if path in self._mappings:
            self.warning("Replacing existing mapping for path \"%s\"" % path)

        self._mappings[path] = avatar

    def deregisterPath(self, path, avatar):
        """
        Attempt to deregister the given path. A deregistration will only be
        accepted if the mapping is to the avatar passed.

        @param path:   The path to deregister
        @type  path:   str
        @param avatar: The avatar representing the streamer being deregistered
        @type  avatar: L{PorterAvatar}
        """
        if path in self._mappings:
            if self._mappings[path] == avatar:
                self.debug("Removing porter mapping for \"%s\"" % path)
                del self._mappings[path]
            else:
                self.warning(
                    "Mapping not removed: refers to a different avatar")
        else:
            self.warning("Mapping not removed: no mapping found")

    def registerPrefix(self, prefix, avatar):
        """
        Register a destination for all requests directed to anything beginning
        with a specified prefix. Where there are multiple matching prefixes,
        the longest is selected.

        @param avatar: The avatar being registered
        @type  avatar: L{PorterAvatar}
        """

        self.debug("Setting prefix \"%s\" for porter", prefix)
        if prefix in self._prefixes:
            self.warning("Overwriting prefix")

        self._prefixes[prefix] = avatar

    def deregisterPrefix(self, prefix, avatar):
        """
        Attempt to deregister a default destination for all requests not
        directed to a specifically-mapped path. This will only succeed if the
        default is currently equal to this avatar.

        @param avatar: The avatar being deregistered
        @type  avatar: L{PorterAvatar}
        """
        if prefix not in self._prefixes:
            self.warning("Mapping not removed: no mapping found")
            return

        if self._prefixes[prefix] == avatar:
            self.debug("Removing prefix destination from porter")
            del self._prefixes[prefix]
        else:
            self.warning(
                "Not removing prefix destination: expected avatar not found")

    def findPrefixMatch(self, path):
        found = None
        # TODO: Horribly inefficient. Replace with pathtree code.
        for prefix in self._prefixes.keys():
            self.log("Checking: %r, %r" % (prefix, path))
            if (path.startswith(prefix) and
                (not found or len(found) < len(prefix))):
                found = prefix
        if found:
            return self._prefixes[found]
        else:
            return None

    def findDestination(self, path):
        """
        Find a destination Avatar for this path.
        @returns: The Avatar for this mapping, or None.
        """

        if path in self._mappings:
            return self._mappings[path]
        else:
            return self.findPrefixMatch(path)

    def generateSocketPath(self):
        """
        Generate a socket pathname in an appropriate location
        """
        # Also see worker/worker.py:_getSocketPath(), and note that
        # this suffers from the same potential race.
        import tempfile
        fd, name = tempfile.mkstemp('.%d' % os.getpid(), 'flumotion.porter.')
        os.close(fd)

        return name

    def generateRandomString(self, numchars):
        """
        Generate a random US-ASCII string of length numchars
        """
        return ''.join(random.choice(string.ascii_letters)
                       for x in range(numchars))

    def have_properties(self):
        props = self.config['properties']

        self.fixRenamedProperties(props,
            [('socket_path', 'socket-path')])

        # We can operate in two modes: explicitly configured (neccesary if you
        # want to handle connections from components in other managers), and
        # self-configured (which is sufficient for slaving only streamers
        # within this manager
        if 'socket-path' in props:
            # Explicitly configured
            self._socketPath = props['socket-path']
            self._username = props['username']
            self._password = props['password']
        else:
            # Self-configuring. Use a randomly create username/password, and
            # a socket with a random name.
            self._username = self.generateRandomString(12)
            self._password = self.generateRandomString(12)
            self._socketPath = self.generateSocketPath()

        self._requirePassword = props.get('require-password', True)
        self._socketMode = props.get('socket-mode', 0666)
        self._port = int(props['port'])
        self._iptablesPort = int(props.get('iptables-port', self._port))
        self._porterProtocol = props.get('protocol',
            'flumotion.component.misc.porter.porter.HTTPPorterProtocol')
        self._interface = props.get('interface', '')
        # if a config has no external-interface set, set it to the same as
        # interface
        self._external_interface = props.get('external-interface',
            self._interface)

    def do_stop(self):
        d = None
        if self._socketlistener:
            # stopListening() calls (via a callLater) connectionLost(), which
            # will unlink our socket, so we don't need to explicitly delete it.
            d = self._socketlistener.stopListening()
        self._socketlistener = None
        return d

    def do_setup(self):
        # Create our combined PB-server/fd-passing channel
        self.have_properties()
        realm = PorterRealm(self)
        checker = checkers.FlexibleCredentialsChecker()
        checker.addUser(self._username, self._password)
        if not self._requirePassword:
            checker.allowPasswordless(True)

        p = portal.Portal(realm, [checker])
        serverfactory = pb.PBServerFactory(p)

        try:
            # Rather than a normal listenTCP() or listenUNIX(), we use
            # listenWith so that we can specify our particular Port, which
            # creates Transports that we know how to pass FDs over.
            try:
                os.unlink(self._socketPath)
            except OSError:
                pass

            self._socketlistener = reactor.listenWith(
                fdserver.FDPort, self._socketPath,
                serverfactory, mode=self._socketMode)
            self.info("Now listening on socketPath %s", self._socketPath)
        except error.CannotListenError:
            self.warning("Failed to create socket %s" % self._socketPath)
            m = messages.Error(T_(N_(
                "Network error: socket path %s is not available."),
                self._socketPath))
            self.addMessage(m)
            self.setMood(moods.sad)
            return defer.fail(errors.ComponentSetupHandledError())

        # Create the class that deals with the specific protocol we're proxying
        # in this porter.
        try:
            proto = reflect.namedAny(self._porterProtocol)
            self.debug("Created proto %r" % proto)
        except (ImportError, AttributeError):
            self.warning("Failed to import protocol '%s', defaulting to HTTP" %
                self._porterProtocol)
            proto = HTTPPorterProtocol

        # And of course we also want to listen for incoming requests in the
        # appropriate protocol (HTTP, RTSP, etc.)
        factory = PorterProtocolFactory(self, proto)
        try:
            reactor.listenWith(
                fdserver.PassableServerPort, self._port, factory,
                    interface=self._interface)
            self.info("Now listening on interface %r on port %d",
                      self._interface, self._port)
        except error.CannotListenError:
            self.warning("Failed to listen on interface %r on port %d",
                         self._interface, self._port)
            m = messages.Error(T_(N_(
                "Network error: TCP port %d is not available."), self._port))
            self.addMessage(m)
            self.setMood(moods.sad)
            return defer.fail(errors.ComponentSetupHandledError())


class PorterProtocolFactory(protocol.Factory):

    def __init__(self, porter, protocol):
        self._porter = porter
        self.protocol = protocol

    def buildProtocol(self, addr):
        p = self.protocol(self._porter)
        p.factory = self
        return p


class PorterProtocol(protocol.Protocol, log.Loggable):
    """
    The base porter is capable of accepting HTTP-like protocols (including
    RTSP) - it reads the first line of a request, and makes the decision
    solely on that.

    We can't guarantee that we read precisely a line, so the buffer we
    accumulate will actually be larger than what we actually parse.

    @cvar MAX_SIZE:   the maximum number of bytes allowed for the first line
    @cvar delimiters: a list of valid line delimiters I check for
    """

    logCategory = 'porterprotocol'

    # Don't permit a first line longer than this.
    MAX_SIZE = 4096

    # Timeout any client connected to the porter for longer than this. A normal
    # client should only ever be connected for a fraction of a second.
    PORTER_CLIENT_TIMEOUT = 30

    # In fact, because we check \r, we'll never need to check for \r\n - we
    # leave this in as \r\n is the more correct form. At the other end, this
    # gets processed by a full protocol implementation, so being flexible hurts
    # us not at all
    delimiters = ['\r\n', '\n', '\r']

    def __init__(self, porter):
        self._buffer = ''
        self._porter = porter
        self.requestId = None # a string that should identify the request

        self._timeoutDC = reactor.callLater(self.PORTER_CLIENT_TIMEOUT,
            self._timeout)

    def connectionMade(self):

        self.requestId = self.generateRequestId()
        # PROBE: accepted connection
        self.debug("[fd %5d] (ts %f) (request-id %r) accepted connection",
                   self.transport.fileno(), time.time(), self.requestId)

        protocol.Protocol.connectionMade(self)

    def _timeout(self):
        self._timeoutDC = None
        self.debug("Timing out porter client after %d seconds",
            self.PORTER_CLIENT_TIMEOUT)
        self.transport.loseConnection()

    def connectionLost(self, reason):
        if self._timeoutDC:
            self._timeoutDC.cancel()
            self._timeoutDC = None

    def dataReceived(self, data):
        self._buffer = self._buffer + data
        self.log("Got data, buffer now \"%s\"" % self._buffer)
        # We accept more than just '\r\n' (the true HTTP line end) in the
        # interests of compatibility.
        for delim in self.delimiters:
            try:
                line, remaining = self._buffer.split(delim, 1)
                break
            except ValueError:
                # We didn't find this delimiter; continue with the others.
                pass
        else:
            # Failed to find a valid delimiter.
            self.log("No valid delimiter found")
            if len(self._buffer) > self.MAX_SIZE:

                # PROBE: dropping
                self.debug("[fd %5d] (ts %f) (request-id %r) dropping, "
                           "buffer exceeded",
                           self.transport.fileno(), time.time(),
                           self.requestId)

                return self.transport.loseConnection()
            else:
                # No delimiter found; haven't reached the length limit yet.
                # Wait for more data.
                return

        # Got a line. self._buffer is still our entire buffer, should be
        # provided to the slaved process.
        parsed = self.parseLine(line)
        if not parsed:
            self.log("Couldn't parse the first line")
            return self.transport.loseConnection()

        identifier = self.extractIdentifier(parsed)
        if not identifier:
            self.log("Couldn't find identifier in first line")
            return self.transport.loseConnection()

        if self.requestId:
            self.log("Injecting request-id %r", self.requestId)
            parsed = self.injectRequestId(parsed, self.requestId)
            # Since injecting the token might have modified the parsed
            # representation of the request, we need to reconstruct the buffer.
            # Fortunately, we know what delimiter did we split on, what's the
            # remaining part and that we only split the buffer in two parts
            self._buffer = delim.join((self.unparseLine(parsed), remaining))

        # PROBE: request
        self.debug("[fd %5d] (ts %f) (request-id %r) identifier %s",
                   self.transport.fileno(), time.time(), self.requestId,
                   identifier)

        # Ok, we have an identifier. Is it one we know about, or do we have
        # a default destination?
        destinationAvatar = self._porter.findDestination(identifier)

        if not destinationAvatar or not destinationAvatar.isAttached():
            if destinationAvatar:
                self.debug("There was an avatar, but it logged out?")

            # PROBE: no destination; see send fd
            self.debug(
                "[fd %5d] (ts %f) (request-id %r) no destination avatar found",
                self.transport.fileno(), time.time(), self.requestId)

            self.writeNotFoundResponse()
            return self.transport.loseConnection()

        # Transfer control over this FD. Pass all the data so-far received
        # along in the same message. The receiver will push that data into
        # the Twisted Protocol object as if it had been normally received,
        # so it looks to the receiver like it has read the entire data stream
        # itself.

        # PROBE: send fd; see no destination and fdserver.py
        self.debug("[fd %5d] (ts %f) (request-id %r) send fd to avatarId %s",
                   self.transport.fileno(), time.time(), self.requestId,
                   destinationAvatar.avatarId)

        # TODO: Check out blocking characteristics of sendFileDescriptor, fix
        # if it blocks.
        try:
            destinationAvatar.mind.broker.transport.sendFileDescriptor(
                self.transport.fileno(), self._buffer)
        except OSError, e:
            self.warning("[fd %5d] failed to send FD: %s",
                         self.transport.fileno(), log.getExceptionMessage(e))
            self.writeServiceUnavailableResponse()
            return self.transport.loseConnection()

        # PROBE: sent fd; see no destination and fdserver.py
        self.debug("[fd %5d] (ts %f) (request-id %r) sent fd to avatarId %s",
                   self.transport.fileno(), time.time(), self.requestId,
                   destinationAvatar.avatarId)

        # After this, we don't want to do anything with the FD, other than
        # close our reference to it - but not close the actual TCP connection.
        # We set keepSocketAlive to make loseConnection() only call close()
        # rather than shutdown() then close()
        self.transport.keepSocketAlive = True
        self.transport.loseConnection()

    def parseLine(self, line):
        """
        Parse the initial line of the request. Return an object that can be
        used to uniquely identify the stream being requested by passing it to
        extractIdentifier, or None if the request is unreadable.

        Subclasses should override this.
        """
        raise NotImplementedError

    def unparseLine(self, parsed):
        """
        Recreate the initial request line from the parsed representation. The
        recreated line does not need to be exactly identical, but both
        parsedLine(unparseLine(line)) and line should contain the same
        information (i.e. unparseLine should not lose information).

        UnparseLine has to return a valid line from the porter protocol's
        scheme point of view (for instance, HTTP).

        Subclasses should override this.
        """
        raise NotImplementedError

    def extractIdentifier(self, parsed):
        """
        Extract a string that uniquely identifies the requested stream from the
        parsed representation of the first request line.

        Subclasses should override this, depending on how they implemented
        parseLine.
        """
        raise NotImplementedError

    def generateRequestId(self):
        """
        Return a string that will uniquely identify the request.

        Subclasses should override this if they want to use request-ids and
        also implement injectRequestId.
        """
        raise NotImplementedError

    def injectRequestId(self, parsed, requestId):
        """
        Take the parsed representation of the first request line and a string
        token, return a parsed representation of the request line with the
        request-id possibly mixed into it.

        Subclasses should override this if they generate request-ids.
        """
        # by default, ignore the request-id
        return parsed

    def writeNotFoundResponse(self):
        """
        Write a response indicating that the requested resource was not found
        in this protocol.

        Subclasses should override this to use the correct protocol.
        """
        raise NotImplementedError

    def writeServiceUnavailableResponse(self):
        """
        Write a response indicating that the requested resource was
        temporarily uavailable in this protocol.

        Subclasses should override this to use the correct protocol.
        """
        raise NotImplementedError


class HTTPPorterProtocol(PorterProtocol):
    scheme = 'http'
    protos = ["HTTP/1.0", "HTTP/1.1"]
    requestIdParameter = 'FLUREQID'
    requestIdBitsNo = 256

    def parseLine(self, line):
        try:
            (method, location, proto) = map(string.strip, line.split(' ', 2))

            if proto not in self.protos:
                return None

            # Currently, we just use the URL parsing code from urllib2
            parsed_url = urlparse.urlparse(location)

            return method, parsed_url, proto

        except ValueError:
            return None

    def unparseLine(self, parsed):
        method, parsed_url, proto = parsed
        return ' '.join((method, urlparse.urlunparse(parsed_url), proto))

    def generateRequestId(self):
        # Remember to return something that does not need quoting to be put in
        # a GET parameter. This way we spare ourselves the effort of quoting in
        # injectRequestId.
        return hex(random.getrandbits(self.requestIdBitsNo))[2:]

    def injectRequestId(self, parsed, requestId):
        method, parsed_url, proto = parsed
        # assuming no need to escape the requestId, see generateRequestId
        sep = ''
        if parsed_url[4] != '':
            sep = '&'
        query_string = ''.join((parsed_url[4],
                                sep, self.requestIdParameter, '=',
                                requestId))
        parsed_url = (parsed_url[:4] +
                      (query_string, )
                      + parsed_url[5:])
        return method, parsed_url, proto

    def extractIdentifier(self, parsed):
        method, parsed_url, proto = parsed
        # Currently, we just return the path part of the URL.
        return parsed_url[2]

    def writeNotFoundResponse(self):
        self.transport.write("HTTP/1.0 404 Not Found\r\n\r\nResource unknown")

    def writeServiceUnavailableResponse(self):
        self.transport.write("HTTP/1.0 503 Service Unavailable\r\n\r\n"
                             "Service temporarily unavailable")


class RTSPPorterProtocol(HTTPPorterProtocol):
    scheme = 'rtsp'
    protos = ["RTSP/1.0"]

    def writeNotFoundResponse(self):
        self.transport.write("RTSP/1.0 404 Not Found\r\n\r\nResource unknown")

    def writeServiceUnavailableResponse(self):
        self.transport.write("RTSP/1.0 503 Service Unavailable\r\n\r\n"
                             "Service temporarily unavailable")
