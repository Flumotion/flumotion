# -*- Mode: Python -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# Flumotion - a streaming media server
# Copyright (C) 2004,2005,2006 Fluendo, S.L. (www.fluendo.com).
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

from twisted.internet.protocol import Protocol, Factory
from twisted.internet.tcp import Port, Connection
from twisted.internet import reactor, address
from twisted.cred import credentials

from twisted.spread import pb

from flumotion.common import medium, log
from flumotion.twisted import defer, fdserver
from flumotion.twisted import pb as fpb

import socket, os

# Very similar to tcp.Server, but we need to call things in a different order
class FDServer(Connection):
    """
    A connection class for use with passed FDs.
    Similar to tcp.Server, but gets the initial FD from a different source,
    obviously, and also passes along some data with the original connection.
    """
    def __init__(self, sock, protocol, additionalData):
        Connection.__init__(self, sock, protocol)
        
        # Inform the protocol we've made a connection.
        protocol.makeConnection(self)

        # Now, we want to feed in the extra data BEFORE the reactor reads 
        # anything additional from the socket. However, if we call this in
        # the other order, and the socket gets closed (or passed to something
        # non-twisted) after just the initial chunk, we'll be calling 
        # startReading() on something we've already stopped reading. That won't
        # work too well... Fortunately, the reactor runs in this thread, so
        # merely adding it (with startReading()) can't cause a read to happen
        # immediately.
        self.startReading()
        self.connected = 1

        protocol.dataReceived(additionalData)

    def getHost(self):
        return address.IPv4Address('TCP', *(self.socket.getsockname() + ('INET',)))

    def getPeer(self):
        return address.IPv4Address('TCP', *(self.socket.getpeername() + ('INET',)))

class FDPassingBroker(pb.Broker, log.Loggable):
    """
    A pb.Broker subclass that handles FDs being passed (with associated data)
    over the same connection as the normal PB data stream.
    When an FD is seen, it creates new protocol objects for them from the 
    childFactory attribute.
    """

    def __init__(self, childFactory, **kwargs):
        pb.Broker.__init__(self, **kwargs)

        self.childFactory = childFactory

    # This is the complex bit. If our underlying transport receives a file
    # descriptor, this gets called - along with the data we got with the FD.
    # We create an appropriate protocol object, and attach it to the reactor.
    def fileDescriptorsReceived(self, fds, message):
        if len(fds) == 1:
            fd = fds[0]

            # Note that we hardcode IPv4 here! 
            sock = socket.fromfd(fd, socket.AF_INET, socket.SOCK_STREAM)

            self.debug("Received FD %d->%d" % (fd, sock.fileno()))

            # Undocumentedly (other than a comment in 
            # Python/Modules/socketmodule.c), socket.fromfd() calls dup() on 
            # the passed FD before it actually wraps it in a socket object. 
            # So, we need to close the FD that we originally had...
            os.close(fd)

            peeraddr = sock.getpeername()
           
            # Based on bits in tcp.Port.doRead()
            protocol = self.childFactory.buildProtocol(
                address._ServerFactoryIPv4Address('TCP', 
                     peeraddr[0], peeraddr[1]))

            FDServer(sock, protocol, message)
        else:
            self.warning("Unexpected: FD-passing message with len(fds) != 1")

class PorterMedium(medium.BaseMedium):
    """
    A medium we use to talk to the porter.
    Mostly, we use this to say what mountpoints (or perhaps, later, 
    (hostname, mountpoint) pairs?) we expect to receive requests for.
    """ 
    def registerPath(self, path):
        return self.callRemote("registerPath", path)

    def deregisterPath(self, path):
        return self.callRemote("deregisterPath", path)

    def registerPrefix(self, prefix):
        return self.callRemote("registerPrefix", prefix)

    def deregisterPrefix(self, prefix):
        return self.callRemote("deregisterPrefix", prefix)
        
class PorterClientFactory(fpb.ReconnectingPBClientFactory):
    """
    A PB client factory that knows how to log into a Porter.
    Lives in streaming components, and accepts FDs passed over this connection.
    """

    def __init__(self, childFactory):
        """
        Create a PorterClientFactory that will use childFactory to create
        protocol instances for clients attached to the FDs received over this
        connection.
        """
        fpb.ReconnectingPBClientFactory.__init__(self)

        self.medium = PorterMedium()

        self.protocol = FDPassingBroker
        self._childFactory = childFactory

    def buildProtocol(self, addr):
        p = self.protocol(self._childFactory)
        p.factory = self
        return p

    def registerPath(self, path):
        return self.medium.registerPath(path)

    def deregisterPath(self, path):
        return self.medium.deregisterPath(path)

    def registerPrefix(self, prefix):
        return self.medium.registerPrefix(prefix)

    def deregisterPrefix(self, prefix):
        return self.medium.deregisterPrefix(prefix)

    def registerDefault(self):
        return self.medium.registerPrefix("/")

    def deregisterDefault(self):
        return self.medium.deregisterPrefix("/")
        
