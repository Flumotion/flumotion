# -*- Mode: Python; test-case-name: flumotion.test.test_htpasswdcrypt -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# flumotion/test/test_htpasswordcrypt.py: regression test for htpasswdcrypt
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
from twisted.internet import defer

from flumotion.common import keycards
from flumotion.component.bouncers import htpasswdcrypt

# this is a type that should not be allowed
class TestHTPasswdCryptKeycard(unittest.TestCase):
    def setUp(self):
        data = """user:qi1Lftt0GZC0o"""
        self.bouncer = htpasswdcrypt.HTPasswdCrypt('testbouncer', None, data)

    def testWrongKeycardClass(self):
        keycard = keycards.Keycard()
        d = defer.maybeDeferred(self.bouncer.authenticate, keycard)
        result = unittest.deferredResult(d)
        self.failIf(result)

class TestHTPasswdCryptUACPP(unittest.TestCase):
    def setUp(self):
        data = """user:qi1Lftt0GZC0o"""
        self.bouncer = htpasswdcrypt.HTPasswdCrypt('testbouncer', None, data)
        
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
        data = """user:qi1Lftt0GZC0o"""
        self.bouncer = htpasswdcrypt.HTPasswdCrypt('testbouncer', None, data)

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
