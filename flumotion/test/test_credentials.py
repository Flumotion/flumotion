# -*- Mode: Python; test-case-name: flumotion.test.test_credentials -*-
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

from flumotion.twisted import credentials

# use some shorter names
CredCrypt = credentials.UsernameCryptPasswordCrypt
CredPlaintext = credentials.UsernameCryptPasswordPlaintext
CredUCPCC = credentials.UsernameCryptPasswordCryptChallenger

class TestUsername(unittest.TestCase):
    def testWithPlaintext(self):
        cred = credentials.Username('user', 'test')
        self.failUnless(cred.checkPassword('test'))
        self.failIf(cred.checkPassword('boohoowrong'))

    def testWithPlaintextWrongPassword(self):
        cred = CredPlaintext('user', 'tes')
        self.failIf(cred.checkCryptPassword('qi1Lftt0GZC0o'))
        self.failIf(cred.checkCryptPassword('boohoowrong'))

class TestUsernameCryptPasswordCrypt(unittest.TestCase):
    def testWithPlaintext(self):
        cred = CredCrypt('user')
        cred.setPasswordSalt('test', 'qi')
        self.assert_(cred.checkCryptPassword('qi1Lftt0GZC0o'))
        self.failIf(cred.checkCryptPassword('boohoowrong'))

    def testWithPlaintextWrongSalt(self):
        cred = CredCrypt('user')
        cred.setPasswordSalt('test', 'as')
        self.failIf(cred.checkCryptPassword('qi1Lftt0GZC0o'))
        self.failIf(cred.checkCryptPassword('boohoowrong'))

    def testWithPlaintextWrongPassword(self):
        cred = CredCrypt('user')
        cred.setPasswordSalt('wrong', 'qi')
        self.failIf(cred.checkCryptPassword('qi1Lftt0GZC0o'))
        self.failIf(cred.checkCryptPassword('boohoowrong'))

    def testWithCrypt(self):
        # sort of silly, since this does a straight comparison, but hey
        cred = CredCrypt('user', 'qi1Lftt0GZC0o') # password is test
        self.assert_(cred.checkCryptPassword('qi1Lftt0GZC0o'))
        self.failIf(cred.checkCryptPassword('boohoowrong'))

class TestUsernameCryptPasswordPlaintext(unittest.TestCase):
    def testWithPlaintext(self):
        cred = CredPlaintext('user', 'test')
        self.assert_(cred.checkCryptPassword('qi1Lftt0GZC0o'))
        self.failIf(cred.checkCryptPassword('boohoowrong'))

    def testWithPlaintextWrongPassword(self):
        cred = CredPlaintext('user', 'tes')
        self.failIf(cred.checkCryptPassword('qi1Lftt0GZC0o'))
        self.failIf(cred.checkCryptPassword('boohoowrong'))

class TestUsernameCryptPasswordCryptChallenger(unittest.TestCase):
    def testWithPlaintext(self):
        cred = CredUCPCC('user')

        # authenticator sets salt and challenge
        cred.salt = 'qi'
        cred.challenge = credentials.cryptChallenge()

        # not responding should fail
        self.failIf(cred.checkCryptPassword('qi1Lftt0GZC0o'))

        # requester responds
        cred.setPassword('test')

        # authenticator verifies against the known good password
        self.assert_(cred.checkCryptPassword('qi1Lftt0GZC0o'))
        self.failIf(cred.checkCryptPassword('boohoowrong'))

    def testWithPlaintextWrongPassword(self):
        cred = CredUCPCC('user')

        # authenticator sets salt and challenge
        cred.salt = 'qi'
        cred.challenge = credentials.cryptChallenge()

        # requester responds with wrong password
        cred.setPassword('wrong')

        # authenticator verifies against the known good password
        self.failIf(cred.checkCryptPassword('qi1Lftt0GZC0o'))
        self.failIf(cred.checkCryptPassword('boohoowrong'))

if __name__ == '__main__':
     unittest.main()
