# -*- Mode: Python -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# Flumotion - a video streaming server
# Copyright (C) 2004 Fluendo
#
# interfaces.py: Component Interfaces
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

"""
Interfaces used in Flumotion
"""

from twisted.python import components

# TODO: Hash types (MD5, crypt, SHA)

class IClientKeycard(components.Interface):

    def getUsername(self):
        "returns the username"

    def getPassword(self):
        "returns the password"

    def getIP(self):
        "returns the client ip"

class IAuthenticate(components.Interface):
    
    def setDomain(self, domain):
        "sets the domain of the authenticator"

    def getDomain(self):
        "returns the domain"
        
    def authenticate(self, keycard):
        "authenticates a keycard, must be a IClientKeycard"

# TODO: Common base?

class IBaseComponent(components.Interface):
    pass

class IAdminComponent(components.Interface):
    pass


class IWorkerComponent(components.Interface):
    pass

class IHeaven(components.Interface):
    def getAvatar(self, avatarID):
        pass

    def removeAvatar(self, avatarID):
        pass
    
class INewCredPerspective(components.Interface):
    def attached(self, mind):
        pass

    def detached(self, mind):
        pass
