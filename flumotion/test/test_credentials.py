# -*- Mode: Python; test-case-name: flumotion.test.test_credentials -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# flumotion/test/test_credentials.py:
# regression test for flumotion.twisted.credentials
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

from flumotion.twisted import credentials

# use some shorter names
CredCrypt = credentials.UsernameCryptPasswordCrypt
CredPlaintext = credentials.UsernameCryptPasswordPlaintext

class TestUsernameCryptPasswordCrypt(unittest.TestCase):
    def testWithPlaintext(self):
        cred = CredCrypt('user')
        cred.setPasswordSalt('test', 'qi')
        assert cred.checkCryptPassword('qi1Lftt0GZC0o')
        assert not cred.checkCryptPassword('boohoowrong')

    def testWithPlaintextWrongSalt(self):
        cred = CredCrypt('user')
        cred.setPasswordSalt('test', 'as')
        assert not cred.checkCryptPassword('qi1Lftt0GZC0o')
        assert not cred.checkCryptPassword('boohoowrong')

    def testWithPlaintextWrongPassword(self):
        cred = CredCrypt('user')
        cred.setPasswordSalt('wrong', 'qi')
        assert not cred.checkCryptPassword('qi1Lftt0GZC0o')
        assert not cred.checkCryptPassword('boohoowrong')

    def testWithCrypt(self):
        # sort of silly, since this does a straight comparison, but hey
        cred = CredCrypt('user', 'qi1Lftt0GZC0o') # password is test
        assert cred.checkCryptPassword('qi1Lftt0GZC0o')
        assert not cred.checkCryptPassword('boohoowrong')

class TestUsernameCryptPasswordPlaintext(unittest.TestCase):
    def testWithPlaintext(self):
        cred = CredPlaintext('user', 'test')
        assert cred.checkCryptPassword('qi1Lftt0GZC0o')
        assert not cred.checkCryptPassword('boohoowrong')

    def testWithPlaintextWrongPassword(self):
        cred = CredPlaintext('user', 'tes')
        assert not cred.checkCryptPassword('qi1Lftt0GZC0o')
        assert not cred.checkCryptPassword('boohoowrong')

if __name__ == '__main__':
     unittest.main()
