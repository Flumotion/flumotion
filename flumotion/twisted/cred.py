# -*- Mode: Python -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# flumotion/twisted/cred.py: credential objects
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

from twisted.cred import checkers, credentials, error

parent = checkers.InMemoryUsernamePasswordDatabaseDontUse
class FlexibleCredentials(parent):
    def __init__(self, **users):
        parent.__init__(self, **users)
        self.anonymous = False
        
    def allowAnonymous(self, anon):
        self.anonymous = anon
                         
    ### ICredentialsChecker interface methods
    def requestAvatarId(self, credentials):
        if self.anonymous:
            return credentials.username
        
        return parent.requestAvatarId(self, credentials)

class Username:
    __implements__ = credentials.IUsernamePassword,
    def __init__(self, username, password=''):
        self.username = username
        self.password = password

