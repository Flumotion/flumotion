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


# FIXME: create a base class that implements setRemoteReference
# since they're the same in all
class IMedium(components.Interface):
    """
    I am a base interface for PB client-side mediums interfacing with
    manager-side avatars.
    """

    def setRemoteReference(self, remoteReference):
        """
        Set the RemoteReference to the manager-side avatar.

        @param remoteReference: L{twisted.spread.pb.RemoteReference}
        """

    def hasRemoteReference(self):
        """
        Check if we have a remote reference to the PB server's avatar.

        @returns: True if we have a remote reference
        """

    def callRemote(self, name, *args, **kwargs):
        """
        Call a method through the remote reference to the manager-side avatar.
        """

class IComponentMedium(IMedium):
    """
    I am an interface for component-side mediums interfacing with server-side
    avatars.
    """
    pass

class IAdminMedium(IMedium):
    """
    I am an interface for admin-side mediums interfacing with manager-side
    avatars.
    """
    pass

class IWorkerMedium(IMedium):
    """
    I am an interface for worker-side mediums interfacing with manager-side
    avatars.
    """
    pass

class IJobMedium(IMedium):
    """
    I am an interface for job-side mediums interfacing with worker-side
    avatars.
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

