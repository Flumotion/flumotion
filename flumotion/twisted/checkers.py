# -*- Mode: Python; test-case-name: flumotion.test.test_checkers -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# flumotion/twisted/checkers.py: credential checkers; see twisted.cred.checkers
#
# Flumotion - a streaming media server
# Copyright (C) 2004 Fluendo, S.L. (www.fluendo.com). All rights reserved.

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
        self.anonymous = False
        
    # we allow anonymous only if the manager has no bouncer
    def allowAnonymous(self, wellDoWeQuestionMark):
        self.anonymous = wellDoWeQuestionMark
                         
    ### ICredentialsChecker interface methods
    def requestAvatarId(self, credentials):
        # FIXME: authenticate using manager's bouncer
        avatarId = getattr(credentials, 'avatarId', None)
        if avatarId:
            self.debug("assigned requested avatarId %s" % avatarId)
            return avatarId

        if self.anonymous:
            return credentials.username
        
        return parent.requestAvatarId(self, credentials)

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
