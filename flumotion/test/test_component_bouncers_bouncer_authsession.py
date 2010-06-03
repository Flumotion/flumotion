# -*- Mode: Python -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# Flumotion - a streaming media server
# Copyright (C) 2004,2005,2006,2007 Fluendo, S.L. (www.fluendo.com).
# All rights reserved.
# flumotion-platform - Flumotion Streaming Platform

# Licensees having purchased or holding a valid Flumotion Advanced
# Streaming Server license may use this file in accordance with the
# Flumotion Advanced Streaming Server Commercial License Agreement.
# See "LICENSE.Flumotion" in the source distribution for more information.

# Headers in this file shall remain intact.

from flumotion.common import testsuite

from flumotion.component.bouncers import component

from flumotion.common import keycards
from twisted.spread import pb


class DummyBouncer(component.AuthSessionBouncer):

    def do_extractKeycardInfo(self, keycard, oldData):
        return keycard


class AuthSessionBouncerTestCase(testsuite.TestCase):

    def setUp(self):
        config = {'name': 'fake',
                  'avatarId': '/default/fake',
                  'plugs': {},
                  'properties': {}}
        self.bouncer = DummyBouncer(config)

    def tearDown(self):
        self.bouncer.stop()

    def testNormalBehaviors(self):
        # Client create a keycard
        keycard = keycards.Keycard()
        self.assertEquals(keycard.state, keycards.REQUESTING)

        # Client send the keycard to the bouncer
        answer = pb.unjelly(pb.jelly(keycard))
        self.assertEquals(answer.state, keycards.REQUESTING)
        self.assertNotEquals(keycard, answer)

        # Bouncer do not know about the keycard
        self.failIf(self.bouncer.hasKeycard(answer))
        self.failIf(self.bouncer.hasAuthSession(answer))
        self.assertEqual(None, self.bouncer.getAuthSessionInfo(answer))

        # Bouncer start an authentication session
        self.failUnless(self.bouncer.startAuthSession(answer))
        self.assertEquals(answer.state, keycards.REQUESTING)
        self.failIf(self.bouncer.hasKeycard(answer))
        self.failUnless(self.bouncer.hasAuthSession(answer))
        self.assertEqual(answer, self.bouncer.getAuthSessionInfo(answer))

        # Bouncer send back the keycard to the client
        challenge = pb.unjelly(pb.jelly(answer))
        self.assertEquals(challenge.state, keycards.REQUESTING)
        self.assertNotEquals(answer, challenge)

        # Client send back a response keycard
        response = pb.unjelly(pb.jelly(challenge))
        self.assertEquals(response.state, keycards.REQUESTING)
        self.assertNotEquals(challenge, response)

        # Bouncer state did not change, and the keycard are associated
        self.failIf(self.bouncer.hasKeycard(answer))
        self.failIf(self.bouncer.hasKeycard(response))
        self.failUnless(self.bouncer.hasAuthSession(answer))
        self.failUnless(self.bouncer.hasAuthSession(response))
        self.assertEqual(answer, self.bouncer.getAuthSessionInfo(answer))
        self.assertEqual(answer, self.bouncer.getAuthSessionInfo(response))
        self.assertNotEqual(response,
                            self.bouncer.getAuthSessionInfo(answer))
        self.assertNotEqual(response,
                            self.bouncer.getAuthSessionInfo(response))

        # Bouncer confirm the authentication
        self.failUnless(self.bouncer.confirmAuthSession(response))
        self.assertEquals(response.state, keycards.AUTHENTICATED)
        self.assertEquals(answer.state, keycards.REQUESTING)
        self.failIf(self.bouncer.hasKeycard(answer))
        self.failUnless(self.bouncer.hasKeycard(response))
        self.failIf(self.bouncer.hasAuthSession(answer))
        self.failIf(self.bouncer.hasAuthSession(response))
        self.assertEqual(None, self.bouncer.getAuthSessionInfo(answer))
        self.assertEqual(None, self.bouncer.getAuthSessionInfo(response))

    def testEarlyCanceling(self):
        keycard = keycards.Keycard()
        answer = pb.unjelly(pb.jelly(keycard))
        self.failUnless(self.bouncer.startAuthSession(answer))

        # Bouncer cancel the authentication
        self.bouncer.cancelAuthSession(answer)
        self.assertEquals(answer.state, keycards.REFUSED)
        self.failIf(self.bouncer.hasKeycard(answer))
        self.failIf(self.bouncer.hasAuthSession(answer))
        self.assertEqual(None, self.bouncer.getAuthSessionInfo(answer))

    def testLateCanceling(self):
        keycard = keycards.Keycard()
        answer = pb.unjelly(pb.jelly(keycard))
        self.failUnless(self.bouncer.startAuthSession(answer))
        challenge = pb.unjelly(pb.jelly(answer))
        response = pb.unjelly(pb.jelly(challenge))

        # Bouncer cancel the authentication
        self.bouncer.cancelAuthSession(response)
        self.assertEquals(response.state, keycards.REFUSED)
        self.assertEquals(answer.state, keycards.REQUESTING)
        self.failIf(self.bouncer.hasKeycard(answer))
        self.failIf(self.bouncer.hasKeycard(response))
        self.failIf(self.bouncer.hasAuthSession(answer))
        self.failIf(self.bouncer.hasAuthSession(response))
        self.assertEqual(None, self.bouncer.getAuthSessionInfo(answer))
        self.assertEqual(None, self.bouncer.getAuthSessionInfo(response))

    def testSessionExpiration(self):
        keycard = keycards.Keycard()
        keycard.ttl = 10
        answer = pb.unjelly(pb.jelly(keycard))

        # Bouncer stqrt a session and return the keycard to the client
        self.failUnless(self.bouncer.startAuthSession(answer))
        challenge = pb.unjelly(pb.jelly(answer))

        self.failIf(self.bouncer.hasKeycard(answer))
        self.failUnless(self.bouncer.hasAuthSession(answer))
        self.assertEqual(answer, self.bouncer.getAuthSessionInfo(answer))

        # Then the session expire
        self.bouncer._expire()

        self.failIf(self.bouncer.hasKeycard(answer))
        self.failIf(self.bouncer.hasAuthSession(answer))
        self.assertEqual(None, self.bouncer.getAuthSessionInfo(answer))

        # The client return the response keycard
        response = pb.unjelly(pb.jelly(challenge))

        self.failIf(self.bouncer.hasKeycard(response))
        self.failIf(self.bouncer.hasAuthSession(response))
        self.assertEqual(None, self.bouncer.getAuthSessionInfo(response))

        # The confirmation is refused
        self.failIf(self.bouncer.confirmAuthSession(response))
        self.assertEquals(response.state, keycards.REFUSED)
        self.assertEquals(answer.state, keycards.REQUESTING)
        self.failIf(self.bouncer.hasKeycard(answer))
        self.failIf(self.bouncer.hasKeycard(response))
        self.failIf(self.bouncer.hasAuthSession(answer))
        self.failIf(self.bouncer.hasAuthSession(response))
        self.assertEqual(None, self.bouncer.getAuthSessionInfo(answer))
        self.assertEqual(None, self.bouncer.getAuthSessionInfo(response))
