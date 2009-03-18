# -*- Mode: Python; test-case-name: flumotion.test.test_pb -*-
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

import crypt

from twisted.cred import portal
from twisted.internet import defer, reactor
from twisted.python import log as tlog
from twisted.spread import pb as tpb
from twisted.trial import unittest
from zope.interface import implements

from flumotion.common import testsuite
from flumotion.common import keycards, log, errors
from flumotion.component.bouncers import htpasswdcrypt, saltsha256
from flumotion.twisted import checkers, pb
from flumotion.twisted import portal as fportal

from flumotion.test.common import haveTwisted

htpasswdcryptConf = {
    'name': 'testbouncer',
    'plugs': {},
    'properties': {'data': "user:qi1Lftt0GZC0o"}}

saltsha256Conf = {
    'name': 'testbouncer',
    'plugs': {},
    'properties': {
    'data':
    ("user:"
     "iamsalt:"
     "2f826124ada2b2cdf11f4fd427c9ca48de0ed49b41476266d8df08d2cf86120e")}}

### lots of fake objects to have fun with


class FakePortalWrapperPlaintext:
    # a fake wrapper with a checker that lets username, password in

    def __init__(self):
        self.broker = FakeBroker()
        self.checker = checkers.FlexibleCredentialsChecker()
        self.checker.addUser("username", "password")
        self.portal = portal.Portal(FakeTRealm(), (self.checker, ))


class FakePortalWrapperCrypt:
    # a fake wrapper with a checker that lets username, crypt(password, iq) in

    def __init__(self):
        self.checker = checkers.CryptChecker()
        cryptPassword = crypt.crypt('password', 'iq')
        self.checker.addUser("username", cryptPassword)
        self.portal = portal.Portal(FakeTRealm(), (self.checker, ))

# FIXME: using real portal


class FakeBouncerPortal:
    # a fake wrapper implementing BouncerPortal lookalike

    def __init__(self, bouncer):
        self.bouncer = bouncer

    def login(self, keycard, mind, interfaces):
        return self.bouncer.authenticate(keycard)


class FakeAvatar(tpb.Avatar):
    implements(tpb.IPerspective)
    loggedIn = loggedOut = False

    def __init__(self):
        pass

    def logout(self):
        self.loggedOut = True


class FakeTRealm:

    def __init__(self):
        self.avatar = FakeAvatar()

    def requestAvatar(self, avatarId, mind, *ifaces):
        interface = ifaces[0]
        assert interface == tpb.IPerspective, (
            "interface is %r and not IPerspective" % interface)
        self.avatar.loggedIn = True
        # we can return a deferred, or return directly
        return defer.succeed((tpb.IPerspective,
                              self.avatar, self.avatar.logout))


class FakeFRealm(FakeTRealm):

    def requestAvatar(self, avatarId, keycard, mind, *interfaces):
        return FakeTRealm.requestAvatar(self, avatarId, mind, *interfaces)


class FakeMind(tpb.Referenceable):
    pass


class FakeBroker(tpb.Broker):
    pass

# our test for twisted's challenger
# this is done for comparison with our challenger


class TestTwisted_PortalAuthChallenger(testsuite.TestCase):
    if haveTwisted(8, 0):
        # FIXME: don't directly use twisted's private classes!
        skip = 'Test broken since twisted 8.0.'

    def setUp(self):
        # PB server creates a challenge
        self.challenge = tpb.challenge()
        # and a challenger to send to the client
        self.challenger = tpb._PortalAuthChallenger(
            FakePortalWrapperPlaintext(),
            'username', self.challenge)

    def testRightPassword(self):
        # client is asked to respond, so generate the response
        response = tpb.respond(self.challenge, 'password')

        self.challenger.remote_respond(response, None)

    def testWrongPassword(self):
        # client is asked to respond, so generate the response
        response = tpb.respond(self.challenge, 'wrong')
        d = self.challenger.remote_respond(response, None)

        def wrongPasswordErrback(wrongpasserror):
            self.assert_(isinstance(wrongpasserror.type(),
                                    errors.NotAuthenticatedError))

        d.addErrback(wrongPasswordErrback)
        return d

