# -*- Mode: Python -*-
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

from flumotion.common import log
from twisted.cred import credentials

class Username:
    __implements__ = credentials.IUsernamePassword,
    def __init__(self, username, password=''):
        self.username = username
        self.password = password

class IUsernameCryptedPassword(credentials.ICredentials):
    def checkCrypted(self, crypted):
        pass
        
class UsernameCryptedPassword:
    __implements__ = (IUsernameCryptedPassword,)

    def __init__(self, username, password, salt):
        assert len(salt) == 2

        self.username = username
        self.crypted = crypt.crypt(password, salt)

    def checkCrypted(self, crypted):
        return self.crypted == crypted
