# -*- Mode: Python; test-case-name: flumotion.test.test_credentials -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# flumotion/twisted/credentials.py: credential objects;
# see twisted.cred.credentials
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

import crypt
import md5
import random

from flumotion.common import log
from twisted.cred import credentials

class Username:
    __implements__ = credentials.IUsernamePassword,
    def __init__(self, username, password=''):
        self.username = username
        self.password = password

class IUsernameCryptPassword(credentials.ICredentials):
    """
    I encapsulate a username and check crypted passwords.

    This credential interface is used when a crypt password is received
    from the party requesting authentication.
    CredentialCheckers which check this kind of credential must store
    the passwords in plaintext or crypt form.

    @type username: C{str}
    @ivar username: The username associated with these credentials.
    """

    def checkCryptPassword(self, cryptPassword):
        """
        Validate these credentials against the correct crypt password.
                                                                                
        @param cryptPassword: The correct, crypt password against which to
        check.
                                                                                
        @return: a deferred which becomes, or a boolean indicating if the
        password matches.
        """

class UsernameCryptPasswordPlaintext:
    """
    I take a username and a plaintext password.
    I implement IUsernameCryptPassword.
    """
    
    __implements__ = IUsernameCryptPassword
    def __init__(self, username, password):
        self.username = username
        self.password = password

    def checkCryptPassword(self, cryptPassword):
        """Check credentials against the given cryptPassword."""
        salt = cryptPassword[:2]
        encrypted = crypt.crypt(self.password, salt)
        return encrypted == cryptPassword

class UsernameCryptPasswordCrypt:
    """
    I take a username and a crypt password.
    When using me you should make sure the password was crypted with the
    correct salt (which is stored in the crypt password backend of whatever
    checker you use); otherwise your password may be a valid crypt, but
    with a different salt.
    I implement IUsernameCryptPassword.
    """
    
    __implements__ = IUsernameCryptPassword
    def __init__(self, username, cryptPassword=None):
        self.username = username
        self.cryptPassword = cryptPassword

    def setPasswordSalt(self, password, salt):
        """
        Given the plaintext password and the salt,
        set the correct cryptPassword.
        """
        assert len(salt) == 2

        self.cryptPassword = crypt.crypt(password, salt)

    def checkCryptPassword(self, cryptPassword):
        """
        Check credentials against the given cryptPassword.
        """
        return self.cryptPassword == cryptPassword

def cryptRespond(challenge, cryptPassword):
    """
    Respond to a given crypt challenge with our cryptPassword.
    """
    import md5
    md = md5.new()
    md.update(cryptPassword)
    md.update(challenge)
    return md.digest()

# copied from twisted.spread.pb.challenge()
def cryptChallenge():
    """
    I return some random data.
    """
    crap = ''
    for x in range(random.randrange(15,25)):
        crap = crap + chr(random.randint(65,90))
    crap = md5.new(crap).digest()
    return crap
    
class UsernameCryptPasswordCryptChallenger:
    """
    I take a username.
    
    Authenticator will give me a salt and challenge me.
    Requester will respond to the challenge.
    At that point I'm ready to be used by a checker.
    The response function used is
    L{flumotion.twisted.credentials.cryptRespond()}

    I implement IUsernameCryptPassword.
    """
    
    __implements__ = IUsernameCryptPassword

    def __init__(self, username):
        self.username = username
        self.salt = None       # set by authenticator
        self.challenge = None  # set by authenticator
        self.response = None   # set by requester

    def setPassword(self, password):
        """
        I encode a given plaintext password using the salt, and respond
        to the challenge.
        """
        assert self.salt
        assert self.challenge
        assert len(self.salt) == 2
        cryptPassword = crypt.crypt(password, self.salt)
        self.response = cryptRespond(self.challenge, cryptPassword)

    def checkCryptPassword(self, cryptPassword):
        """
        Check credentials against the given cryptPassword.
        """
        if not self.response:
            return False

        expected = cryptRespond(self.challenge, cryptPassword)
        return self.response == expected
