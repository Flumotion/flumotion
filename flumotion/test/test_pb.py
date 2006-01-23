# -*- Mode: Python; test-case-name: flumotion.test.test_pb -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# Flumotion - a streaming media server
# Copyright (C) 2004,2005,2006 Fluendo, S.L. (www.fluendo.com).
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

import crypt

from twisted.internet import defer, reactor
from twisted.python import log as tlog
from twisted.spread import pb as tpb
from twisted.cred import credentials as tcredentials
from twisted.cred import checkers as tcheckers
from twisted.cred import portal, error

from flumotion.twisted import checkers, credentials, pb
from flumotion.twisted import portal as fportal
from flumotion.common import keycards, log
from flumotion.component.bouncers import htpasswdcrypt

bouncerconf = {'name': 'testbouncer',
               'properties': {'data': "user:qi1Lftt0GZC0o"}}

### lots of fake objects to have fun with

class FakePortalWrapperPlaintext:
    # a fake wrapper with a checker that lets username, password in
    def __init__(self):
        self.broker = FakeBroker()
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

class FakeAvatar(tpb.Avatar):
    __implements__ = (tpb.IPerspective, )
    loggedIn = loggedOut = False
    
    def __init__(self):
        pass

    def logout(self):
        self.loggedOut = True

class FakeRealm:
    def __init__(self):
        self.avatar = FakeAvatar()
    def requestAvatar(self, avatarId, mind, *interfaces):
        interface = interfaces[0]
        assert interface == tpb.IPerspective
        self.avatar.loggedIn = True
        # we can return a deferred, or return directly
        return defer.succeed((tpb.IPerspective, self.avatar, self.avatar.logout))

class FakeMind(tpb.Referenceable):
    pass

class FakeBroker(tpb.Broker):
    pass

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

### SHINY NEW FPB
class Test_BouncerWrapper(unittest.TestCase):
    def setUp(self):
        broker = FakeBroker()

        self.bouncer = htpasswdcrypt.HTPasswdCrypt()
        self.bouncer.setup(bouncerconf)
        self.bouncerPortal = fportal.BouncerPortal(FakeRealm(), self.bouncer)
        self.wrapper = pb._BouncerWrapper(self.bouncerPortal, broker)
        
    def testUACPPOk(self):
        mind = FakeMind()
        keycard = keycards.KeycardUACPP('user', 'test', '127.0.0.1')
        d = self.wrapper.remote_login(keycard, mind, 'twisted.spread.pb.IPerspective')
        result = unittest.deferredResult(d)
        self.assert_(isinstance(result, tpb.AsReferenceable))
    
    def testUACPPWrongPassword(self):
        keycard = keycards.KeycardUACPP('user', 'tes', '127.0.0.1')
        d = self.wrapper.remote_login(keycard, "avatarId", 'twisted.spread.pb.IPerspective')
        failure = unittest.deferredError(d)
        failure.trap(error.UnauthorizedLogin)

    def testUACPCCOk(self):
        # create
        keycard = keycards.KeycardUACPCC('user', '127.0.0.1')

        # send
        d = self.wrapper.remote_login(keycard, None, 'twisted.spread.pb.IPerspective')
        keycard = unittest.deferredResult(d)
        self.assertEquals(keycard.state, keycards.REQUESTING)

        # respond to challenge
        keycard.setPassword('test')
        d = self.wrapper.remote_login(keycard, None, 'twisted.spread.pb.IPerspective')
        # check if we have a referenceable
        result = unittest.deferredResult(d)
        self.assert_(isinstance(result, tpb.AsReferenceable))
    
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

    def testUACPCCTamperWithChallenge(self):
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

class Test_FPortalRoot(unittest.TestCase):
    def setUp(self):
        self.bouncerPortal = fportal.BouncerPortal(FakeRealm(), 'bouncer')
        self.root = pb._FPortalRoot(self.bouncerPortal)

    def testRootObject(self):
        root = self.root.rootObject('a')
        self.failUnless(isinstance(root, pb._BouncerWrapper))
        self.assertEquals(root.broker, 'a')

