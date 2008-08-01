# -*- Mode: Python; test-case-name:flumotion.test.test_component_feed -*-
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

import errno
import os

from twisted.internet import reactor, defer, main
from twisted.python import log as tlog
from twisted.python import failure

from flumotion.common import testsuite
from flumotion.common import log, errors
from flumotion.component import feed
from flumotion.component.bouncers import htpasswdcrypt
from flumotion.twisted import pb as fpb
from flumotion.worker import feedserver


class FakeWorkerBrain(log.Loggable):
    _deferredFD = None

    def waitForFD(self):
        if self._deferredFD is None:
            self._deferredFD = defer.Deferred()
        return self._deferredFD

    def feedToFD(self, componentId, feedName, fd, eaterId):
        self.info('feed to fd: %s %s %d %s',
                  componentId, feedName, fd, eaterId)
        self.waitForFD().callback((componentId, feedName, fd, eaterId))
        # need to return True for server to keep fd open
        return True

    def eatFromFD(self, componentId, eaterAlias, fd, feedId):
        self.info('eat from fd: %s %s %d %s',
                  componentId, eaterAlias, fd, feedId)
        self.waitForFD().callback((componentId, eaterAlias, fd, feedId))
        return True


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

# these tests test both flumotion.worker.feedserver and
# flumotion.component.feed.


class FeedTestCase(testsuite.TestCase, log.Loggable):
    bouncerconf = {'name': 'testbouncer',
                   'plugs': {},
                   # user:test
                   'properties': {'data': "user:qi1Lftt0GZC0o"}}

    def setUp(self):
        self._fdCount = countOpenFileDescriptors()

        self.brain = FakeWorkerBrain()
        self._bouncer = bouncer = htpasswdcrypt.HTPasswdCrypt(self.bouncerconf)
        self.feedServer = FeedServer(self.brain, bouncer, 0)
        self.assertAdditionalFDsOpen(1, 'setUp (socket)')

    def assertAdditionalFDsOpen(self, additionalFDs=0, debug=''):
        actual = countOpenFileDescriptors()
        self.assertEqual(self._fdCount + additionalFDs, actual,
                         debug + (' (%d + %d != %d)'
                                  % (self._fdCount, additionalFDs, actual)))

    def tearDown(self):
        try:
            self.flushLoggedErrors(errors.NotAuthenticatedError)
        except AttributeError:
            tlog.flushErrors(errors.NotAuthenticatedError)
        log._getTheFluLogObserver().clearIgnores()
        d = self.feedServer.shutdown()
        d.addCallback(lambda _: self._bouncer.stop())
        d.addCallback(lambda _: self.assertAdditionalFDsOpen(0, 'tearDown'))
        return d


class TestFeedClient(FeedTestCase, log.Loggable):

    def testConnectWithoutDroppingPB(self):
        client = feed.FeedMedium(logName='test')
        factory = feed.FeedClientFactory(client)

        self.failIf(client.hasRemoteReference())

        def login():
            port = self.feedServer.getPortNum()
            self.assertAdditionalFDsOpen(1, 'connect (socket)')
            reactor.connectTCP('localhost', port, factory)
            self.assertAdditionalFDsOpen(2, 'connect (socket, client)')
            return factory.login(fpb.Authenticator(username='user',
                                                   password='test'))

        def cleanup(res):
            # We're not using requestFeed, so no reference should be set
            self.failIf(client.hasRemoteReference())

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

    def testBadPass(self):
        client = feed.FeedMedium(logName='test')
        factory = feed.FeedClientFactory(client)

        def login():
            port = self.feedServer.getPortNum()
            self.assertAdditionalFDsOpen(1, 'connect (socket)')
            reactor.connectTCP('localhost', port, factory)
            self.assertAdditionalFDsOpen(2, 'connect (socket, client)')
            return factory.login(fpb.Authenticator(username='user',
                                                   password='badpass'))

        def loginOk(root):
            raise AssertionError('should not get here')

        def loginFailed(failure):

            def gotRoot(root):
                # an idempotent method, should return a network failure if
                # the remote side disconnects as it should
                return root.callRemote('getKeycardClasses')

            def gotError(failure):
                self.assertAdditionalFDsOpen(1, 'feedSent (socket)')
                self.info('success')

            def gotKeycardClasses(classes):
                raise AssertionError('should not get here')

            self.info('loginFailed: %s', log.getFailureMessage(failure))
            failure.trap(errors.NotAuthenticatedError)
            d = factory.getRootObject() # should fire immediately
            d.addCallback(gotRoot)
            d.addCallbacks(gotKeycardClasses, gotError)

            return d

        d = login()
        d.addCallbacks(loginOk, loginFailed)
        return d


