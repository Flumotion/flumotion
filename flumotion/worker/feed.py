# -*- Mode: Python; test-case-name: flumotion.test.test_worker_feed -*-
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

"""
implementation of a PB Server through which other components can request
to eat from or feed to this worker's components.
"""

from twisted.internet import reactor, defer
from twisted.cred import error
from twisted.python import components, failure, reflect
from twisted.spread import pb
from twisted.cred import portal

from flumotion.configure import configure
from flumotion.common import log, common, interfaces
from flumotion.twisted import checkers, compat
from flumotion.twisted import portal as fportal
from flumotion.twisted import pb as fpb
from flumotion.twisted.defer import defer_generator_method

class ProxyManagerBouncer(log.Loggable):
    logCategory = "proxymanagerbouncer"
    # should be set as soon as we can ask the manager's bouncer
    keycardClasses = () 

    """
    I proxy authenticate calls to the manager's bouncer.
    """
    def __init__(self, remote):
        """
        @param remote: an object that has .callRemote()
        """
        self._remote = remote

    def getKeycardClasses(self):
        """
        Call me before asking me to authenticate, so I know what I can
        authenticate.
        """
        def getKeycardClassesCb(classes):
            self.keycardClasses = [reflect.namedObject(n) for n in classes]
            self.debug('set proxied keycardClasses to %r' % self.keycardClasses)
            return classes

        d = self._remote.callRemote('getKeycardClasses')
        d.addCallback(getKeycardClassesCb)
        return d

    def authenticate(self, keycard):
        self.debug("Authenticating keycard %r against manager" % keycard)
        return self._remote.callRemote('authenticate', None, keycard)

class ProxyManagerBouncerPortal(fportal.BouncerPortal):
    def getKeycardClasses(self):
        self.debug('proxy getting keycardclasses')
        d = self.bouncer.getKeycardClasses()
        return d

class FeedAvatar(pb.Avatar, log.Loggable):
    """
    I am an avatar in a FeedServer for components that log in and request
    to eat from or feed to one of my components.

    My mind is a reference to a L{FeedMedium}
    """
    logCategory = "feed-avatar"

    def __init__(self, feedServerParent):
        """
        @param feedServerParent: the parent of the feed server
        @type  feedServerParent: implementor of
                                  L{interfaces.IFeedServerParent}
        """
        self._transport = None
        self._feedServerParent = feedServerParent

    def attached(self, mind):
        self.debug("mind %s attached" % mind)
        self._mind = mind

    def detached(self):
        self.debug("mind %s detached" % self._mind)
        self._mind = None

    def perspective_sendFeed(self, fullFeedId):
        """
        Called when the PB client wants us to send them the given feed.
        """
        self.debug('remote --> FEEDSERVER: perspective_sendFeed(%s)' %
            fullFeedId)
        # the PB message needs to be sent from the side that has the feeder
        # for proper switching, so we call back as a reply
        self.debug('FEEDSERVER --> remote: callRemote(sendFeedReply, %s)' %
            fullFeedId)
        d = self._mind.callRemote('sendFeedReply', fullFeedId)
        d.addCallback(self._sendFeedReplyCb, fullFeedId)
        self.debug('remote <-- FEEDSERVER: perspective_sendFeed(%s): None' %
            fullFeedId)

    def _sendFeedReplyCb(self, result, fullFeedId):
        # compare with startStreaming in prototype
        self.debug(
            'FEEDSERVER <-- remote: callRemote(sendFeedReply, %s): %r' % (
                fullFeedId, result))
        t = self._mind.broker.transport
        t.stopReading()
        t.stopWriting()
        # this keeps a ref around, so the socket will not get closed
        self._transport = t
        self._mind.broker.transport = None

        # hand off the fd to the component
        self.debug("Attempting to send FD: %d" % t.fileno())
        
        (flowName, componentName, feedName) = common.parseFullFeedId(fullFeedId)
        self._feedServerParent.feedToFD(
            common.componentId(flowName, componentName), feedName, t.fileno())

    def perspective_receiveFeed(self, componentId, feedId):
        """
        Called when the PB client wants to send the given feedId to the
        given component
        """
        self.debug('remote --> FEEDSERVER: perspective_receiveFeed(%s, %s)' % (
            componentId, feedId))
        # we need to make sure our result goes back, so only stop reading
        t = self._mind.broker.transport
        t.stopReading()
        reactor.callLater(0, self._doReceiveFeed, componentId, feedId)

    def _doReceiveFeed(self, componentId, feedId):
        t = self._mind.broker.transport
        self.debug('flushing PB write queue')
        t.doWrite()
        self.debug('stop writing to transport')
        t.stopWriting()
        # this keeps a ref around, so the socket will not get closed
        self._transport = t
        self._mind.broker.transport = None

        # pass the fd to the component to eat from
        fd = t.fileno()
        self.debug('telling component %s to eat feedId %s from fd %d' % (
            componentId, feedId, fd))
        self._feedServerParent.eatFromFD(componentId, feedId, fd)

