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

from twisted.spread import pb

from flumotion.common import medium, log
from flumotion.twisted import credentials, defer, fdserver

import socket

# Very similar to tcp.Server, but we need to call things in a different order
class FDServer(Connection):
    def __init__(self, sock, protocol, additionalData):
        Connection.__init__(self, sock, protocol)
        
        # Inform the protocol we've made a connection, and then feed in the
        # extra data.
        protocol.makeConnection(self)
        protocol.dataReceived(additionalData)

        # Then add self to the reactor.
        self.startReading()
        self.connected = 1

    def getHost(self):
        return address.IPv4Address('TCP', *(self.socket.getsockname() + ('INET',)))

    def getPeer(self):
        return address.IPv4Address('TCP', *(self.socket.getpeername() + ('INET',)))

class FDPassingBroker(pb.Broker):
    def __init__(self, childFactory, **kwargs):
        pb.Broker.__init__(self, **kwargs)

        self.childFactory = childFactory

    # This is the complex bit. If our underlying transport receives a file
    # descriptor, this gets called - along with the data we got with the FD.
    # We create an appropriate protocol object, and attach it to the reactor.
    def fileDescriptorsReceived(self, fds, message):
        # TODO: Handle multiple FDs?
        if len(fds) == 1:
            fd = fds[0]
            print "Got fd ", fd
            # Note that we hardcode IPv4 here! 
            sock = socket.fromfd(fd, socket.AF_INET, socket.SOCK_STREAM)
            peeraddr = sock.getpeername()
           
            # Based on bits in tcp.Port.doRead()
            protocol = self.childFactory.buildProtocol(
                address._ServerFactoryIPv4Address('TCP', 
                     peeraddr[0], peeraddr[1]))

            FDServer(sock, protocol, message)
        else:
            print "Unexpected! len %d, message %s" % (len(fds), message)

class PorterMedium(medium.BaseMedium):
    """
    A medium we use to talk to the porter.
    Mostly, we use this to say what mountpoints (or perhaps, later, 
    (hostname, mountpoint) pairs?) we expect to receive requests for.
    """ 
    def registerPath(self, path):
        # TODO: Remote call to register this path
        pass

class PorterClientFactory(pb.PBClientFactory, log.Loggable):
    """
    A PB client factory that knows how to log into a Porter.
    Lives in streaming components, and accepts FDs passed over this connection.
    TODO: Augment docs.
    """
    def __init__(self, user, password, childFactory):
        """
        user and password used to log into the Porter.
        """
        pb.PBClientFactory.__init__(self)

        self.medium = PorterMedium()
        self.login(user, password)

        self.protocol = FDPassingBroker
        self.childFactory = childFactory

    def buildProtocol(self, addr):
        p = self.protocol(self.childFactory)
        p.factory = self
        return p

    def login(self, username, password):
        d = pb.PBClientFactory.login(self, 
            credentials.UsernamePassword(username, password), 
            self.medium)
        yield d

        try:
            remoteRef = d.value();
            self.medium.setRemoteReference(remoteRef)
        except Exception, e:
            self.error("Failed to log in to Porter: %s" % 
                log.getExceptionMessage(e))
    login = defer.defer_generator_method(login)

    def stopFactory(self):
        # Ideally, we'd already have logged out on shutdown. However, if the
        # porter gets stopped first, I think this gets called?
        self.medium.shutdown()

    def registerPath(self, path):
        self.medium.registerPath(path)
        