class TestUpstreamFeedClient(FeedTestCase, log.Loggable):

    def testConnectAndFeed(self):
        client = feed.FeedMedium(logName='test')

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
            self.assertAdditionalFDsOpen(
                3, 'feedSent (socket, client, server)')

            # This is poking the feedmedium's internals, but in the end,
            # this test is of the feed medium's internals, so that's ok.
            return client._feedToDeferred

        def feedReady((feedId, fd)):
            # this fd is ours, it's our responsibility to close it.
            self.assertEquals(feedId, 'bar:baz')

            # The feed medium should have dropped its reference already
            self.failIf(client.hasRemoteReference())

            self.assertAdditionalFDsOpen(3, 'cleanup (socket, client, server)')
            os.close(fd)
            self.assertAdditionalFDsOpen(2, 'cleanup (socket, server)')

            return self.feedServer.waitForAvatarExit()

        def checkfds(_):
            self.assertAdditionalFDsOpen(1, 'feedReadyOnServer (socket)')

        d = login()
        d.addCallback(sendFeed)
        d.addCallback(feedSent)
        d.addCallback(feedReady)
        d.addCallback(checkfds)
        return d

    def testRequestFeed(self):
        client = feed.FeedMedium(logName='frobby')

        self.failIf(client.hasRemoteReference())

        def requestFeed():
            port = self.feedServer.getPortNum()
            self.assertAdditionalFDsOpen(1, 'connect (socket)')
            d = client.requestFeed('localhost', port,
                                   fpb.Authenticator(username='user',
                                                     password='test'),
                                   '/foo/bar:baz')
            self.failIf(client.hasRemoteReference())
            self.assertAdditionalFDsOpen(2, 'connect (socket, client)')
            return d

        def gotFeed((feedId, fd)):
            # the feed medium should have dropped its reference to the
            # remotereference by now, otherwise we get cycles, and
            # remote references can't exist in cycles because they have
            # a __del__ method
            self.failIf(client.hasRemoteReference())

            self.assertEquals(feedId, 'bar:baz')
            self.assertAdditionalFDsOpen(3, 'cleanup (socket, client, server)')
            # our responsibility to close fd
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

        d = requestFeed()
        d.addCallback(gotFeed)
        d.addCallback(feedReadyOnServer)
        d.addCallback(checkfds)
        return d


class TestDownstreamFeedClient(FeedTestCase, log.Loggable):

    def testConnectAndFeed(self):
        client = feed.FeedMedium(logName='test')

        def login():
            port = self.feedServer.getPortNum()
            self.assertAdditionalFDsOpen(1, 'connect (socket)')
            d = client.startConnecting('localhost', port,
                                       fpb.Authenticator(username='user',
                                                         password='test',
                                                         avatarId='test:src'))
            self.assertAdditionalFDsOpen(2, 'connect (socket, client)')
            return d

        def receiveFeed(remote):
            client.setRemoteReference(remote)
            self.assertAdditionalFDsOpen(3, 'feed (socket, client, server)')
            return remote.callRemote('receiveFeed', '/foo/bar:baz')

        def feedReceived(thisValueIsNone):
            return self.feedServer.waitForAvatarExit()

        def serverFdPassed(res):
            self.assertAdditionalFDsOpen(2, 'feedSent (socket, client)')

            t = client.remote.broker.transport
            self.info('stop reading from transport')
            t.stopReading()

            self.info('flushing PB write queue')
            t.doWrite()
            self.info('stop writing to transport')
            t.stopWriting()

            t.keepSocketAlive = True

            # avoid refcount cycles
            client.setRemoteReference(None)

            # Since we need to be able to know when the file descriptor
            # closes, and we currently could be within a doReadOrWrite
            # callstack, close the fd from within a callLater instead to
            # avoid corrupting the reactor's internal state.
            d = defer.Deferred()

            def loseConnection():
                t.connectionLost(failure.Failure(main.CONNECTION_DONE))
                d.callback(None)

            reactor.callLater(0, loseConnection)
            return d

        def checkfds(_):
            self.assertAdditionalFDsOpen(1, 'feedReadyOnServer (socket)')

        d = login()
        d.addCallback(receiveFeed)
        d.addCallback(feedReceived)
        d.addCallback(serverFdPassed)
        d.addCallback(checkfds)
        return d

    def testRequestFeed(self):
        client = feed.FeedMedium(logName='frobby')

        self.failIf(client.hasRemoteReference())

        def requestFeed():
            port = self.feedServer.getPortNum()
            self.assertAdditionalFDsOpen(1, 'connect (socket)')
            d = client.sendFeed('localhost', port,
                                fpb.Authenticator(username='user',
                                                  password='test',
                                                  avatarId='test:src'),
                                '/foo/bar:baz')
            self.failIf(client.hasRemoteReference())
            self.assertAdditionalFDsOpen(2, 'connect (socket, client)')
            return d

        def gotFeed((fullFeedId, fd)):
            # the feed medium should have dropped its reference to the
            # remotereference by now, otherwise we get cycles, and
            # remote references can't exist in cycles because they have
            # a __del__ method
            self.assertEquals(fullFeedId, '/foo/bar:baz')
            self.failIf(client.hasRemoteReference())
            # since both the server and the client close their
            # transports via calllaters, we don't know how many extra
            # sockets should be open now

            # this fd is ours to close
            os.close(fd)

            return self.feedServer.waitForAvatarExit()

        def checkfds(_):
            self.assertAdditionalFDsOpen(1, 'feedReadyOnServer (socket)')

        d = requestFeed()
        d.addCallback(gotFeed)
        d.addCallback(checkfds)
        return d
