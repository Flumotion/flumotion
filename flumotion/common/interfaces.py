# -*- Mode: Python -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# flumotion/common/interfaces.py: common interfaces
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

class IComponentView(components.Interface):
    """
    I am an interface implemented by PB client-side views for component clients.
    """
    pass

class IAdminView(components.Interface):
    """
    I am an interface implemented by PB client-side views for admin clients.
    """
    pass

class IWorkerView(components.Interface):
    """
    I am an interface implemented by PB client-side views for worker clients.
    """
    pass

class IHeaven(components.Interface):
    def createAvatar(self, avatarId):
        """
        Creates a new avatar matching the type of heaven.

        @type avatarId: string

        @returns: the avatar from the matching heaven for a new object.
        """

    def removeAvatar(self, avatarId):
        """
        Remove the avatar with the given Id from the heaven.
        """
    
class INewCredPerspective(components.Interface):
    def attached(self, mind):
        """
        Attaches a mind

        @type mind: PB Broker
        """

    def detached(self, mind):
        """
        Detaches a mind

        @type mind: PB Broker
        """

