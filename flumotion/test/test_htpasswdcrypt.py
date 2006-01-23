# -*- Mode: Python; test-case-name: flumotion.test.test_htpasswdcrypt -*-
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
from twisted.internet import defer

from flumotion.common import keycards
from flumotion.component.bouncers import htpasswdcrypt

bouncerconf = {'name': 'testbouncer',
               'properties': {'data': "user:qi1Lftt0GZC0o"}}

# this is a type that should not be allowed
class TestHTPasswdCryptKeycard(unittest.TestCase):
    def setUp(self):
        self.bouncer = htpasswdcrypt.HTPasswdCrypt()

    def testWrongKeycardClass(self):
        keycard = keycards.Keycard()
        d = defer.maybeDeferred(self.bouncer.authenticate, keycard)
        result = unittest.deferredResult(d)
        self.failIf(result)

class TestHTPasswdCryptUACPP(unittest.TestCase):
    def setUp(self):
        self.bouncer = htpasswdcrypt.HTPasswdCrypt()
        self.bouncer.setup(bouncerconf)

    def tearDown(self):
        del self.bouncer
        
    def testInit(self):
        self.assert_(self.bouncer._checker)
        
    def testOk(self):
        keycard = keycards.KeycardUACPP('user', 'test', '127.0.0.1')
        d = defer.maybeDeferred(self.bouncer.authenticate, keycard)
        result = unittest.deferredResult(d)
        self.assertEquals(result.state, keycards.AUTHENTICATED)

    def testWrongUser(self):
        keycard = keycards.KeycardUACPP('wronguser', 'test', '127.0.0.1')
        d = defer.maybeDeferred(self.bouncer.authenticate, keycard)
        result = unittest.deferredResult(d)
        self.failIf(result)

    def testWrongPassword(self):
        keycard = keycards.KeycardUACPP('test', 'wrongpass', '127.0.0.1')
        d = defer.maybeDeferred(self.bouncer.authenticate, keycard)
        result = unittest.deferredResult(d)
        self.assertEquals(result, None)

class TestHTPasswdCryptUACPCC(unittest.TestCase):
    def setUp(self):
        self.bouncer = htpasswdcrypt.HTPasswdCrypt()
        self.bouncer.setup(bouncerconf)

    def testOk(self):
        # create challenger
        keycard = keycards.KeycardUACPCC('user', '127.0.0.1')
        self.assert_(keycard)
        self.assertEquals(keycard.state, keycards.REQUESTING)

        # submit for auth
        d = defer.maybeDeferred(self.bouncer.authenticate, keycard)
        result = unittest.deferredResult(d)
        self.assertEquals(result.state, keycards.REQUESTING)

        # respond to challenge and resubmit
        result.setPassword('test')
        d = defer.maybeDeferred(self.bouncer.authenticate, keycard)
        result = unittest.deferredResult(d)
        self.assertEquals(result.state, keycards.AUTHENTICATED)

    def testTamperWithChallenge(self):
        # create challenger
        keycard = keycards.KeycardUACPCC('user', '127.0.0.1')
        self.assert_(keycard)
        self.assertEquals(keycard.state, keycards.REQUESTING)

        # submit for auth
        d = defer.maybeDeferred(self.bouncer.authenticate, keycard)
        result = unittest.deferredResult(d)
        self.assertEquals(result.state, keycards.REQUESTING)

        # mess with challenge, respond to challenge and resubmit
        result.challenge = "I am a h4x0r"
        result.setPassword('test')
        d = defer.maybeDeferred(self.bouncer.authenticate, keycard)
        result = unittest.deferredResult(d)
        self.failIf(result)

if __name__ == '__main__':
    unittest.main()
