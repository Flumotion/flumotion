# -*- Mode: Python -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# Flumotion - a video streaming server
# Copyright (C) 2004 Fluendo
#
# cred.py: add-ons for twisted credential
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Street #330, Boston, MA 02111-1307, USA.

from twisted.cred import checkers, credentials, error

parent = checkers.InMemoryUsernamePasswordDatabaseDontUse
class FlexibleCredentials(parent):
    def __init__(self, **users):
        parent.__init__(self, **users)
        self.anonymous = False
        
    def allowAnonymous(self, anon):
        self.anonymous = anon
                         
    def requestAvatarId(self, credentials):
        if self.anonymous:
            return credentials.username
        
        return parent.requestAvatarId(self, credentials)

class Username:
    __implements__ = credentials.IUsernamePassword,
    def __init__(self, username, password=''):
        self.username = username
        self.password = password

