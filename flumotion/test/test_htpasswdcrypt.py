# -*- Mode: Python; test-case-name: flumotion.test.test_htpasswdcrypt -*-
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

from flumotion.common import testsuite
from twisted.trial import unittest
from twisted.internet import defer

from flumotion.common import keycards
from flumotion.component.bouncers import htpasswdcrypt


bouncerconf = {'name': 'testbouncer',
               'plugs': {},
               'properties': {'data': "user:qi1Lftt0GZC0o"}}

# this is a type that should not be allowed


class TestHTPasswdCryptKeycard(testsuite.TestCase):

    def setUp(self):
        self.bouncer = htpasswdcrypt.HTPasswdCrypt(bouncerconf)

    def tearDown(self):
        self.bouncer.stop()

    def testWrongKeycardClass(self):
        keycard = keycards.Keycard()
        d = defer.maybeDeferred(self.bouncer.authenticate, keycard)

        def wrongKeycardClassCallback(result):
            self.failIf(result)
        d.addCallback(wrongKeycardClassCallback)
        return d


class TestHTPasswdCryptUACPP(testsuite.TestCase):

    def setUp(self):
        self.bouncer = htpasswdcrypt.HTPasswdCrypt(bouncerconf)

    def tearDown(self):
        self.bouncer.stop()
        del self.bouncer

    def testInit(self):
        self.assert_(self.bouncer._checker)

    def testOk(self):
        keycard = keycards.KeycardUACPP('user', 'test', '127.0.0.1')
        d = defer.maybeDeferred(self.bouncer.authenticate, keycard)

        def okCallback(result):
            self.assertEquals(result.state, keycards.AUTHENTICATED)
        d.addCallback(okCallback)
        return d

    def testWrongUser(self):
        keycard = keycards.KeycardUACPP('wronguser', 'test', '127.0.0.1')
        d = defer.maybeDeferred(self.bouncer.authenticate, keycard)

        def wrongUserCallback(result):
            self.failIf(result)
        d.addCallback(wrongUserCallback)
        return d

    def testWrongPassword(self):
        keycard = keycards.KeycardUACPP('test', 'wrongpass', '127.0.0.1')
        d = defer.maybeDeferred(self.bouncer.authenticate, keycard)

        def wrongPasswordCallback(result):
            self.assertEquals(result, None)
        d.addCallback(wrongPasswordCallback)
        return d


class TestHTPasswdCryptUACPCC(testsuite.TestCase):

    def setUp(self):
        self.bouncer = htpasswdcrypt.HTPasswdCrypt(bouncerconf)

    def tearDown(self):
        self.bouncer.stop()

    def testOk(self):
        # create challenger
        keycard = keycards.KeycardUACPCC('user', '127.0.0.1')
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
        keycard = keycards.KeycardUACPCC('user', '127.0.0.1')
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
