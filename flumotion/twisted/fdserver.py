# -*- Mode: Python -*-
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

from flumotion.common import log
from flumotion.extern.fdpass import fdpass

from twisted.internet import unix, main, address, tcp
from twisted.spread import pb

import errno
import os
import socket

# Heavily based on 
# http://twistedmatrix.com/trac/browser/sandbox/exarkun/copyover/server.py
# and client.py
# Thanks for the inspiration!

class FDServer(unix.Server):
    def sendFileDescriptor(self, fileno, data="\0"):
        return fdpass.writefds(self.fileno(), [fileno], data)

class FDPort(unix.Port):
    transport = FDServer

class FDClient(unix.Client):
    def doRead(self):
        if not self.connected:
            return
        try:
            (fds, message) = fdpass.readfds(self.fileno(), 64 * 1024)
        except socket.error, se:
            if se.args[0] == errno.EWOULDBLOCK:
                return
            else:
                return main.CONNECTION_LOST
        else:
            if not message:
                return main.CONNECTION_DONE

            if len(fds) > 0:
                return self.protocol.fileDescriptorsReceived(fds, message)
            else:
                return self.protocol.dataReceived(message)

class FDConnector(unix.Connector):
    def _makeTransport(self):
        return FDClient(self.address, self, self.reactor)

class FDPassingBroker(pb.Broker, log.Loggable):
    """
    A pb.Broker subclass that handles FDs being passed to it (with associated
    data) over the same connection as the normal PB data stream.
    When an FD is seen, it creates new protocol objects for them from the 
    childFactory attribute.
    """
    # FIXME: looks like we can only use our own subclasses that take
    # three __init__ args
    def __init__(self, childFactory, connectionClass, **kwargs):
        """
        @param connectionClass: a subclass of L{twisted.internet.tcp.Connection}
        """
        pb.Broker.__init__(self, **kwargs)

        self.childFactory = childFactory
        self._connectionClass = connectionClass

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

            self._connectionClass(sock, protocol, message)
        else:
            self.warning("Unexpected: FD-passing message with len(fds) != 1")

class PassableServerConnection(tcp.Server):
    """
    A subclass of tcp.Server that permits passing the FDs used to other 
    processes (by just calling close(2) rather than shutdown(2) on them)
    """

    def __init__(self, sock, protocol, client, server, sessionno):
        tcp.Server.__init__(self, sock, protocol, client, server, sessionno)
        self.keepSocketAlive = False

    def _closeSocket(self):
        # We override this (from tcp._SocketCloser) so that we can close sockets
        # properly in the normal case, but once we've passed our socket on via
        # the FD-channel, we just close() it (not calling shutdown() which will
        # close the TCP channel without closing the FD itself)
        if self.keepSocketAlive:
            try:
                self.socket.close()
            except socket.error:
                pass
        else:
            tcp.Server._closeSocket(self)

class PassableServerPort(tcp.Port):
    transport = PassableServerConnection
