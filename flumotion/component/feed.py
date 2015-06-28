# -*- Mode: Python; test-case-name: flumotion.test.test_worker_feed -*-
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

"""
implementation of a PB Client to interface with feedserver.py
"""

import socket
import os

from twisted.internet import reactor, main, defer, tcp
from twisted.python import failure
from zope.interface import implements

from flumotion.common import log, common, interfaces
from flumotion.twisted import pb as fpb

__version__ = "$Rev$"


# copied from fdserver.py so that it can be bundled


class _SocketMaybeCloser(tcp._SocketCloser):
    keepSocketAlive = False

    def _closeSocket(self, orderly=False):
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
            args = []
            from twisted import version as v
            if (v.major, v.minor, v.micro) > (11, 0, 0):
                args.append(orderly)
            tcp.Server._closeSocket(self, *args)


class PassableClientConnection(_SocketMaybeCloser, tcp.Client):
    pass


class PassableClientConnector(tcp.Connector):
    # It is unfortunate, but it seems that either we override this
    # private-ish method or reimplement BaseConnector.connect(). This is
    # the path that tcp.py takes, so we take it too.

    def _makeTransport(self):
        return PassableClientConnection(self.host, self.port,
                                        self.bindAddress, self,
                                        self.reactor)


class FeedClientFactory(fpb.FPBClientFactory, log.Loggable):
    """
    I am a client factory used by a feed component's medium to log into
    a worker and exchange feeds.
    """
    logCategory = 'feedclient'
    perspectiveInterface = interfaces.IFeedMedium

    def __init__(self, medium):
        fpb.FPBClientFactory.__init__(self)
        self.medium = medium

# not a BaseMedium because we are going to do strange things to the transport


