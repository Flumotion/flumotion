# -*- Mode: Python; test-case-name: flumotion.test.test_saltsha256 -*-
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

from flumotion.common import testsuite
from twisted.trial import unittest
from twisted.internet import defer

from flumotion.common import keycards
from flumotion.component.bouncers import saltsha256


bouncerconf = {
    'name': 'testbouncer',
    'plugs': {},
    'properties': {
        'data': ("user:"
                 "iamsalt:"
                 "2f826124ada2b2cdf11f4fd427c9ca48"
                 "de0ed49b41476266d8df08d2cf86120e")}}

# this is a type that should not be allowed


class TestWrongKeycardClass(testsuite.TestCase):

    def setUp(self):
        self.bouncer = saltsha256.SaltSha256(bouncerconf)

    def tearDown(self):
        self.bouncer.stop()

    def testWrongKeycardClass(self):
        keycard = keycards.Keycard()
        d = defer.maybeDeferred(self.bouncer.authenticate, keycard)

        def wrongKeycardClassCallback(result):
            self.failIf(result)
        d.addCallback(wrongKeycardClassCallback)
        return d


class TestSaltSha256USCPCC(testsuite.TestCase):

    def setUp(self):
        self.bouncer = saltsha256.SaltSha256(bouncerconf)

    def tearDown(self):
        self.bouncer.stop()

    def testOk(self):
        # create challenger
        keycard = keycards.KeycardUASPCC('user', '127.0.0.1')
        self.assert_(keycard)
        self.assertEquals(keycard.state, keycards.REQUESTING)

        # submit for auth
        d = defer.maybeDeferred(self.bouncer.authenticate, keycard)

        def okCallback(result):
            self.assertEquals(result.state, keycards.REQUESTING)
            # respond to challenge and resubmit
            result.setPassword('test')
            dd = defer.maybeDeferred(self.bouncer.authenticate, keycard)

            def authenticatedCallback(result):
                self.assertEquals(result.state, keycards.AUTHENTICATED)
            dd.addCallback(authenticatedCallback)
            return dd

        d.addCallback(okCallback)
        return d

    def testTamperWithChallenge(self):
        # create challenger
        keycard = keycards.KeycardUASPCC('user', '127.0.0.1')
        self.assert_(keycard)
        self.assertEquals(keycard.state, keycards.REQUESTING)

        # submit for auth
        d = defer.maybeDeferred(self.bouncer.authenticate, keycard)

        def tamperCallback(result):
            self.assertEquals(result.state, keycards.REQUESTING)
            # mess with challenge, respond to challenge and resubmit
            result.challenge = "I am a h4x0r"
            result.setPassword('test')
            dd = defer.maybeDeferred(self.bouncer.authenticate, keycard)

            def tamperAuthenticateCallback(result):
                self.failIf(result)
            dd.addCallback(tamperAuthenticateCallback)
            return dd
        d.addCallback(tamperCallback)
        return d
if __name__ == '__main__':
    unittest.main()