# time for the big kahuna
class Test_FPBClientFactory(unittest.TestCase):
    def setUp(self):
        self.realm = FakeRealm()
        self.bouncer = htpasswdcrypt.HTPasswdCrypt()
        self.bouncer.setup(bouncerconf)
        self.portal = fportal.BouncerPortal(self.realm, self.bouncer)
        unsafeTracebacks = 1
        self.factory = tpb.PBServerFactory(self.portal, unsafeTracebacks=1)
        self.port = reactor.listenTCP(0, self.factory, interface="127.0.0.1")
        self.portno = self.port.getHost().port
        # don't output Twisted tracebacks for PB errors we will trigger
        log.theFluLogObserver.ignoreErrors(error.UnauthorizedLogin)

    def tearDown(self):
        log.theFluLogObserver.clearIgnores()
        self.port.stopListening()
        reactor.iterate()
        reactor.iterate()

    def clientDisconnect(self, factory, reference):
        # clean up broker by waiting on Disconnect notify
        d = defer.Deferred()
        if reference:
            reference.notifyOnDisconnect(lambda r: d.callback(None))
        factory.disconnect()
        if reference:
            unittest.deferredResult(d)
 
    def testUACPPOk(self):
        factory = pb.FPBClientFactory()

        # create
        keycard = keycards.KeycardUACPP('user', 'test', '127.0.0.1')

        # send 
        d = factory.login(keycard, 'MIND')
        reactor.connectTCP("127.0.0.1", self.portno, factory)

        # get result
        result = unittest.deferredResult(d)
        self.assert_(isinstance(result, tpb.RemoteReference))
        self.clientDisconnect(factory, result)

    def testUACPPWrongPassword(self):
        factory = pb.FPBClientFactory()
        keycard = keycards.KeycardUACPP('user', 'tes', '127.0.0.1')
        d = factory.login(keycard, 'MIND')
        c = reactor.connectTCP("127.0.0.1", self.portno, factory)

        p = unittest.deferredError(d)
        self.failUnless(p.check("twisted.cred.error.UnauthorizedLogin"))
        self.clientDisconnect(factory, None)
        from twisted.cred.error import UnauthorizedLogin
        tlog.flushErrors(UnauthorizedLogin)

    def testUACPCCOk(self):
        factory = pb.FPBClientFactory()

        # create
        keycard = keycards.KeycardUACPCC('user', '127.0.0.1')

        # send
        d = factory.login(keycard, 'MIND')
        c = reactor.connectTCP("127.0.0.1", self.portno, factory)

        # get result
        keycard = unittest.deferredResult(d)
        self.assertEquals(keycard.state, keycards.REQUESTING)

        # respond to challenge
        keycard.setPassword('test')
        d = factory.login(keycard, 'MIND')

        # check if we have a remote reference
        result = unittest.deferredResult(d)
        self.assert_(isinstance(result, tpb.RemoteReference))
        self.clientDisconnect(factory, result)

    def testUACPCCWrongUser(self):
        factory = pb.FPBClientFactory()

        # create
        keycard = keycards.KeycardUACPCC('wronguser', '127.0.0.1')

        # send
        d = factory.login(keycard, 'MIND')
        c = reactor.connectTCP("127.0.0.1", self.portno, factory)
        keycard = unittest.deferredResult(d)
        self.assertEquals(keycard.state, keycards.REQUESTING)

        # respond to challenge
        keycard.setPassword('test')
        d = factory.login(keycard, 'MIND')

        # find copied failure
        p = unittest.deferredError(d)
        self.failUnless(p.check("twisted.cred.error.UnauthorizedLogin"))
        self.clientDisconnect(factory, None)
        from twisted.cred.error import UnauthorizedLogin
        tlog.flushErrors(UnauthorizedLogin)

    def testUACPCCWrongPassword(self):
        factory = pb.FPBClientFactory()

        # create
        keycard = keycards.KeycardUACPCC('user', '127.0.0.1')

        # send
        d = factory.login(keycard, 'MIND')
        c = reactor.connectTCP("127.0.0.1", self.portno, factory)
        keycard = unittest.deferredResult(d)
        self.assertEquals(keycard.state, keycards.REQUESTING)

        # respond to challenge
        keycard.setPassword('wrongpass')
        d = factory.login(keycard, 'MIND')

        # find copied failure
        p = unittest.deferredError(d)
        self.failUnless(p.check("twisted.cred.error.UnauthorizedLogin"))
        self.clientDisconnect(factory, None)
        from twisted.cred.error import UnauthorizedLogin
        tlog.flushErrors(UnauthorizedLogin)

    def testUACPCCTamperWithChallenge(self):
        factory = pb.FPBClientFactory()

        # create
        keycard = keycards.KeycardUACPCC('user', '127.0.0.1')
        self.assert_(keycard)
        self.assertEquals(keycard.state, keycards.REQUESTING)

        # send
        d = factory.login(keycard, 'MIND')
        c = reactor.connectTCP("127.0.0.1", self.portno, factory)

        keycard = unittest.deferredResult(d)
        self.assertEquals(keycard.state, keycards.REQUESTING)

        # mess with challenge, respond to challenge and resubmit
        keycard.challenge = "I am a h4x0r"
        keycard.setPassword('test')
        d = factory.login(keycard, 'MIND')

        # find copied failure
        p = unittest.deferredError(d)
        self.failUnless(p.check("twisted.cred.error.UnauthorizedLogin"))
        self.clientDisconnect(factory, None)
        from twisted.cred.error import UnauthorizedLogin
        tlog.flushErrors(UnauthorizedLogin)

if __name__ == '__main__':
     unittest.main()
