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

from twisted.internet.protocol import Protocol, Factory
from twisted.internet.tcp import Port, Connection
from twisted.internet import reactor, address
from twisted.cred import credentials

from flumotion.common import medium, log
from flumotion.twisted import defer, fdserver
from flumotion.twisted import pb as fpb

import socket

__version__ = "$Rev$"


# Very similar to tcp.Server, but we need to call things in a different order
class FDPorterServer(Connection):
    """
    A connection class for use with passed FDs.
    Similar to tcp.Server, but gets the initial FD from a different source,
    obviously, and also passes along some data with the original connection.
    """
    def __init__(self, sock, protocol, addr, additionalData):
        Connection.__init__(self, sock, protocol)
        self.client = addr

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
        return address.IPv4Address('TCP', *(
            self.socket.getsockname() + ('INET', )))

    def getPeer(self):
        return address.IPv4Address('TCP', *(self.client + ('INET', )))

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

        self.protocol = fdserver.FDPassingBroker
        self._childFactory = childFactory

    def buildProtocol(self, addr):
        p = self.protocol(self._childFactory, FDPorterServer)
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

class HTTPPorterClientFactory(PorterClientFactory):
    def __init__(self, childFactory, mountPoints, do_start_deferred,
                 prefixes=None):
        """
        @param mountPoints: a list of mountPoint strings that should be
                            registered to the porter
        """
        PorterClientFactory.__init__(self, childFactory)
        self._mountPoints = mountPoints
        self._prefixes = prefixes or []
        self._do_start_deferred = do_start_deferred

    def _fireDeferred(self, r):
        # If we still have the deferred, fire it (this happens after we've
        # completed log in the _first_ time, not subsequent times)
        if self._do_start_deferred:
            self.debug("Firing initial deferred: should indicate "
                       "that login is complete")
            self._do_start_deferred.callback(None)
            self._do_start_deferred = None

    def gotDeferredLogin(self, deferred):
        # This is called when we start logging in to give us the deferred for
        # the login process. Once we're logged in, we want to set our
        # remote ref, then register our path with the porter, then (possibly)
        # fire a different deferred
        self.debug("Got deferred login, adding callbacks")
        deferred.addCallback(self.medium.setRemoteReference)
        for mount in self._mountPoints:
            self.debug("Registering mount point %s with porter", mount)
            deferred.addCallback(lambda r, m: self.registerPath(m),
                mount)
        for mount in self._prefixes:
            self.debug("Registering mount prefix %s with porter", mount)
            deferred.addCallback(lambda r, m: self.registerPrefix(m),
                mount)
        deferred.addCallback(self._fireDeferred)
