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

from twisted.internet import reactor

from flumotion.common import log, common, interfaces
from flumotion.twisted import compat
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
        self._transports = {} # fullFeedId -> transport

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
        # store the transport so a ref to the socket is kept around. If we
        # get reconnected, this'll be overwritten, and the socket will be 
        # collected, and closed
        self._transports[fullFeedId] = t
        self.remote.broker.transport = None
        # pass the fd to the component to eat from
        fd = t.fileno()
        self.debug('telling component to eat from fd %d' % fd)
        (flowName, componentName, feedName) = common.parseFullFeedId(fullFeedId)
        self.component.eatFromFD(common.feedId(componentName, feedName), fd)

