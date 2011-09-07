# -*- Mode: Python; test-case-name: flumotion.test.test_testclasses -*-
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

from twisted.internet import defer
from twisted.spread import pb

from flumotion.common import log
from flumotion.common import testsuite

attr = testsuite.attr


# an object that subclasses from both Cacheable and RemoteCache
# can be serialized over more than one PB connection
# state changes on the "master" still get serialized to the slaves


class FakeKeycard(pb.Cacheable, pb.RemoteCache):
    name = None
    observers = None

    def getStateToCacheAndObserveFor(self, perspective, observer):
        # we can't implement __init__ due to pb.RemoteCache, so ...
        if not self.observers:
            self.observers = []
        self.observers.append(observer)
        return {'name': self.name}

    # since we inherit from both classes, each with their own jellyFor,
    # we need to make sure they get called correctly

    def jellyFor(self, jellier):
        if not self.broker:
            # since we don't have a broker yet, this is the first time
            # we go through one, so we are the "master" and we should
            # be jellied as a cacheable
            return pb.Cacheable.jellyFor(self, jellier)

        if jellier.invoker and jellier.invoker is not self.broker:
            # we are being sent through a different broker than the one
            # that actually created us, so again, treat us as a cacheable
            return pb.Cacheable.jellyFor(self, jellier)

        # we've already been seen by a broker, so we should be jellied as
        # a remotecache
        return pb.RemoteCache.jellyFor(self, jellier)

    def setName(self, name):
        l = []
        self.name = name
        if self.observers: # since it can be None, see class def
            for o in self.observers:
                d = o.callRemote('setName', name)
                l.append(d)
        return defer.DeferredList(l)

    def observe_setName(self, name):
        log.debug("fakekeycard", "%r.observe_setName, %r" % (self, name))
        # invoke the setter so our RemoteCache's in turn get notified
        return self.setName(name)

    def stoppedObserving(self, perspective, observer):
        self.observers.remove(observer)

pb.setUnjellyableForClass(FakeKeycard, FakeKeycard)


class FakeCacheable(pb.Cacheable):
    pass


class FakeRemoteCache(pb.RemoteCache):
    pass


pb.setUnjellyableForClass(FakeCacheable, FakeRemoteCache)


class TestOnePB(testsuite.TestCase):

    def setUp(self):
        self.pb = testsuite.TestPB()
        return self.pb.start()

    def tearDown(self):
        return self.pb.stop()

    def testFakeKeycard(self):
        keycard = FakeKeycard()
        keycard.name = "tarzan"
        keycard.password = "jane"

        def _send():
        # sending it should result in a keycard that does not have password
            d = self.pb.send(keycard)
            return d

        def _sendCb(sent):
            self.failUnless(sent)
            self.failIfEquals(keycard, sent)
            self.failIf(hasattr(sent, "password"))

            # receiving it again should give us back the original keycard
            d = self.pb.receive(sent)
            return d

        def _receiveCb(received):
            self.failUnless(received)
            self.assertEquals(keycard, received)
            self.assertEquals(received.password, "jane")

        d = _send()
        d.addCallback(_sendCb)
        d.addCallback(_receiveCb)
        return d

    def testCacheable(self):
        c = FakeCacheable()

        def _receive(sent):
            # we can send it back though
            d = self.pb.receive(sent)
            return d

        def _receiveCb(received):
            self.assertEquals(c, received)

        d = self.pb.send(c)
        d.addCallback(_receive)
        d.addCallback(_receiveCb)
        return d


class TestTwoPB(testsuite.TestCase):
    # test if our classes work over two chained PB connections

    slow = True

    def setUp(self):
        self.pb1 = testsuite.TestPB()
        self.pb2 = testsuite.TestPB()
        d = self.pb1.start()
        d.addCallback(lambda r: self.pb2.start())
        return d

    def tearDown(self):
        d = self.pb1.stop()
        d.addCallback(lambda r: self.pb2.stop())
        return d

    def testFakeKeycard(self):
        keycard = FakeKeycard()
        keycard.name = "tarzan"
        keycard.password = "jane"

        def _send1():
            # sending it should result in a keycard that does not have password
            d = self.pb1.send(keycard)
            return d

        def _send1Cb(sent1):
            self.failUnless(sent1)
            self.failIfEquals(keycard, sent1)
            self.failIf(hasattr(sent1, "password"))
            return sent1

        def _send2(sent1):
            log.debug('TestTwoPB', 'sending sent1 %r' % sent1)
            self.sent1 = sent1
            d = self.pb2.send(sent1)
            return d

        def _send2Cb(sent2):
            self.failUnless(sent2)
            self.failIfEquals(keycard, sent2)
            self.failIf(hasattr(sent2, "password"))
            return sent2

        def _receive2(sent2):
            self.sent2 = sent2
            d = self.pb2.receive(sent2)
            return d

        def _receive2Cb(received2):
            # receive in pb 2; ie "in the middle"
            self.failUnless(received2)
            self.assertEquals(self.sent1, received2)
            return received2

        def _receive1(received2):
            d = self.pb1.receive(received2)
            return d

        def _receive1Cb(received1):
            # receive in pb 1
            self.failUnless(received1)
            self.assertEquals(keycard, received1)
            self.assertEquals(received1.password, "jane")
            return received1

        def _setName(result):
            # show that setting the name on the original object gets
            # proxied
            return keycard.setName('mowgli')

        def _setNameCb(result):
            self.assertEquals(self.sent2.name, 'mowgli')

        d = _send1()
        d.addCallback(_send1Cb)
        d.addCallback(_send2)
        d.addCallback(_send2Cb)
        d.addCallback(_receive2)
        d.addCallback(_receive2Cb)
        d.addCallback(_setName)
        d.addCallback(_setNameCb)
        return d