# an internal class; used by the worker to create avatars for Feed clients
class _WorkerFeedDispatcher(log.Loggable):
    """
    I implement L{portal.IRealm}.
    I make sure that when a L{pb.Avatar} is requested through me, the
    Avatar being returned knows about the mind (client) requesting
    the Avatar.
    """

    __implements__ = portal.IRealm

    logCategory = 'dispatcher'

    def __init__(self, brain):
        """
        @param brain: L{flumotion.worker.worker.WorkerBrain}
        """
        self._brain = brain

    ### IRealm methods

    # requestAvatar gets called through ClientFactory.login()
    # An optional second argument can be passed to login, which should be
    # a L{twisted.spread.flavours.Referenceable}
    # A L{twisted.spread.pb.RemoteReference} to it is passed to
    # requestAvatar as mind.

    # So in short, the mind is a reference to the client passed in login()
    # on the peer, allowing any object that has the mind to call back
    # to the piece that called login(),
    # which in our case is a component or an admin client.
    def requestAvatar(self, avatarId, keycard, mind, *ifaces):
        avatar = FeedAvatar(self._brain)
        # schedule a perspective attached for after this function
        # FIXME: there needs to be a way to not have to do a callLater
        # blindly so cleanup can be guaranteed
        reactor.callLater(0, avatar.attached, mind)

        return (pb.IPerspective, avatar, avatar.detached)

def feedServerFactory(brain, unsafeTracebacks=0):
        """
        Create and return an FPB server factory.

        @param brain: L{flumotion.worker.worker.WorkerBrain}
        """
        # create a Dispatcher which will hand out avatars to clients
        # connecting to me
        dispatcher = _WorkerFeedDispatcher(brain)

        # create a portal so that I can be connected to, through our dispatcher
        # implementing the IRealm and a bouncer
        # FIXME: decide if we allow anonymous login in this small (?) window
        bouncer = ProxyManagerBouncer(brain)
        portal = ProxyManagerBouncerPortal(dispatcher, bouncer)
        #unsafeTracebacks = 1 # for debugging tracebacks to clients
        factory = pb.PBServerFactory(portal, unsafeTracebacks=unsafeTracebacks)
        return factory

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
class FeedMedium(pb.Referenceable, log.Loggable):
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
    compat.implements(interfaces.IFeedMedium)

    remote = None

    def __init__(self, component):
        """
        @param component: the component this is a feed client for
        @type  component: L{flumotion.component.feedcomponent.FeedComponent}
        """
        self.component = component
        self._transports = {} # fullFeedId -> transport

    ### IMedium methods
    def setRemoteReference(self, remoteReference):
        self.remote = remoteReference

    def hasRemoteReference(self):
        return self.remote is not None

    def callRemote(self, name, *args, **kwargs):
        return self.remote.callRemote(name, args, kwargs)

    def remote_sendFeedReply(self, fullFeedId):
        self.debug('feedserver --> FEEDCLIENT: remote_sendFeedReply(%s)' %
            fullFeedId)
        t = self.remote.broker.transport
        # make sure we stop receiving PB messages
        self.debug('stop reading from transport')
        t.stopReading()
        reactor.callLater(0, self._doFeedTo, fullFeedId, t)
        self.debug('feedserver <-- FEEDCLIENT: remote_sendFeedReply(%s): None' %
            fullFeedId)

    def _doFeedTo(self, fullFeedId, t):
        self.debug('flushing PB write queue')
        t.doWrite()
        self.debug('stop writing to transport')
        t.stopWriting()
        # store the transport so a ref to the socket is kept around
        self._transports[fullFeedId] = t
        self.remote.broker.transport = None
        # pass the fd to the component to eat from
        fd = t.fileno()
        self.debug('telling component to eat from fd %d' % fd)
        (flowName, componentName, feedName) = common.parseFullFeedId(fullFeedId)
        self.component.eatFromFD(common.feedId(componentName, feedName), fd)
