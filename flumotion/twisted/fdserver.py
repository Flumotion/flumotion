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
import struct
import time

__version__ = "$Rev$"


# Heavily based on
# http://twistedmatrix.com/trac/browser/sandbox/exarkun/copyover/server.py
# and client.py
# Thanks for the inspiration!

# Since we're doing this over a stream socket, our file descriptor messages
# aren't guaranteed to be received alone; they could arrive along with some
# unrelated data.
# So, we prefix the message with a 16 byte magic signature, and a length,
# and if we receive file descriptors decode based on this.
#
# map() instead of a string to workaround gettext encoding problems.
#
MAGIC_SIGNATURE = ''.join(map(chr, [253, 252, 142, 127, 7, 71, 185, 234,
                                    161, 117, 238, 216, 220, 54, 200, 163]))


class FDServer(unix.Server):

    def sendFileDescriptor(self, fileno, data=""):
        message = struct.pack("@16sI", MAGIC_SIGNATURE, len(data)) + data
        return fdpass.writefds(self.fileno(), [fileno], message)


class FDPort(unix.Port):
    transport = FDServer


class FDClient(unix.Client): #, log.Loggable):

    def doRead(self):
        if not self.connected:
            return
        try:
            (fds, message) = fdpass.readfds(self.fileno(), 64 * 1024)
        except OSError, e:
            if e.errno in (errno.EWOULDBLOCK, errno.EAGAIN):
                return
            else:
                return main.CONNECTION_LOST
        else:
            if not message:
                return main.CONNECTION_DONE

            if len(fds) > 0:
                # Look for our magic cookie in (possibly) the midst of other
                # data. Pass surrounding chunks, if any, onto dataReceived(),
                # which (undocumentedly) must return None unless a failure
                # occurred.
                # Pass the actual FDs and their message to
                # fileDescriptorsReceived()
                offset = message.find(MAGIC_SIGNATURE)
                if offset < 0:
                    # Old servers did not send this; be hopeful that this
                    # doesn't have bits of other protocol (i.e. PB) mixed up
                    # in it.
                    return self.protocol.fileDescriptorsReceived(fds, message)
                elif offset > 0:
                    ret = self.protocol.dataReceived(message[0:offset])
                    if ret:
                        return ret

                msglen = struct.unpack("@I", message[offset+16:offset+20])[0]
                offset += 20
                ret = self.protocol.fileDescriptorsReceived(fds,
                    message[offset:offset+msglen])
                if ret:
                    return ret

                if offset+msglen < len(message):
                    return self.protocol.dataReceived(message[offset+msglen:])
                return ret
            else:
              #  self.debug("No FDs, passing to dataReceived")
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
        @param connectionClass: subclass of L{twisted.internet.tcp.Connection}
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

            # PROBE: received fd; see porter.py
            self.debug("[fd %5d] (ts %f) received fd from %d, created socket",
                       sock.fileno(), time.time(), fd)

            # Undocumentedly (other than a comment in
            # Python/Modules/socketmodule.c), socket.fromfd() calls dup() on
            # the passed FD before it actually wraps it in a socket object.
            # So, we need to close the FD that we originally had...
            os.close(fd)

            try:
                peeraddr = sock.getpeername()
            except socket.error:
                self.info("Socket disconnected before being passed to client")
                sock.close()
                return

            # Based on bits in tcp.Port.doRead()
            addr = address._ServerFactoryIPv4Address('TCP',
                peeraddr[0], peeraddr[1])
            protocol = self.childFactory.buildProtocol(addr)

            self._connectionClass(sock, protocol, peeraddr, message)
        else:
            self.warning("Unexpected: FD-passing message with len(fds) != 1")


class _SocketMaybeCloser(tcp._SocketCloser):
    keepSocketAlive = False

    def _closeSocket(self):
        # We override this (from tcp._SocketCloser) so that we can close
        # sockets properly in the normal case, but once we've passed our
        # socket on via the FD-channel, we just close() it (not calling
        # shutdown() which will close the TCP channel without closing
        # the FD itself)
        if self.keepSocketAlive:
            try:
                self.socket.close()
            except socket.error:
                pass
        else:
            tcp.Server._closeSocket(self)


class PassableServerConnection(_SocketMaybeCloser, tcp.Server):
    """
    A subclass of tcp.Server that permits passing the FDs used to other
    processes (by just calling close(2) rather than shutdown(2) on them)
    """
    pass


class PassableServerPort(tcp.Port):
    transport = PassableServerConnection
