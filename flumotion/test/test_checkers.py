# -*- Mode: Python; test-case-name: flumotion.test.test_checkers -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# Flumotion - a streaming media server
# Copyright (C) 2004,2005 Fluendo, S.L. (www.fluendo.com). All rights reserved.

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
