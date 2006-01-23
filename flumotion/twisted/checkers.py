# -*- Mode: Python; test-case-name: flumotion.test.test_checkers -*-
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

"""
Flumotion Twisted credential checkers
"""

from twisted.cred import checkers, error
from twisted.internet import defer
from twisted.python import failure

from flumotion.common import log
from flumotion.twisted import credentials

# FIXME: give the manager's bouncer's checker to the flexcredchecker,
# and forward to it
parent = checkers.InMemoryUsernamePasswordDatabaseDontUse
class FlexibleCredentialsChecker(parent, log.Loggable):
    """
    I am an in-memory username/password credentials checker that also
    allows anonymous logins if instructed to do so.
    """
    logCategory = 'credchecker'
    def __init__(self, **users):
        parent.__init__(self, **users)
        self._passwordless = False # do we allow passwordless logins ?
        
    def allowPasswordless(self, wellDoWeQuestionMark):
        self._passwordless = wellDoWeQuestionMark
                         
    ### ICredentialsChecker interface methods
    def requestAvatarId(self, credentials):
        avatarId = getattr(credentials, 'avatarId', None)

        d = None
        if not self._passwordless:
            self.debug('authenticating user %s' % credentials.username)
            d = parent.requestAvatarId(self, credentials)
        else:
            self.debug('allowing passwordless login for user %s' %
                credentials.username)
            d = defer.succeed(credentials.username)

        d.addCallback(self._requestCallback, avatarId)
        return d

    def _requestCallback(self, result, avatarId):
        if avatarId:
            self.debug("assigned requested avatarId %s" % avatarId)
            return avatarId
        else:
            self.debug("assigned avatarId %s" % result)
            return result

class CryptChecker(log.Loggable):
    """
    I check credentials using a crypt-based backend.
    """
    __implements__ = (checkers.ICredentialsChecker, )
    credentialInterfaces = (credentials.IUsernameCryptPassword, )

    logCategory = 'cryptchecker'

    def __init__(self, **users):
        self.users = users

    def addUser(self, username, cryptPassword):
        """
        Add the given username and password.

        @param username:      name of the user to add
        @type  username:      string
        @param cryptPassword: the crypted password for this user
        @type  cryptPassword: string
        """
        self.debug('added user %s' % username)
        self.users[username] = cryptPassword

    def _cbCryptPasswordMatch(self, matched, username):
        if matched:
            self.debug('user %s authenticated' % username)
            return username
        else:
            self.debug('user %s refused, password not matched' % username)
            return failure.Failure(error.UnauthorizedLogin())

    ### ICredentialsChecker methods
    def requestAvatarId(self, credentials):
        if credentials.username in self.users:
            return defer.maybeDeferred(
                credentials.checkCryptPassword,
                self.users[credentials.username]).addCallback(
                self._cbCryptPasswordMatch, credentials.username)
        else:
            self.debug('user %s refused, not in database' %
                credentials.username)
            return defer.fail(error.UnauthorizedLogin())
