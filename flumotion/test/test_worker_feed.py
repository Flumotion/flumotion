# -*- Mode: Python; test-case-name:flumotion.test.test_worker_worker -*-
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


import common

import errno
import os

from twisted.trial import unittest
from twisted.internet import reactor, defer

from flumotion.twisted import pb as fpb
from flumotion.common import log
from flumotion.component.bouncers import htpasswdcrypt

from flumotion.worker import feed, feedserver


class FakeWorkerBrain(log.Loggable):
    _deferredFD = None

    def waitForFD(self):
        if self._deferredFD is None:
            self._deferredFD = defer.Deferred()
        return self._deferredFD

    def feedToFD(self, componentId, feedName, fd, eaterId):
        self.info('feed to fd: %s %s %d %s', componentId, feedName, fd, eaterId)
        self.waitForFD().callback((componentId, feedName, fd, eaterId))
        # need to return True for server to keep fd open
        return True

    def eatFromFD(self, componentId, feedId, fd):
        self.info('eat from fd: %s %d %s', feedId, fd)
        return True
   
class FakeComponent(log.Loggable):
    def __init__(self, name='test'):
        self.name = name
        self._deferredFD = None
    
    def waitForFD(self):
        if self._deferredFD is None:
            self._deferredFD = defer.Deferred()
        return self._deferredFD

    def eatFromFD(self, feedId, fd):
        self.info('eat from fd: %s %d', feedId, fd)
        self.waitForFD().callback((feedId, fd))

def countOpenFileDescriptors():
    import resource
    soft, hard = resource.getrlimit(resource.RLIMIT_NOFILE)
    n = 0
    for fd in range(soft):
        try:
            os.fstat(fd)
            n += 1
        except OSError, e:
            if e.errno != errno.EBADF:
                n += 1
        except Exception:
            pass
    return n

# subclass feedserver so that we can test some avatar logout details
class FeedServer(feedserver.FeedServer):
    _deferredAvatarLogout = None

    def waitForAvatarExit(self):
        if self._deferredAvatarLogout is None:
            self._deferredAvatarLogout = defer.Deferred()
        return self._deferredAvatarLogout

    def avatarLogout(self, avatar):
        feedserver.FeedServer.avatarLogout(self, avatar)
        # callback in a callLater so that we can make sure the fd is
        # closed
        reactor.callLater(0, self.waitForAvatarExit().callback, None)