### SHINY NEW FPB


class Test_BouncerWrapper(testsuite.TestCase):

    def setUp(self):
        broker = FakeBroker()

        self.bouncer = htpasswdcrypt.HTPasswdCrypt(htpasswdcryptConf)
        self.bouncerPortal = fportal.BouncerPortal(FakeFRealm(), self.bouncer)
        self.wrapper = pb._BouncerWrapper(self.bouncerPortal, broker)

    def tearDown(self):
        self.bouncer.stop()

    def testUACPPOk(self):
        mind = FakeMind()
        keycard = keycards.KeycardUACPP('user', 'test', '127.0.0.1')
        d = self.wrapper.remote_login(keycard, mind,
            'twisted.spread.pb.IPerspective')

        def uacppOkCallback(result):
            self.assert_(isinstance(result, tpb.AsReferenceable))
            return result

        d.addCallback(uacppOkCallback)
        return d

    def testUACPPWrongPassword(self):
        keycard = keycards.KeycardUACPP('user', 'tes', '127.0.0.1')
        d = self.wrapper.remote_login(keycard, "avatarId",
            'twisted.spread.pb.IPerspective')

        def uacppWrongPasswordErrback(wrongpasserror):
            self.assert_(isinstance(wrongpasserror.type(),
                                    errors.NotAuthenticatedError))

        d.addErrback(uacppWrongPasswordErrback)
        return d

    def testUACPCCOk(self):
        # create
        keycard = keycards.KeycardUACPCC('user', '127.0.0.1')

        # send
        d = self.wrapper.remote_login(keycard, None,
            'twisted.spread.pb.IPerspective')

        def uacpccOkCallback(keycard):
            self.assertEquals(keycard.state, keycards.REQUESTING)
            # respond to challenge
            keycard.setPassword('test')
            d = self.wrapper.remote_login(keycard, None,
                'twisted.spread.pb.IPerspective')

            def uacpccOkCallback2(result):
                self.assert_(isinstance(result, tpb.AsReferenceable))
                return result
            d.addCallback(uacpccOkCallback2)
            return d

        d.addCallback(uacpccOkCallback)
        return d

    def testUACPCCWrongUser(self):
        # create
        keycard = keycards.KeycardUACPCC('wronguser', '127.0.0.1')

        # send
        d = self.wrapper.remote_login(keycard, "avatarId",
            'twisted.spread.pb.IPerspective')

        def uacpccWrongUserCallback(keycard):
            self.assertEquals(keycard.state, keycards.REQUESTING)
            # respond to challenge
            keycard.setPassword('test')
            d = self.wrapper.remote_login(keycard, "avatarId",
                'twisted.spread.pb.IPerspective')

            def uacpccWrongUserErrback(failure):
                self.assert_(isinstance(failure.type(),
                    errors.NotAuthenticatedError))
                return True
            d.addErrback(uacpccWrongUserErrback)
            return d

        d.addCallback(uacpccWrongUserCallback)
        return d

    def testUACPCCWrongPassword(self):
        # create
        keycard = keycards.KeycardUACPCC('user', '127.0.0.1')

        # send
        d = self.wrapper.remote_login(keycard, "avatarId",
            'twisted.spread.pb.IPerspective')

        def uacpccWrongPasswordCallback(keycard):
            self.assertEquals(keycard.state, keycards.REQUESTING)
            # respond to challenge
            keycard.setPassword('wrong')
            d = self.wrapper.remote_login(keycard, "avatarId",
                'twisted.spread.pb.IPerspective')

            def uacpccWrongPasswordErrback(failure):
                self.assert_(isinstance(failure.type(),
                    errors.NotAuthenticatedError))
                return True
            d.addErrback(uacpccWrongPasswordErrback)
            return d

        d.addCallback(uacpccWrongPasswordCallback)
        return d

    def testUACPCCTamperWithChallenge(self):
        # create challenger
        keycard = keycards.KeycardUACPCC('user', '127.0.0.1')
        self.assert_(keycard)
        self.assertEquals(keycard.state, keycards.REQUESTING)

        # submit for auth
        d = self.wrapper.remote_login(keycard, "avatarId",
            'twisted.spread.pb.IPerspective')

        def uacpccTamperCallback(keycard):
            self.assertEquals(keycard.state, keycards.REQUESTING)

            # mess with challenge, respond to challenge and resubmit
            keycard.challenge = "I am a h4x0r"
            keycard.setPassword('test')
            d = self.wrapper.remote_login(keycard, "avatarId",
                'twisted.spread.pb.IPerspective')

            def uacpccTamperErrback(failure):
                self.assert_(isinstance(failure.type(),
                    errors.NotAuthenticatedError))
            d.addErrback(uacpccTamperErrback)
            return d

        d.addCallback(uacpccTamperCallback)
        return d


