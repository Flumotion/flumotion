# -*- Mode: Python; test-case-name: flumotion.test.test_credentials -*-
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

"""
Flumotion Twisted credentials
"""

import md5

import random

from flumotion.common import log
from twisted.cred import credentials
from zope.interface import implements

try:
    import crypt
except ImportError:
    from flumotion.extern import unixcrypt as crypt

__version__ = "$Rev$"


class Username:
    """
    I am your average username and password credentials.
    """
    implements(credentials.IUsernamePassword)
    def __init__(self, username, password=''):
        self.username = username
        self.password = password

    def checkPassword(self, password):
        return password == self.password

IUsernamePassword = credentials.IUsernamePassword

IUsernameHashedPassword = credentials.IUsernameHashedPassword

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

    implements(IUsernameCryptPassword)
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

    implements(IUsernameCryptPassword)
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

def dataToHex(data):
    """
    Take a string of bytes, and return a string of two-digit hex values.
    """
    l = []
    for c in data:
        l.append("%02x" % ord(c))
    return "".join(l)

# copied from twisted.spread.pb.challenge()
def cryptChallenge():
    """
    I return some random data.
    """
    crap = ''
    for x in range(random.randrange(15, 25)):
        crap = crap + chr(random.randint(65, 90) + x - x) # pychecker madness
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

    implements(IUsernameCryptPassword)

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

class IToken(credentials.ICredentials):
    """I encapsulate a token.

    This credential is used when a token is received from the
    party requesting authentication.

    @type token: C{str}
    @ivar token: The token associated with these credentials.
    """

class Token:
    implements(IToken)

    def __init__(self, token):
        self.token = token

class IUsernameSha256Password(credentials.ICredentials):
    """
    I encapsulate a username and check SHA-256 passwords.

    This credential interface is used when a SHA-256 algorithm is used
    on the password by the party requesting authentication..
    CredentialCheckers which check this kind of credential must store
    the passwords in plaintext or SHA-256 form.

    @type username: C{str}
    @ivar username: The username associated with these credentials.
    """

    def checkSha256Password(self, sha256Password):
        """
        Validate these credentials against the correct SHA-256 password.

        @param sha256Password: The correct SHA-256 password against which to
        check.

        @return: a deferred which becomes, or a boolean indicating if the
        password matches.
        """

# our Sha256 passwords are salted;
# ie the password string is salt + dataToHex(SHA256 digest(salt + password))
class UsernameSha256PasswordCryptChallenger:
    """
    I take a username.

    Authenticator will give me a salt and challenge me.
    Requester will respond to the challenge.
    At that point I'm ready to be used by a checker.
    The response function used is
    L{flumotion.twisted.credentials.cryptRespond()}

    I implement IUsernameSha256Password.
    """

    implements(IUsernameSha256Password)

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
        from Crypto.Hash import SHA256
        hasher = SHA256.new()
        hasher.update(self.salt)
        hasher.update(password)
        sha256Password = self.salt + dataToHex(hasher.digest())
        self.response = cryptRespond(self.challenge, sha256Password)

    def checkSha256Password(self, sha256Password):
        """
        Check credentials against the given sha256Password.
        """
        if not self.response:
            return False

        expected = cryptRespond(self.challenge, sha256Password)
        return self.response == expected

class HTTPDigestChallenger(log.Loggable):
    _algorithm = "MD5" # MD5-sess also supported

    def __init__(self, username):
        self.username = username
        self.nonce = None
        self.method = None
        self.uri = None

        self.qop = None # If non-None, the next two must be set
        self.cnonce = None
        self.ncvalue = None

        self.response = None

    def checkHTTPDigestResponse(self, ha1):
        expectedResponse = self._calculateRequestDigest(
            self.username, ha1, self.nonce, self.cnonce,
            self.method, self.uri, self.ncvalue, self.qop)

        self.debug(
            "Attempting to check calculated response %s against "
            " provided response %r", expectedResponse, self.response)
        self.debug("Username %s, nonce %s, method %s, uri %s, qop %s, "
                   "cnonce %s, ncvalue %s", self.username, self.nonce,
                   self.method, self.uri, self.qop, self.cnonce,
                   self.ncvalue)
        self.debug("Using H(A1): %s", ha1)

        if not self.response:
            return False

        return self.response == expectedResponse

    def _calculateHA1(self, ha1, nonce, cnonce):
        """
        Calculate H(A1) as from specification (RFC2617) section 3.2.2, given
        the initial hash H(username:realm:passwd), hex-encoded.

        This basically applies the second-level hashing for MD5-sess, if
        required.
        """
        if self._algorithm == 'MD5':
            return ha1
        elif self._algorithm == 'MD5-sess':
            HA1 = ha1.decode('hex')

            m = md5.md5()
            m.update(HA1)
            m.update(':')
            m.update(nonce)
            m.update(':')
            m.update(cnonce)
            return m.digest().encode('hex')
        else:
            raise NotImplementedError("Unimplemented algorithm")

    def _calculateHA2(self, method, uri):
        # We don't support auth-int, otherwise we'd optionally need to do
        # some more work here
        m = md5.md5()
        m.update(method)
        m.update(':')
        m.update(uri)
        return m.digest().encode('hex')

    def _calculateRequestDigest(self, username, ha1, nonce, cnonce, method,
            uri, ncvalue, qop):
        HA1 = self._calculateHA1(ha1, nonce, cnonce)
        HA2 = self._calculateHA2(method, uri)

        m = md5.md5()
        m.update(HA1)
        m.update(':')
        m.update(nonce)
        if qop:
            m.update(':')
            m.update(ncvalue)
            m.update(':')
            m.update(cnonce)
            m.update(':')
            m.update(qop) # Must be 'auth', others not supported
        m.update(':')
        m.update(HA2)

        return m.digest().encode('hex')
