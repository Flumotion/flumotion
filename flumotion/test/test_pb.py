# -*- Mode: Python; test-case-name: flumotion.test.test_pb -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# flumotion/test/test_pb.py:
# regression test for flumotion.twisted.pb
#
# Flumotion - a streaming media server
# Copyright (C) 2004 Fluendo (www.fluendo.com)

# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
# See "LICENSE.GPL" in the source distribution for more information.

# This program is also licensed under the Flumotion license.
# See "LICENSE.Flumotion" in the source distribution for more information.

import common
from twisted.trial import unittest

import crypt

from twisted.internet import defer
from twisted.spread import pb as tpb
from twisted.cred import credentials as tcredentials
from twisted.cred import checkers as tcheckers
from twisted.cred import portal, error

from flumotion.twisted import checkers, credentials, pb
from flumotion.twisted import portal as fportal
from flumotion.common import keycards
from flumotion.component.bouncers import htpasswdcrypt

class FakePortalWrapperPlaintext:
    # a fake wrapper with a checker that lets username, password in
    def __init__(self):
        self.checker = tcheckers.InMemoryUsernamePasswordDatabaseDontUse()
        self.checker.addUser("username", "password")
        self.portal = portal.Portal(FakeRealm(), (self.checker, ))

class FakePortalWrapperCrypt:
    # a fake wrapper with a checker that lets username, crypt(password, iq) in
    def __init__(self):
        self.checker = checkers.CryptChecker()
        cryptPassword = crypt.crypt('password', 'iq')
        self.checker.addUser("username", cryptPassword)
        self.portal = portal.Portal(FakeRealm(), (self.checker, ))

# FIXME: using real portal
class FakeBouncerPortal:
    # a fake wrapper implementing BouncerPortal lookalike
    def __init__(self, bouncer):
        self.bouncer = bouncer

    def login(self, keycard, mind, interfaces):
        return self.bouncer.authenticate(keycard)

class FakeRealm:
    def requestAvatar(self, avatarId, mind, *interfaces):
        return defer.Deferred()

# our test for twisted's challenger
# this is done for comparison with our challenger
class TestTwisted_PortalAuthChallenger(unittest.TestCase):
    def setUp(self):
        # PB server creates a challenge
        self.challenge = tpb.challenge()
        # and a challenger to send to the client
        self.challenger = tpb._PortalAuthChallenger(FakePortalWrapperPlaintext(), 
            'username', self.challenge)

    def testRightPassword(self):
        # client is asked to respond, so generate the response
        response = tpb.respond(self.challenge, 'password')

        self.challenger.remote_respond(response, None)

    def testWrongPassword(self):
        # client is asked to respond, so generate the response
        response = tpb.respond(self.challenge, 'wrong')

        d = self.challenger.remote_respond(response, None)
        failure = unittest.deferredError(d)
        failure.trap(error.UnauthorizedLogin)

class TestFlumotion_PortalAuthChallenger(unittest.TestCase):
    def setUp(self):
        # our PB server creates a salty challenge
        self.challenge = tpb.challenge()
        self.challenge = 'is' + 'thesalt'
        # and a challenger to send to the client
        self.challenger = pb._PortalAuthChallenger(FakePortalWrapperPlaintext(), 
            'username', 'avatarId',
            self.challenge, None)

    def testRightPassword(self):
        # client is asked to respond, so generate the response
        salt = self.challenge[:2]
        import crypt
        cryptPassword = crypt.crypt('password', salt)
        response = tpb.respond(self.challenge, cryptPassword)

        self.challenger.remote_respond(response, None)

    def testWrongPassword(self):
        # client is asked to respond, so generate the response
        response = tpb.respond(self.challenge, 'wrong')

        d = self.challenger.remote_respond(response, None)
        failure = unittest.deferredError(d)
        failure.trap(error.UnauthorizedLogin)

class TestFlumotion_PortalAuthChallengerCrypt(unittest.TestCase):
    def setUp(self):
        # PB server receives login request with username
        username = "username"
        
        # our PB server creates a salty challenge for the given username
        portal = FakePortalWrapperCrypt()
        checker = portal.checker
        cryptPassword = checker.users[username]
        salt = cryptPassword[:2]
        self.challenge = salt + tpb.challenge()
        
        # and a challenger to send to the client
        self.challenger = pb._PortalAuthChallenger(portal, 
            username, 'avatarId',
            self.challenge, None)

    def testRightPassword(self):
        # client is asked to respond, so generate the response
        salt = self.challenge[:2]
        cryptPassword = crypt.crypt('password', salt)
        response = tpb.respond(self.challenge, cryptPassword)

        # client sends response to the server
        self.challenger.remote_respond(response, None)

    def testWrongPassword(self):
        # client is asked to respond, so generate the response
        response = tpb.respond(self.challenge, 'wrong')

        d = self.challenger.remote_respond(response, None)
        failure = unittest.deferredError(d)
        failure.trap(error.UnauthorizedLogin)

