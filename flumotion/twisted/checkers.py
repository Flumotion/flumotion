# -*- Mode: Python; test-case-name: flumotion.test.test_checkers -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# flumotion/twisted/checkers.py: credential checkers; see twisted.cred.checkers
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

from twisted.cred import checkers, error
from twisted.internet import defer
from twisted.python import failure

from flumotion.common import log
from flumotion.twisted import credentials

# FIXME: give the manager's bouncer's checker to the flexcredchecker,
# and forward to it
parent = checkers.InMemoryUsernamePasswordDatabaseDontUse
class FlexibleCredentialsChecker(parent, log.Loggable):
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

class CryptChecker:
    __implements__ = checkers.ICredentialsChecker
    credentialInterfaces = ( credentials.IUsernameCryptPassword, )

    def __init__(self, **users):
        self.users = users

    def addUser(self, username, cryptPassword):
        self.users[username] = cryptPassword

    def _cbCryptPasswordMatch(self, matched, username):
        if matched:
            return username
        else:
            return failure.Failure(error.UnauthorizedLogin())

    def requestAvatarId(self, credentials):
        if credentials.username in self.users:
            return defer.maybeDeferred(
                credentials.checkCryptPassword,
                self.users[credentials.username]).addCallback(
                self._cbCryptPasswordMatch, credentials.username)
        else:
            return failure.Failure(error.UnauthorizedLogin())
