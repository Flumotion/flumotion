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
    def feedToFD(self, componentId, feedName, fd, eaterId):
        self.info('feed to fd: %s %d %s', feedId, fd, eaterId)
        # return avatar.sendFeed(feedName, fd, eaterId)

    def eatFromFD(self, componentId, feedId, fd):
        self.info('eat from fd: %s %d %s', feedId, fd)
        # return avatar.receiveFeed(feedId, fd)
   
class FakeComponent(log.Loggable):
    def __init__(self, name='test'):
        self.name = name
    
    def eatFromFD(self, feedId, fd):
        self.info('eat from fd: %s %d', feedId, fd)


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
            # this, actually disconnecting from a callLater. Blah!
            # self.assertAdditionalFDsOpen(2, 'cleanup (socket, server)')
            return self.feedServer.waitForAvatarExit()

        def checkfds(res):
            self.assertAdditionalFDsOpen(1, 'cleanup (socket)')
            
        d = login()
        d.addCallback(cleanup)
        d.addCallback(checkfds)
        return d