### SHINY NEW FPB
class Test_BouncerWrapper(unittest.TestCase):
    def setUp(self):
        data = """user:qi1Lftt0GZC0o"""
        self.bouncer = htpasswdcrypt.HTPasswdCrypt('testbouncer', None, data)
        self.bouncerPortal = fportal.BouncerPortal(FakeRealm(), self.bouncer)
        self.wrapper = pb._BouncerWrapper(self.bouncerPortal, None)

        
    def FIXME_UACPPOk(self):
        keycard = keycards.KeycardUACPP('user', 'test', '127.0.0.1')
        d = self.wrapper.remote_login(keycard, "avatarId", 'twisted.spread.pb.IPerspective')
        keycard = unittest.deferredResult(d)
        self.assertEquals(keycard.state, keycards.REQUESTING)
        keycard = unittest.deferredResult(d)
        self.assertEquals(keycard.state, keycards.AUTHENTICATED)

    def testUACPPWrongPassword(self):
        keycard = keycards.KeycardUACPP('user', 'tes', '127.0.0.1')
        d = self.wrapper.remote_login(keycard, "avatarId", 'twisted.spread.pb.IPerspective')
        failure = unittest.deferredError(d)
        failure.trap(error.UnauthorizedLogin)

    def FIXME_UACPCCOk(self):
        # create
        keycard = keycards.KeycardUACPCC('user', '127.0.0.1')

        # send
        d = self.wrapper.remote_login(keycard, None, 'twisted.spread.pb.IPerspective')
        keycard = unittest.deferredResult(d)
        self.assertEquals(keycard.state, keycards.REQUESTING)

        # respond to challenge
        keycard.setPassword('test')
        d = self.wrapper.remote_login(keycard, None, 'twisted.spread.pb.IPerspective')
        keycard = unittest.deferredResult(d)
        self.assertEquals(keycard.state, keycards.AUTHENTICATED)

    def testUACPCCWrongUser(self):
        # create
        keycard = keycards.KeycardUACPCC('wronguser', '127.0.0.1')

        # send
        d = self.wrapper.remote_login(keycard, "avatarId", 'twisted.spread.pb.IPerspective')
        keycard = unittest.deferredResult(d)
        self.assertEquals(keycard.state, keycards.REQUESTING)

        # respond to challenge
        keycard.setPassword('test')
        d = self.wrapper.remote_login(keycard, "avatarId", 'twisted.spread.pb.IPerspective')
        failure = unittest.deferredError(d)
        failure.trap(error.UnauthorizedLogin)

    def testUACPCCWrongPassword(self):
        # create
        keycard = keycards.KeycardUACPCC('user', '127.0.0.1')

        # send
        d = self.wrapper.remote_login(keycard, "avatarId", 'twisted.spread.pb.IPerspective')
        keycard = unittest.deferredResult(d)
        self.assertEquals(keycard.state, keycards.REQUESTING)

        # respond to challenge
        keycard.setPassword('wrong')
        d = self.wrapper.remote_login(keycard, "avatarId", 'twisted.spread.pb.IPerspective')
        failure = unittest.deferredError(d)
        failure.trap(error.UnauthorizedLogin)

    def testTamperWithChallenge(self):
        # create challenger
        keycard = keycards.KeycardUACPCC('user', '127.0.0.1')
        self.assert_(keycard)
        self.assertEquals(keycard.state, keycards.REQUESTING)
                                                                                
        # submit for auth
        d = self.wrapper.remote_login(keycard, "avatarId", 'twisted.spread.pb.IPerspective')
        keycard = unittest.deferredResult(d)
        self.assertEquals(keycard.state, keycards.REQUESTING)
                                                                                
        # mess with challenge, respond to challenge and resubmit
        keycard.challenge = "I am a h4x0r"
        keycard.setPassword('test')
        d = self.wrapper.remote_login(keycard, "avatarId", 'twisted.spread.pb.IPerspective')
        failure = unittest.deferredError(d)
        failure.trap(error.UnauthorizedLogin)
 
if __name__ == '__main__':
     unittest.main()