class Test_FPortalRoot(testsuite.TestCase):

    def setUp(self):
        self.bouncerPortal = fportal.BouncerPortal(FakeFRealm(), 'bouncer')
        self.root = pb._FPortalRoot(self.bouncerPortal)

    def testRootObject(self):
        root = self.root.rootObject('a')
        self.failUnless(isinstance(root, pb._BouncerWrapper))
        self.assertEquals(root.broker, 'a')


class TestAuthenticator(testsuite.TestCase):

    def testIssueNoInfo(self):
        # not setting any useful auth info on the authenticator does not
        # allow us to issue a keycard
        a = pb.Authenticator(username="tarzan")
        d = a.issue([
            "flumotion.common.keycards.KeycardUACPP", ])
        d.addCallback(lambda r: self.failIf(r))
        return d

    def testIssueUACPP(self):
        # our authenticator by default only does challenge-based keycards
        a = pb.Authenticator(username="tarzan", password="jane",
            address="localhost")
        d = a.issue([
            "flumotion.common.keycards.KeycardUACPP", ])
        d.addCallback(lambda r: self.failIf(r))

    def testIssueUACPCC(self):
        a = pb.Authenticator(username="tarzan", password="jane",
            address="localhost")
        d = a.issue([
            "flumotion.common.keycards.KeycardUACPCC", ])
        d.addCallback(lambda r: self.failUnless(isinstance(r,
            keycards.KeycardUACPCC)))
        return d

# time for the big kahuna
# base class so we can use different bouncers


class Test_FPBClientFactory(testsuite.TestCase):

    def setUp(self):
        self.realm = FakeFRealm()
        self.bouncer = self.bouncerClass(self.bouncerConf)
        self.portal = fportal.BouncerPortal(self.realm, self.bouncer)
        self.serverFactory = tpb.PBServerFactory(self.portal,
            unsafeTracebacks=0)
        self.port = reactor.listenTCP(0, self.serverFactory,
            interface="127.0.0.1")
        self.portno = self.port.getHost().port

    def flushNotAuthenticatedError(self):
        try:
            self.flushLoggedErrors(errors.NotAuthenticatedError)
        except AttributeError:
            tlog.flushErrors(errors.NotAuthenticatedError)

    def tearDown(self):
        self.bouncer.stop()
        self.flushNotAuthenticatedError()
        self.port.stopListening()

    def clientDisconnect(self, factory, reference):
        # clean up broker by waiting on Disconnect notify
        d = defer.Deferred()
        if reference:
            reference.notifyOnDisconnect(lambda r: d.callback(None))
        factory.disconnect()
        if reference:
            return d

# test with htpasswdcrypt bouncer first