class FeedMedium(fpb.Referenceable):
    """
    I am a client for a Feed Server.

    I am used as the remote interface between a component and another
    component.

    @ivar component:   the component this is a feed client for
    @type component:   L{flumotion.component.feedcomponent.FeedComponent}
    @ivar remote:      a reference to a
                       L{flumotion.worker.feedserver.FeedAvatar}
    @type remote:      L{twisted.spread.pb.RemoteReference}
    """
    logCategory = 'feedmedium'
    remoteLogName = 'feedserver'
    implements(interfaces.IFeedMedium)

    remote = None

    def __init__(self, logName=None):
        if logName:
            assert isinstance(logName, str)
        self.logName = logName
        self._factory = None
        self._feedToDeferred = defer.Deferred()

    def startConnecting(self, host, port, authenticator, timeout=30,
                        bindAddress=None):
        """Optional helper method to connect to a remote feed server.

        This method starts a client factory connecting via a
        L{PassableClientConnector}. It offers the possibility of
        cancelling an in-progress connection via the stopConnecting()
        method.

        @param host:          the remote host name
        @type  host:          str
        @param port:          the tcp port on which to connect
        @param port           int
        @param authenticator: the authenticator, normally provided by
                              the worker
        @type  authenticator: L{flumotion.twisted.pb.Authenticator}

        @returns: a deferred that will fire with the remote reference,
                  once we have authenticated.
        """
        assert self._factory is None
        self._factory = FeedClientFactory(self)
        c = PassableClientConnector(host, port,
            self._factory, timeout, bindAddress, reactor=reactor)
        c.connect()
        return self._factory.login(authenticator)

    def requestFeed(self, host, port, authenticator, fullFeedId):
        """Request a feed from a remote feed server.

        This helper method calls startConnecting() to make the
        connection and authenticate, and will return the feed file
        descriptor or an error. A pending connection attempt can be
        cancelled via stopConnecting().

        @param host:          the remote host name
        @type  host:          str
        @param port:          the tcp port on which to connect
        @type  port:          int
        @param authenticator: the authenticator, normally provided by
                              the worker
        @type  authenticator: L{flumotion.twisted.pb.Authenticator}
        @param fullFeedId:    the full feed id (/flow/component:feed)
                              offered by the remote side
        @type  fullFeedId:    str

        @returns: a deferred that, if successful, will fire with a pair
                  (feedId, fd). In an error case it will errback and close the
                  remote connection.
        """

        def connected(remote):
            self.setRemoteReference(remote)
            return remote.callRemote('sendFeed', fullFeedId)

        def feedSent(res):
            # res is None
            # either just before or just after this, we received a
            # sendFeedReply call from the feedserver. so now we're
            # waiting on the component to get its fd
            return self._feedToDeferred

        def error(failure):
            self.warning('failed to retrieve %s from %s:%d', fullFeedId,
                         host, port)
            self.debug('failure: %s', log.getFailureMessage(failure))
            self.debug('closing connection')
            self.stopConnecting()
            return failure

        d = self.startConnecting(host, port, authenticator)
        d.addCallback(connected)
        d.addCallback(feedSent)
        d.addErrback(error)
        return d

    def sendFeed(self, host, port, authenticator, fullFeedId):
        """Send a feed to a remote feed server.

        This helper method calls startConnecting() to make the
        connection and authenticate, and will return the feed file
        descriptor or an error. A pending connection attempt can be
        cancelled via stopConnecting().

        @param host:          the remote host name
        @type  host:          str
        @param port:          the tcp port on which to connect
        @type  port:          int
        @param authenticator: the authenticator, normally provided by
                              the worker
        @type  authenticator: L{flumotion.twisted.pb.Authenticator}
        @param fullFeedId:    the full feed id (/flow/component:eaterAlias)
                              to feed to on the remote size
        @type  fullFeedId:    str

        @returns: a deferred that, if successful, will fire with a pair
                  (feedId, fd). In an error case it will errback and close the
                  remote connection.
        """

        def connected(remote):
            assert isinstance(remote.broker.transport, _SocketMaybeCloser)
            self.setRemoteReference(remote)
            return remote.callRemote('receiveFeed', fullFeedId)

        def feedSent(res):
            t = self.remote.broker.transport
            self.debug('stop reading from transport')
            t.stopReading()

            self.debug('flushing PB write queue')
            t.doWrite()
            self.debug('stop writing to transport')
            t.stopWriting()

            t.keepSocketAlive = True
            fd = os.dup(t.fileno())

            # avoid refcount cycles
            self.setRemoteReference(None)

            d = defer.Deferred()

            def loseConnection():
                t.connectionLost(failure.Failure(main.CONNECTION_DONE))
                d.callback((fullFeedId, fd))

            reactor.callLater(0, loseConnection)
            return d

        def error(failure):
            self.warning('failed to retrieve %s from %s:%d', fullFeedId,
                         host, port)
            self.debug('failure: %s', log.getFailureMessage(failure))
            self.debug('closing connection')
            self.stopConnecting()
            return failure

        d = self.startConnecting(host, port, authenticator)
        d.addCallback(connected)
        d.addCallback(feedSent)
        d.addErrback(error)
        return d

    def stopConnecting(self):
        """Stop a pending or established connection made via
        startConnecting().

        Stops any established or pending connection to a remote feed
        server started via the startConnecting() method. Safe to call
        even if connection has not been started.
        """
        if self._factory:
            self._factory.disconnect()
            self._factory = None
        # not sure if this is necessary; call it just in case, so we
        # don't leave a lingering reference cycle
        self.setRemoteReference(None)

    ### IMedium methods

    def setRemoteReference(self, remoteReference):
        self.remote = remoteReference

    def hasRemoteReference(self):
        return self.remote is not None

    def callRemote(self, name, *args, **kwargs):
        return self.remote.callRemote(name, args, kwargs)

    def remote_sendFeedReply(self, fullFeedId):
        t = self.remote.broker.transport
        # make sure we stop receiving PB messages
        self.debug('stop reading from transport')
        t.stopReading()
        reactor.callLater(0, self._doFeedTo, fullFeedId, t)

    def _doFeedTo(self, fullFeedId, t):
        self.debug('flushing PB write queue')
        t.doWrite()
        self.debug('stop writing to transport')
        t.stopWriting()

        # make sure shutdown() is not called on the socket
        t.keepSocketAlive = True

        fd = os.dup(t.fileno())
        # Similar to feedserver._sendFeedReplyCb, but since we are in a
        # callLater, not doReadOrWrite, we call connectionLost directly
        # on the transport.
        t.connectionLost(failure.Failure(main.CONNECTION_DONE))

        # This medium object is of no use any more; drop our reference
        # to the remote so we can avoid cycles.
        self.setRemoteReference(None)

        (flowName, componentName, feedName) = common.parseFullFeedId(
            fullFeedId)
        feedId = common.feedId(componentName, feedName)

        self.debug('firing deferred with feedId %s on fd %d', feedId,
                   fd)
        self._feedToDeferred.callback((feedId, fd))
