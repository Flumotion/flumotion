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

import common

from twisted.trial import unittest
from twisted.internet import defer, reactor

from flumotion.component.bouncers import bouncer
from flumotion.common import keycards


class FakeBouncerMedium(bouncer.BouncerMedium):
    def __init__(self):
        self.calls = []

    def callRemote(self, method, *args, **kwargs):
        self.calls.append((method, args, kwargs))
        return defer.succeed(None)

class TrivialBouncerTest(unittest.TestCase):
    def setUp(self):
        self.comp = bouncer.TrivialBouncer()
        self.comp.setMedium(FakeBouncerMedium())
        return self.comp.start()

    def tearDown(self):
        return self.comp.stop()

    def testHarness(self):
        pass

    def assertAttr(self, keycard, attr, val):
        self.assertEquals(getattr(keycard, attr), val)
        return keycard

    def testAuthentication(self):
        k = keycards.KeycardGeneric()
        self.assertEquals(k.state, keycards.REQUESTING)

        d = self.comp.authenticate(k)
        d.addCallback(self.assertAttr, 'state', keycards.AUTHENTICATED)
        return d

    def testTimeoutAlgorithm(self):
        # the plan: make a keycard that expires in 0.75 seconds, and
        # set up the component such that it checks for expired keycards
        # every half second. this test will check the keycard's
        # ttl value at 0.25 seconds and 0.75 seconds, and will
        # make sure that at 1.25 seconds that the keycard is out of the
        # bouncer.

        # check for expired keycards every half a second
        self.comp.KEYCARD_EXPIRE_INTERVAL = 0.5

        def checkTimeout(k):
            def check(expected, inBouncer, furtherChecks):
                if k.ttl != expected:
                    d.errback(AssertionError('ttl %r != expected %r'
                                             % (k.ttl, expected)))
                if inBouncer:
                    if not self.comp.hasKeycard(k):
                        d.errback(AssertionError('comp missing keycard'))
                else:
                    if self.comp.hasKeycard(k):
                        d.errback(AssertionError(
                            'comp unexpectedly has keycard'))
                        
                if furtherChecks:
                    args = furtherChecks.pop(0)
                    args += (furtherChecks,)
                    reactor.callLater(*args)
                else:
                    d.callback('success')
            reactor.callLater(0.25, check, 0.75, True,
                              [(0.5, check, 0.25, True),
                               (0.5, check, -0.25, False)])
            d = defer.Deferred()
            return d

        def checkCalls(res):
            self.assertEquals(self.comp.medium.calls,
                              [('expireKeycard', (k.requesterId, k.id), {})])
            return res

        k = keycards.KeycardGeneric()
        k.ttl = 0.75
        self.assertEquals(k.state, keycards.REQUESTING)
        d = self.comp.authenticate(k)
        d.addCallback(self.assertAttr, 'state', keycards.AUTHENTICATED)
        d.addCallback(self.assertAttr, 'ttl', 0.75)
        d.addCallback(checkTimeout)
        d.addCallback(checkCalls)
        return d