class Test_FPBClientFactoryHTPasswdCrypt(Test_FPBClientFactory):
    bouncerClass = htpasswdcrypt.HTPasswdCrypt
    bouncerConf = htpasswdcryptConf

    def testOk(self):
        factory = pb.FPBClientFactory()
        a = pb.Authenticator(username="user", password="test",
            address="127.0.0.1")

        # send
        d = factory.login(a)
        c = reactor.connectTCP("127.0.0.1", self.portno, factory)

        def OkCallback(result):
            # make sure we really used challenge/response keycard
            self.failUnless(isinstance(factory.keycard,
                                       keycards.KeycardUACPCC))
            self.assert_(isinstance(result, tpb.RemoteReference))
            return self.clientDisconnect(factory, result)

        d.addCallback(OkCallback)
        return d

    def testWrongPassword(self):
        factory = pb.FPBClientFactory()
        a = pb.Authenticator()
        a = pb.Authenticator(username="user", password="wrong",
            address="127.0.0.1")
        d = factory.login(a)

        c = reactor.connectTCP("127.0.0.1", self.portno, factory)

        log.debug("trial", "wait for result")

        def WrongPasswordErrback(failure):
            self.failUnless(isinstance(factory.keycard,
                                       keycards.KeycardUACPCC))
            # This is a CopiedFailure
            self.assert_(failure.check(
                "flumotion.common.errors.NotAuthenticatedError"))
            log.debug("trial", "got failure %r" % failure)
            c.disconnect()
            return True
        d.addErrback(WrongPasswordErrback)
        return d

# FIXME: rewrite such that we can enforce a challenger, possibly
# by setting a property on the bouncer

    def notestUACPCCOk(self):
        factory = pb.FPBClientFactory()

        # send
        d = factory.login(self.authenticator, 'MIND')
        c = reactor.connectTCP("127.0.0.1", self.portno, factory)

        def uacpccOkCallback(keycard):
            # get result
            self.assertEquals(keycard.state, keycards.REQUESTING)
            # respond to challenge
            keycard.setPassword('test')
            d = factory.login(keycard, 'MIND')
            # check if we have a remote reference

            def uacpccOkCallback2(result):
                self.assert_(isinstance(result, tpb.RemoteReference))
                return self.clientDisconnect(factory, result)
            d.addCallback(uacpccOkCallback2)
            return d

        d.addCallback(uacpccOkCallback)
        return d

    def testWrongUser(self):
        factory = pb.FPBClientFactory()

        # create
        a = pb.Authenticator(username="wronguser", password="test",
            address="127.0.0.1")

        # send
        d = factory.login(a)
        c = reactor.connectTCP("127.0.0.1", self.portno, factory)

        def WrongUserCb(keycard):
            self.fail("Should have returned NotAuthenticatedError")

        def WrongUserEb(failure):
            # find copied failure
            self.failUnless(failure.check(
                "flumotion.common.errors.NotAuthenticatedError"))
            return self.clientDisconnect(factory, None)

        d.addCallback(WrongUserCb)
        d.addErrback(WrongUserEb)

        return d

    def notestUACPCCWrongPassword(self):
        factory = pb.FPBClientFactory()

        # create
        keycard = keycards.KeycardUACPCC('user', '127.0.0.1')

        # send
        d = factory.login(keycard, 'MIND')
        c = reactor.connectTCP("127.0.0.1", self.portno, factory)

        def uacpccWrongPasswordCallback(keycard):
            self.assertEquals(keycard.state, keycards.REQUESTING)

            # respond to challenge
            keycard.setPassword('wrongpass')
            d = factory.login(keycard, 'MIND')

            def uacpccWrongPasswordErrback(failure):
                # find copied failure
                self.failUnless(failure.check(
                    "flumotion.common.errors.NotAuthenticatedError"))
                return self.clientDisconnect(factory, None)

            d.addErrback(uacpccWrongPasswordErrback)
            return d

        d.addCallback(uacpccWrongPasswordCallback)
        return d

    def notestUACPCCTamperWithChallenge(self):
        factory = pb.FPBClientFactory()

        # create
        keycard = keycards.KeycardUACPCC('user', '127.0.0.1')
        self.assert_(keycard)
        self.assertEquals(keycard.state, keycards.REQUESTING)

        # send
        d = factory.login(keycard, 'MIND')
        c = reactor.connectTCP("127.0.0.1", self.portno, factory)

        def uacpccTamperCallback(keycard):
            self.assertEquals(keycard.state, keycards.REQUESTING)

            # mess with challenge, respond to challenge and resubmit
            keycard.challenge = "I am a h4x0r"
            keycard.setPassword('test')
            d = factory.login(keycard, 'MIND')

            def uacpccTamperErrback(failure):
                # find copied failure
                self.failUnless(failure.check(
                    "flumotion.common.errors.NotAuthenticatedError"))
                return self.clientDisconnect(factory, None)

            d.addErrback(uacpccTamperErrback)
            return d
        d.addCallback(uacpccTamperCallback)
        return d

