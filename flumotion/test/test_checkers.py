# -*- Mode: Python; test-case-name: flumotion.test.test_checkers -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# flumotion/test/test_checkers.py:
# regression test for flumotion.twisted.checkers
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

from twisted.cred import error

from flumotion.twisted import credentials, checkers

# Use some shorter names
CredPlaintext = credentials.UsernameCryptPasswordPlaintext
CredCrypt = credentials.UsernameCryptPasswordCrypt

class TestCryptCheckerInit(unittest.TestCase):
    def setUp(self):
        self.checker = checkers.CryptChecker(user='qi1Lftt0GZC0o')

    def testCredPlaintext(self):
        cred = CredPlaintext('user', 'test')
        d = self.checker.requestAvatarId(cred)
        assert unittest.deferredResult(d) == 'user'

class TestCryptCheckerAddUser(unittest.TestCase):
    def setUp(self):
        username = 'user'
        cryptPassword = crypt.crypt('test', 'qi')
        self.checker = checkers.CryptChecker()
        self.checker.addUser(username, cryptPassword)

    def testCredPlaintext(self):
        cred = CredPlaintext('user', 'test')
        d = self.checker.requestAvatarId(cred)
        assert unittest.deferredResult(d) == 'user'

    def testCredPlaintextWrongPassword(self):
        cred = CredPlaintext('user', 'tes')
        d = self.checker.requestAvatarId(cred)
        failure = unittest.deferredError(d)
        failure.trap(error.UnauthorizedLogin)

    def testCredPlaintextWrongUser(self):
        cred = CredPlaintext('wrong', 'test')
        d = self.checker.requestAvatarId(cred)
        failure = unittest.deferredError(d)
        failure.trap(error.UnauthorizedLogin)

    def testCredCrypt(self):
        crypted = crypt.crypt('test', 'qi')
        assert crypted == 'qi1Lftt0GZC0o'
        cred = CredCrypt('user', crypted)
        d = self.checker.requestAvatarId(cred)
        assert unittest.deferredResult(d) == 'user'

    def testCredCryptWrongSalt(self):
        crypted = crypt.crypt('test', 'aa')
        cred = CredCrypt('user', crypted)
        d = self.checker.requestAvatarId(cred)
        failure = unittest.deferredError(d)
        failure.trap(error.UnauthorizedLogin)

    def testCredCryptWrongPassword(self):
        crypted = crypt.crypt('wrong', 'qi')
        cred = CredCrypt('user', crypted)
        d = self.checker.requestAvatarId(cred)
        failure = unittest.deferredError(d)
        failure.trap(error.UnauthorizedLogin)

    def testCredCryptWrongUser(self):
        crypted = crypt.crypt('test', 'qi')
        cred = CredCrypt('wronguser', crypted)
        d = self.checker.requestAvatarId(cred)
        failure = unittest.deferredError(d)
        failure.trap(error.UnauthorizedLogin)

if __name__ == '__main__':
     unittest.main()
