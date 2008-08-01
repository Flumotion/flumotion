# -*- Mode: Python; test-case-name: flumotion.test.test_checkers -*-
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

import crypt

from twisted.cred import credentials as tcredentials
from flumotion.twisted import credentials, checkers
from flumotion.common import errors



# Use some shorter names
CredPlaintext = credentials.UsernameCryptPasswordPlaintext
CredCrypt = credentials.UsernameCryptPasswordCrypt


class TestFlexibleWithPassword(testsuite.TestCase):

    def setUp(self):
        self.checker = checkers.FlexibleCredentialsChecker(user='test')

    def testCredPlaintextCorrect(self):

        def credPlaintextCorrectCallback(result):
            self.assertEquals(result, 'user')
        cred = tcredentials.UsernamePassword('user', 'test')
        d = self.checker.requestAvatarId(cred)
        d.addCallback(credPlaintextCorrectCallback)
        return d

    def testCredPlaintextCorrectWithId(self):

        def credPlaintextCorrectWithIdCallback(result):
            self.assertEquals(result, 'requested')
            return True
        cred = tcredentials.UsernamePassword('user', 'test')
        cred.avatarId = "requested"
        d = self.checker.requestAvatarId(cred)
        d.addCallback(credPlaintextCorrectWithIdCallback)
        return d

    def testCredPlaintextWrong(self):

        def credPlaintextWrongErrback(failure):
            self.assert_(isinstance(failure.type(),
                                    errors.NotAuthenticatedError))
            return True
        cred = tcredentials.UsernamePassword('user', 'wrong')
        d = self.checker.requestAvatarId(cred)
        d.addErrback(credPlaintextWrongErrback)
        return d


class TestFlexibleWithoutPassword(testsuite.TestCase):

    def setUp(self):
        self.checker = checkers.FlexibleCredentialsChecker(user='test')
        self.checker.allowPasswordless(True)

    def testCredPlaintextCorrect(self):

        def credPlaintextCorrectCallback(result):
            self.assertEquals(result, 'user')
            return True
        cred = tcredentials.UsernamePassword('user', '')
        d = self.checker.requestAvatarId(cred)
        d.addCallback(credPlaintextCorrectCallback)
        return d

    def testCredPlaintextCorrectWithId(self):

        def credPlaintextCorrectWithIdCallback(result):
            self.assertEquals(result, 'requested')
            return True
        cred = tcredentials.UsernamePassword('user', '')
        cred.avatarId = "requested"
        d = self.checker.requestAvatarId(cred)
        d.addCallback(credPlaintextCorrectWithIdCallback)
        return d


class TestCryptCheckerInit(testsuite.TestCase):

    def setUp(self):
        self.checker = checkers.CryptChecker(user='qi1Lftt0GZC0o')

    def testCredPlaintext(self):

        def credPlaintextCallback(result):
            self.assertEquals(result, 'user')
            return True
        cred = CredPlaintext('user', 'test')
        d = self.checker.requestAvatarId(cred)
        d.addCallback(credPlaintextCallback)
        return d


class TestCryptCheckerAddUser(testsuite.TestCase):

    def setUp(self):
        username = 'user'
        cryptPassword = crypt.crypt('test', 'qi')
        self.checker = checkers.CryptChecker()
        self.checker.addUser(username, cryptPassword)

    def testCredPlaintext(self):

        def credPlaintextCallback(result):
            self.assertEquals(result, 'user')
            return True
        cred = CredPlaintext('user', 'test')
        d = self.checker.requestAvatarId(cred)
        d.addCallback(credPlaintextCallback)
        return d

    def testCredPlaintextWrongPassword(self):

        def credPlaintextWrongPasswordErrback(failure):
            self.assert_(isinstance(failure.type(),
                                    errors.NotAuthenticatedError))
            return True
        cred = CredPlaintext('user', 'tes')
        d = self.checker.requestAvatarId(cred)
        d.addErrback(credPlaintextWrongPasswordErrback)
        return d

    def testCredPlaintextWrongUser(self):

        def credPlaintextWrongUserErrback(failure):
            self.assert_(isinstance(failure.type(),
                                    errors.NotAuthenticatedError))
            return True
        cred = CredPlaintext('wrong', 'test')
        d = self.checker.requestAvatarId(cred)
        d.addErrback(credPlaintextWrongUserErrback)
        return d

    def testCredCrypt(self):

        def credCryptCallback(result):
            self.assertEquals(result, 'user')
            return True
        crypted = crypt.crypt('test', 'qi')
        self.assertEquals(crypted, 'qi1Lftt0GZC0o')
        cred = CredCrypt('user', crypted)
        d = self.checker.requestAvatarId(cred)
        d.addCallback(credCryptCallback)
        return d

    def testCredCryptWrongSalt(self):

        def credCryptWrongSaltErrback(failure):
            self.assert_(isinstance(failure.type(),
                                    errors.NotAuthenticatedError))
            return True
        crypted = crypt.crypt('test', 'aa')
        cred = CredCrypt('user', crypted)
        d = self.checker.requestAvatarId(cred)
        d.addErrback(credCryptWrongSaltErrback)
        return d

    def testCredCryptWrongPassword(self):

        def credCryptWrongPasswordErrback(failure):
            self.assert_(isinstance(failure.type(),
                                    errors.NotAuthenticatedError))
            return True
        crypted = crypt.crypt('wrong', 'qi')
        cred = CredCrypt('user', crypted)
        d = self.checker.requestAvatarId(cred)
        d.addErrback(credCryptWrongPasswordErrback)
        return d

    def testCredCryptWrongUser(self):

        def credCryptWrongUserErrback(failure):
            self.assert_(isinstance(failure.type(),
                                    errors.NotAuthenticatedError))
            return True
        crypted = crypt.crypt('test', 'qi')
        cred = CredCrypt('wronguser', crypted)
        d = self.checker.requestAvatarId(cred)
        d.addErrback(credCryptWrongUserErrback)
        return d

if __name__ == '__main__':
    unittest.main()