class TestFeedServer(unittest.TestCase, log.Loggable):
    bouncerconf = {'name': 'testbouncer',
                   'plugs': {},
                   # user:test
                   'properties': {'data': "user:qi1Lftt0GZC0o"}}

    def setUp(self):
        self._fdCount = countOpenFileDescriptors()

        self.brain = FakeWorkerBrain()
        self._bouncer = bouncer = htpasswdcrypt.HTPasswdCrypt()
        bouncer.setup(self.bouncerconf)
        self.feedServer = FeedServer(self.brain, bouncer, 0)
        self.assertAdditionalFDsOpen(1, 'setUp (socket)')

    def assertAdditionalFDsOpen(self, additionalFDs=0, debug=''):
        actual = countOpenFileDescriptors()
        self.assertEqual(self._fdCount + additionalFDs, actual,
                         debug + (' (%d + %d != %d)'
                                  % (self._fdCount, additionalFDs, actual)))

    def tearDown(self):
        d = self.feedServer.shutdown()
        d.addCallback(lambda _: self._bouncer.stop())
        d.addCallback(lambda _: self.assertAdditionalFDsOpen(0, 'tearDown'))
        return d
        
    def testConnectWithoutDroppingPB(self):
        component = FakeComponent()
        client = feed.FeedMedium(component)
        factory = feed.FeedClientFactory(client)

        def login():
            port = self.feedServer.getPortNum()
            self.assertAdditionalFDsOpen(1, 'connect (socket)')
            reactor.connectTCP('localhost', port, factory)
            self.assertAdditionalFDsOpen(2, 'connect (socket, client)')
            return factory.login(fpb.Authenticator(username='user',
                                                   password='test'))

        def cleanup(res):
            self.assertAdditionalFDsOpen(3, 'cleanup (socket, client, server)')
            factory.disconnect()

            # disconnect calls loseConnection() on the transport, which
            # can return a deferred. In the case of TCP sockets it does
            # this, actually disconnecting from a callLater, so we can't
            # assert on the open FD's at this point
            # self.assertAdditionalFDsOpen(2, 'cleanup (socket, server)')

            # have to drop into the reactor to wait for this one
            return self.feedServer.waitForAvatarExit()

        def checkfds(res):
            self.assertAdditionalFDsOpen(1, 'cleanup (socket)')
            
        d = login()
        d.addCallback(cleanup)
        d.addCallback(checkfds)
        return d

    def testConnectAndFeedLegacy(self):
        # this is a legacy test, to see if existing (25 april)
        # components connecting with normal tcp transports still works.
        component = FakeComponent()
        client = feed.FeedMedium(component)
        factory = feed.FeedClientFactory(client)

        def login():
            port = self.feedServer.getPortNum()
            self.assertAdditionalFDsOpen(1, 'connect (socket)')
            reactor.connectTCP('localhost', port, factory)
            self.assertAdditionalFDsOpen(2, 'connect (socket, client)')
            return factory.login(fpb.Authenticator(username='user',
                                                   password='test'))

        def sendFeed(remote):
            # apparently one has to do magic to get the feed to work
            client.setRemoteReference(remote)
            self.assertAdditionalFDsOpen(3, 'feed (socket, client, server)')
            return remote.callRemote('sendFeed', '/foo/bar:baz')

        def feedSent(thisValueIsNone):
            # either just before or just after this, we received a
            # sendFeedReply call from the feedserver. so now we're
            # waiting on the component to get its fd
            self.assertAdditionalFDsOpen(3, 'feedSent (socket, client, server)')
            return component.waitForFD()

        def feedReady((feedId, fd)):
            # at this point... well things are complicated. twisted
            # still knows about the fd, because of client._transports,
            # but it's not in the reactor. see the FIXME at feed.py:99.
            # ideally here the fd we receive is ours, unrelated to the
            # socket object, which we would then close. in practice we
            # close it because the socket object will not be closed from
            # python in the context of this test case. Need to fix the FIXME!
            self.assertEquals(feedId, 'bar:baz')
            self.assertAdditionalFDsOpen(3, 'cleanup (socket, client, server)')
            os.close(fd)
            self.assertAdditionalFDsOpen(2, 'cleanup (socket, client, server)')
            return self.brain.waitForFD()

        def feedReadyOnServer((componentId, feedName, fd, eaterId)):
            # this likely fires directly, not having dropped into the
            # reactor.

            # this fd is not ours, we should dup it if we want to hold
            # onto it
            return self.feedServer.waitForAvatarExit()

        def checkfds(_):
            self.assertAdditionalFDsOpen(1, 'feedReadyOnServer (socket)')

        d = login()
        d.addCallback(sendFeed)
        d.addCallback(feedSent)
        d.addCallback(feedReady)
        d.addCallback(feedReadyOnServer)
        d.addCallback(checkfds)
        return d

    def testConnectAndFeed(self):
        component = FakeComponent()
        client = feed.FeedMedium(component)

        def login():
            port = self.feedServer.getPortNum()
            self.assertAdditionalFDsOpen(1, 'connect (socket)')
            d = client.startConnecting('localhost', port,
                                       fpb.Authenticator(username='user',
                                                         password='test'))
            self.assertAdditionalFDsOpen(2, 'connect (socket, client)')
            return d

        def sendFeed(remote):
            # apparently one has to do magic to get the feed to work
            client.setRemoteReference(remote)
            self.assertAdditionalFDsOpen(3, 'feed (socket, client, server)')
            return remote.callRemote('sendFeed', '/foo/bar:baz')

        def feedSent(thisValueIsNone):
            # either just before or just after this, we received a
            # sendFeedReply call from the feedserver. so now we're
            # waiting on the component to get its fd
            self.assertAdditionalFDsOpen(3, 'feedSent (socket, client, server)')
            return component.waitForFD()

        def feedReady((feedId, fd)):
            # at this point... well things are complicated. twisted
            # still knows about the fd, because of client._transports,
            # but it's not in the reactor. see the FIXME at feed.py:99.
            # ideally here the fd we receive is ours, unrelated to the
            # socket object, which we would then close. in practice we
            # close it because the socket object will not be closed from
            # python in the context of this test case. Need to fix the FIXME!
            self.assertEquals(feedId, 'bar:baz')
            self.assertAdditionalFDsOpen(3, 'cleanup (socket, client, server)')
            os.close(fd)
            self.assertAdditionalFDsOpen(2, 'cleanup (socket, client, server)')
            return self.brain.waitForFD()

        def feedReadyOnServer((componentId, feedName, fd, eaterId)):
            # this likely fires directly, not having dropped into the
            # reactor.

            # this fd is not ours, we should dup it if we want to hold
            # onto it
            return self.feedServer.waitForAvatarExit()

        def checkfds(_):
            self.assertAdditionalFDsOpen(1, 'feedReadyOnServer (socket)')

        d = login()
        d.addCallback(sendFeed)
        d.addCallback(feedSent)
        d.addCallback(feedReady)
        d.addCallback(feedReadyOnServer)
        d.addCallback(checkfds)
        return d
