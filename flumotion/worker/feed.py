# -*- Mode: Python; test-case-name: flumotion.test.test_worker_feed -*-
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

"""
implementation of a PB Client to interface with feedserver.py
"""

import os

from twisted.internet import reactor, main
from twisted.python import failure

from flumotion.common import log, common, interfaces
from flumotion.twisted import compat, fdserver
from flumotion.twisted import pb as fpb


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
    @ivar remote:       a reference to a L{FeedAvatar}
    @type remote:       L{twisted.spread.pb.RemoteReference}
    """
    logCategory = 'feedmedium'
    remoteLogName = 'feedserver'
    compat.implements(interfaces.IFeedMedium)

    remote = None

    def __init__(self, component):
        """
        @param component: the component this is a feed client for
        @type  component: L{flumotion.component.feedcomponent.FeedComponent}
        """
        self.component = component
        self.logName = component.name
        self._factory = None
        self._transports = {} # fullFeedId -> transport

    def startConnecting(self, host, port, authenticator, timeout=30,
                        bindAddress=None):
        """Optional helper method to connect to a remote feed server.

        This method starts a client factory connecting via a
        L{flumotion.twisted.fdserver.PassableClientConnector}. It offers
        the possibility of cancelling an in-progress connection via the
        stopConnecting() method.

        @param host: the remote host name
        @type host: str
        @param port: the tcp port on which to connect
        @param port int
        @param authenticator: the authenticator, normally provided by
        the worker
        @param authenticator: L{flumotion.twisted.pb.Authenticator}

        @returns: a deferred that will fire with the remote reference,
        once we have authenticated.
        """
        assert self._factory is None
        self._factory = FeedClientFactory(self)
        reactor.connectWith(fdserver.PassableClientConnector, host,
                            port, self._factory, timeout, bindAddress)
        return self._factory.login(authenticator)

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
        def mungeTransport(transport):
            # see fdserver.py, i am a bad bad man
            def _closeSocket():
                if transport.keepSocketAlive:
                    try:
                        transport.socket.close()
                    except socket.error:
                        pass
                else:
                    tcp.Server._closeSocket(self)
            transport._closeSocket = _closeSocket
            return transport
                        
        self.debug('flushing PB write queue')
        t.doWrite()
        self.debug('stop writing to transport')
        t.stopWriting()

        # make sure shutdown() is not called on the socket
        if not isinstance(t, fdserver._SocketMaybeCloser):
            t = mungeTransport(t)
        t.keepSocketAlive = True
        
        fd = os.dup(t.fileno())
        # Similar to feedserver._sendFeedReplyCb, but since we are in a
        # callLater, not doReadOrWrite, we call connectionLost directly
        # on the transport.
        t.connectionLost(failure.Failure(main.CONNECTION_DONE))

        self.debug('telling component to eat from fd %d' % fd)
        (flowName, componentName, feedName) = common.parseFullFeedId(fullFeedId)
        self.component.eatFromFD(common.feedId(componentName, feedName), fd)

