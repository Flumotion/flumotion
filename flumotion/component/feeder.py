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

import time

import gst

from twisted.internet import reactor

from flumotion.common import componentui

__version__ = "$Rev$"


class Feeder:
    """
    This class groups feeder-related information as used by a Feed Component.

    @ivar feederName: name of the feeder
    @ivar uiState: the serializable UI State for this feeder
    """

    def __init__(self, feederName):
        self.feederName = feederName
        self.elementName = 'feeder:' + feederName
        self.payName = self.elementName + '-pay'
        self.uiState = componentui.WorkerComponentUIState()
        self.uiState.addKey('feederName')
        self.uiState.set('feederName', feederName)
        self.uiState.addListKey('clients')
        self._fdToClient = {} # fd -> (FeederClient, cleanupfunc)
        self._clients = {} # id -> FeederClient

    def __repr__(self):
        return ('<Feeder %s (%d client(s))>'
                % (self.feederName, len(self._clients)))

    def clientConnected(self, clientId, fd, cleanup):
        """
        The given client has connected on the given file descriptor, and is
        being added to multifdsink. This is called solely from the reactor
        thread.

        @param clientId: id of the client of the feeder
        @param fd:       file descriptor representing the client
        @param cleanup:  callable to be called when the given fd is removed
        """
        if clientId not in self._clients:
            # first time we see this client, create an object
            client = FeederClient(clientId)
            self._clients[clientId] = client
            self.uiState.append('clients', client.uiState)

        client = self._clients[clientId]
        self._fdToClient[fd] = (client, cleanup)

        client.connected(fd)

        return client

    def clientDisconnected(self, fd):
        """
        The client has been entirely removed from multifdsink, and we may
        now close its file descriptor.
        The client object stays around so we can track over multiple
        connections.

        Called from GStreamer threads.

        @type fd: file descriptor
        """
        (client, cleanup) = self._fdToClient.pop(fd)
        client.disconnected(fd=fd)

        # To avoid races between this thread (a GStreamer thread) closing the
        # FD, and the reactor thread reusing this FD, we only actually perform
        # the close in the reactor thread.
        reactor.callFromThread(cleanup, fd)

    def getClients(self):
        """
        @rtype: list of all L{FeederClient}s ever seen, including currently
                disconnected clients
        """
        return self._clients.values()


class FeederClient:
    """
    This class groups information related to the client of a feeder.
    The client is identified by an id.
    The information remains valid for the lifetime of the feeder, so it
    can track reconnects of the client.

    @ivar clientId: id of the client of the feeder
    @ivar fd:       file descriptor the client is currently using, or None.
    """

    def __init__(self, clientId):
        self.uiState = componentui.WorkerComponentUIState()
        self.uiState.addKey('client-id', clientId)
        self.fd = None
        self.uiState.addKey('fd', None)

        # these values can be set to None, which would mean
        # Unknown, not supported
        # these are supported
        for key in (
            'bytes-read-current', # bytes read over current connection
            'bytes-read-total',   # bytes read over all connections
            'reconnects',         # number of connections made by this client
            'last-connect',       # last client connection, in epoch seconds
            'last-disconnect',    # last client disconnect, in epoch seconds
            'last-activity',      # last time client read or connected
            ):
            self.uiState.addKey(key, 0)
        # these are possibly unsupported
        for key in (
            'buffers-dropped-current', # buffers dropped over current conn
            'buffers-dropped-total',   # buffers dropped over all connections
            ):
            self.uiState.addKey(key, None)

        # internal state allowing us to track global numbers
        self._buffersDroppedBefore = 0
        self._bytesReadBefore = 0

    def setStats(self, stats):
        """
        @type stats: list
        """
        bytesSent = stats[0]
        #timeAdded = stats[1]
        #timeRemoved = stats[2]
        #timeActive = stats[3]
        timeLastActivity = float(stats[4]) / gst.SECOND
        if len(stats) > 5:
            # added in gst-plugins-base 0.10.11
            buffersDropped = stats[5]
        else:
            # We don't know, but we cannot use None
            # since that would break integer addition below
            buffersDropped = 0

        self.uiState.set('bytes-read-current', bytesSent)
        self.uiState.set('buffers-dropped-current', buffersDropped)
        self.uiState.set('bytes-read-total', self._bytesReadBefore + bytesSent)
        self.uiState.set('last-activity', timeLastActivity)
        if buffersDropped is not None:
            self.uiState.set('buffers-dropped-total',
                self._buffersDroppedBefore + buffersDropped)

    def connected(self, fd, when=None):
        """
        The client has connected on this fd.
        Update related stats.

        Called only from the reactor thread.
        """
        if not when:
            when = time.time()

        if self.fd:
            # It's normal to receive a reconnection before we notice
            # that an old connection has been closed. Perform the
            # disconnection logic for the old FD if necessary. See #591.
            self._updateUIStateForDisconnect(self.fd, when)

        self.fd = fd
        self.uiState.set('fd', fd)
        self.uiState.set('last-connect', when)
        self.uiState.set('reconnects', self.uiState.get('reconnects', 0) + 1)

    def _updateUIStateForDisconnect(self, fd, when):
        if self.fd == fd:
            self.fd = None
            self.uiState.set('fd', None)
        self.uiState.set('last-disconnect', when)

        # update our internal counters and reset current counters to 0
        self._bytesReadBefore += self.uiState.get('bytes-read-current')
        self.uiState.set('bytes-read-current', 0)
        if self.uiState.get('buffers-dropped-current') is not None:
            self._buffersDroppedBefore += self.uiState.get(
                'buffers-dropped-current')
            self.uiState.set('buffers-dropped-current', 0)

    def disconnected(self, when=None, fd=None):
        """
        The client has disconnected.
        Update related stats.

        Called from GStreamer threads.
        """
        if self.fd != fd:
            # assume that connected() already called
            # _updateUIStateForDisconnect for us
            return

        if not when:
            when = time.time()

        reactor.callFromThread(self._updateUIStateForDisconnect, fd,
                               when)