# test with sha256 bouncer


class Test_FPBClientFactorySaltSha256(Test_FPBClientFactory):
    bouncerClass = saltsha256.SaltSha256
    bouncerConf = saltsha256Conf

    def testOk(self):
        factory = pb.FPBClientFactory()
        a = pb.Authenticator(username="user", password="test",
            address="127.0.0.1")
        # send
        d = factory.login(a)
        c = reactor.connectTCP("127.0.0.1", self.portno, factory)

        def OkCallback(result):
            # make sure we really used an SHA256 challenge/response keycard
            self.failUnless(isinstance(factory.keycard,
                                       keycards.KeycardUASPCC))
            self.assert_(isinstance(result, tpb.RemoteReference))
            return self.clientDisconnect(factory, result)

        d.addCallback(OkCallback)
        return d

    def testWrongPassword(self):
        factory = pb.FPBClientFactory()
        a = pb.Authenticator(username="user", password="wrong",
            address="127.0.0.1")
        d = factory.login(a)

        c = reactor.connectTCP("127.0.0.1", self.portno, factory)

        log.debug("trial", "wait for result")

        def WrongPasswordErrback(failure):
            # make sure we really used an SHA256 challenge/response keycard
            self.failUnless(isinstance(factory.keycard,
                                       keycards.KeycardUASPCC))
            # This is a CopiedFailure
            self.assert_(failure.check(
                "flumotion.common.errors.NotAuthenticatedError"))
            log.debug("trial", "got failure %r" % failure)
            c.disconnect()
            return True
        d.addErrback(WrongPasswordErrback)
        return d

    def testWrongUser(self):
        factory = pb.FPBClientFactory()

        # create
        a = pb.Authenticator(username="wronguser", password="test",
            address="127.0.0.1")

        # send
        d = factory.login(a)
        c = reactor.connectTCP("127.0.0.1", self.portno, factory)

        def WrongUserCb(keycard):
            self.fail("Should have returned NotAuthenticatedError")

        def WrongUserEb(failure):
            # find copied failure
            self.failUnless(failure.check(
                "flumotion.common.errors.NotAuthenticatedError"))
            return self.clientDisconnect(factory, None)

        d.addCallback(WrongUserCb)
        d.addErrback(WrongUserEb)

        return d

# FIXME: do this with a fake authenticator that tampers with the challenge

    def notestUACPCCTamperWithChallenge(self):
        factory = pb.FPBClientFactory()

        # create
        keycard = keycards.KeycardUACPCC('user', '127.0.0.1')
        self.assert_(keycard)
        self.assertEquals(keycard.state, keycards.REQUESTING)

        # send
        d = factory.login(keycard, 'MIND')
        c = reactor.connectTCP("127.0.0.1", self.portno, factory)

        def uacpccTamperCallback(keycard):
            self.assertEquals(keycard.state, keycards.REQUESTING)

            # mess with challenge, respond to challenge and resubmit
            keycard.challenge = "I am a h4x0r"
            keycard.setPassword('test')
            d = factory.login(keycard, 'MIND')

            def uacpccTamperErrback(failure):
                # find copied failure
                self.failUnless(failure.check(
                    "flumotion.common.errors.NotAuthenticatedError"))
                return self.clientDisconnect(factory, None)

            d.addErrback(uacpccTamperErrback)
            return d
        d.addCallback(uacpccTamperCallback)
        return d


if __name__ == '__main__':
    unittest.main()
