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
implementation of a PB Server through which other components can request
to eat from or feed to this worker's components.
"""

from twisted.internet import reactor, defer, main
from twisted.cred import error
from twisted.python import components, failure, reflect
from twisted.spread import pb
from twisted.cred import portal

from flumotion.configure import configure
from flumotion.common import log, common, interfaces
from flumotion.twisted import checkers, compat, fdserver
from flumotion.twisted import portal as fportal
from flumotion.twisted import pb as fpb
from flumotion.twisted.defer import defer_generator_method

class FeedServer(log.Loggable):
    """
    I am the feed server. PHEAR
    """

    __implements__ = portal.IRealm

    logCategory = 'dispatcher'

    def __init__(self, brain, bouncer, portNum):
        """
        @param brain: L{flumotion.worker.worker.WorkerBrain}
        """
        self._brain = brain
        self._tport = None
        self.listen(bouncer, portNum)

    def getPortNum(self):
        if not self._tport:
            self.warning('not listening!')
            return 0
        return self._tport.getHost().port

    def listen(self, bouncer, portNum, unsafeTracebacks=0):
        portal = fportal.BouncerPortal(self, bouncer)
        factory = pb.PBServerFactory(portal,
                                     unsafeTracebacks=unsafeTracebacks)

        tport = reactor.listenWith(fdserver.PassableServerPort, portNum,
                                   factory)

        self._tport = tport
        self.debug('Listening for feed requests on TCP port %d',
                   self.getPortNum())

    def shutdown(self):
        d = self._tport.stopListening()
        self._tport = None
        return d

    ### IRealm method
    def requestAvatar(self, avatarId, keycard, mind, *ifaces):
        avatar = FeedAvatar(self, avatarId, mind)
        return (pb.IPerspective, avatar,
                lambda: self.avatarLogout(avatar))

    def avatarLogout(self, avatar):
        self.debug('feed avatar logged out: %s', avatar.avatarId)

    ## proxy these to the brain
    def feedToFD(self, componentId, feedId, fd, eaterId):
        return self._brain.feedToFD(componentId, feedId, fd, eaterId)

    def eatFromFD(self, componentId, feedId, fd):
        return self._brain.eatFromFD(componentId, feedId, fd)

class FeedAvatar(fpb.Avatar):
    """
    I am an avatar in a FeedServer for components that log in and request
    to eat from or feed to one of my components.

    My mind is a reference to a L{FeedMedium}
    """
    logCategory = "feedavatar"
    remoteLogName = "feedmedium"

    def __init__(self, feedServer, avatarId, mind):
        """
        """
        fpb.Avatar.__init__(self, avatarId)
        self._transport = None
        self.feedServer = feedServer
        self.avatarId = avatarId
        self.setMind(mind)

    def perspective_sendFeed(self, fullFeedId):
        """
        Called when the PB client wants us to send them the given feed.
        """
        # the PB message needs to be sent from the side that has the feeder
        # for proper switching, so we call back as a reply
        d = self.mindCallRemote('sendFeedReply', fullFeedId)
        d.addCallback(self._sendFeedReplyCb, fullFeedId)

    def _sendFeedReplyCb(self, result, fullFeedId):
        # compare with startStreaming in prototype
        # Remove this from the reactor; we mustn't read or write from it from
        # here on
        t = self.mind.broker.transport
        t.stopReading()
        t.stopWriting()

        # hand off the fd to the component
        self.debug("Attempting to send FD: %d" % t.fileno())
        
        (flowName, componentName, feedName) = common.parseFullFeedId(fullFeedId)
        componentId = common.componentId(flowName, componentName)

        if self.feedServer.feedToFD(componentId, feedName, t.fileno(),
                                    self.avatarId):
            t.keepSocketAlive = True

        # We removed the transport from the reactor before sending the FD; now
        # we want a complete and immediate cleanup of the socket, which 
        # loseConnection() doesn't do.
        t.connectionLost(failure.Failure(main.CONNECTION_DONE))

    # TODO: receiveFeed is bitrotten. Clean it up.
    def perspective_receiveFeed(self, componentId, feedId):
        """
        Called when the PB client wants to send the given feedId to the
        given component
        """
        # we need to make sure our result goes back, so only stop reading
        t = self.mind.broker.transport
        t.stopReading()
        reactor.callLater(0, self._doReceiveFeed, componentId, feedId)

    # FIXME: receiveFeed is broken and this method below will
    # probably leak fds.  Fix before using.
    def _doReceiveFeed(self, componentId, feedId):
        t = self.mind.broker.transport
        self.debug('flushing PB write queue')
        t.doWrite()
        self.debug('stop writing to transport')
        t.stopWriting()
        # this keeps a ref around, so the socket will not get closed
        self._transport = t
        self.mind.broker.transport = None

        # pass the fd to the component to eat from
        fd = t.fileno()
        self.debug('telling component %s to eat feedId %s from fd %d' % (
            componentId, feedId, fd))
        if not self.feedServer.eatFromFD(componentId, feedId, fd):
            self.debug("unsuccessful request to eatFromFD.")
