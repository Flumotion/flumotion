# -*- Mode: Python -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# Flumotion - a streaming media server
# Copyright (C) 2004,2005 Fluendo, S.L. (www.fluendo.com). All rights reserved.

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
Flumotion interfaces
"""

from twisted.python import components

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
    """
    My implementors manage avatars logging in to the manager.
    """
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
