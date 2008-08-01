# -*- Mode: Python -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# Flumotion - a streaming media server
# Copyright (C) 2007 Fluendo, S.L. (www.fluendo.com).
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

from flumotion.common import testsuite

from twisted.internet import defer, reactor

from flumotion.common import keycards


class FakeMedium:
    calls = []

    def callRemote(self, method, *args, **kwargs):
        if not self.calls:
            # avoid modifying the class attribute
            self.calls = []
        self.calls.append((method, args, kwargs))
        return defer.succeed(None)


class TrivialBouncerTest(testsuite.TestCase):
    obj = None
    medium = None

    def setUp(self):
        assert self.obj, "subclass must set self.obj"
        assert self.medium, "subclass must set self.medium"

    def testHarness(self):
        pass

    def assertAttr(self, keycard, attr, val):
        self.assertEquals(getattr(keycard, attr), val)
        return keycard

    def testAuthentication(self):
        k = keycards.KeycardGeneric()
        self.assertEquals(k.state, keycards.REQUESTING)

        d = self.obj.authenticate(k)
        d.addCallback(self.assertAttr, 'state', keycards.AUTHENTICATED)
        return d

    def setKeycardExpireInterval(self, interval):
        # can be overridden
        self.obj._expirer.timeout = interval

    def testTimeoutAlgorithm(self):
        # the plan: make a keycard that expires in 0.75 seconds, and
        # set up the component such that it checks for expired keycards
        # every half second. this test will check the keycard's
        # ttl value at 0.25 seconds and 0.75 seconds, and will
        # make sure that at 1.25 seconds that the keycard is out of the
        # bouncer.

        # check for expired keycards every half a second
        self.setKeycardExpireInterval(0.5)

        def checkTimeout(k):

            def check(expected, inBouncer, furtherChecks):
                if k.ttl != expected:
                    d.errback(AssertionError('ttl %r != expected %r'
                                             % (k.ttl, expected)))
                    return
                if inBouncer:
                    if not self.obj.hasKeycard(k):
                        d.errback(AssertionError('comp missing keycard'))
                        return
                else:
                    if self.obj.hasKeycard(k):
                        d.errback(AssertionError(
                            'comp unexpectedly has keycard'))
                        return

                if furtherChecks:
                    args = furtherChecks.pop(0)
                    args += (furtherChecks, )
                    reactor.callLater(*args)
                else:
                    d.callback('success')
            reactor.callLater(0.25, check, 0.75, True,
                              [(0.5, check, 0.25, True),
                               (0.5, check, -0.25, False)])
            d = defer.Deferred()
            return d

        def checkCalls(res):
            self.assertEquals(self.medium.calls,
                              [('expireKeycard', (k.requesterId, k.id), {})])
            return res

        k = keycards.KeycardGeneric()
        k.ttl = 0.75
        self.assertEquals(k.state, keycards.REQUESTING)
        d = self.obj.authenticate(k)
        d.addCallback(self.assertAttr, 'state', keycards.AUTHENTICATED)
        d.addCallback(self.assertAttr, 'ttl', 0.75)
        d.addCallback(checkTimeout)
        d.addCallback(checkCalls)
        return d

    def testKeepAlive(self):

        def adjustTTL(_):
            self.assertEquals(k.ttl, 0.75)
            self.obj.keepAlive('bar', 10)
            self.assertEquals(k.ttl, 0.75)
            self.obj.keepAlive('foo', 10)
            self.assertEquals(k.ttl, 10)

        k = keycards.KeycardGeneric()
        k.ttl = 0.75
        k.issuerName = 'foo'
        self.assertEquals(k.state, keycards.REQUESTING)
        d = self.obj.authenticate(k)
        d.addCallback(self.assertAttr, 'state', keycards.AUTHENTICATED)
        d.addCallback(self.assertAttr, 'ttl', 0.75)
        d.addCallback(adjustTTL)
        return d

    def testAutoExpire(self):

        def authenticated(_):
            self.assertAttr(k, 'state', keycards.AUTHENTICATED)
            self.assertAttr(k, 'ttl', 0)
            self.failIf(self.obj.hasKeycard(k))
            self.assertEquals(self.medium.calls, [])

        k = keycards.KeycardGeneric()
        k.ttl = 0
        self.assertEquals(k.state, keycards.REQUESTING)
        d = self.obj.authenticate(k)
        d.addCallback(authenticated)
        return d
