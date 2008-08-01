# -*- Mode: Python -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# Flumotion - a streaming media server
# Copyright (C) 2004,2005,2006,2007,2008 Fluendo, S.L. (www.fluendo.com).
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

"""interfaces used by flumotion
"""

from zope.interface import Attribute, Interface

__version__ = "$Rev$"


# See also flumotion.medium.BaseMedium.
class IMedium(Interface):
    """I am a base interface for PB client-side mediums interfacing with
    manager-side avatars.
    """
    def setRemoteReference(remoteReference):
        """Set the RemoteReference to the manager-side avatar.
        @param remoteReference: L{twisted.spread.pb.RemoteReference}
        """

    def hasRemoteReference():
        """Check if we have a remote reference to the PB server's avatar.
        @returns: True if we have a remote reference
        """

    def callRemote(name, *args, **kwargs):
        """Call a method through the remote reference to the
        manager-side avatar.
        @param name: name of remote method
        """


class IComponentMedium(IMedium):
    """I am an interface for component-side mediums interfacing
    with server-side avatars.
    """


class IStreamingComponent(Interface):
    """An interface for streaming components, for plugs that
    require a streaming component of some sort to use.
    """

    def getUrl():
        """Return a URL that the streaming component is streaming.
        """

    def getDescription():
        """Return a description of the stream from this component.
        """


class IAdminMedium(IMedium):
    """I am an interface for admin-side mediums interfacing with manager-side
    avatars.
    """


class IWorkerMedium(IMedium):
    """I am an interface for worker-side mediums interfacing with manager-side
    avatars.
    """


class IPorterMedium(IMedium):
    """I am an interface for porter client mediums interfacing with the porter.
    """


class IJobMedium(IMedium):
    """I am an interface for job-side mediums interfacing with worker-side
    avatars.
    """


class IFeedMedium(IMedium):
    """I am an interface for mediums in a job or manager interfacing with feed
    avatars.
    """


class IHeaven(Interface):
    """My implementors manage avatars logging in to the manager.
    """
    def createAvatar(avatarId):
        """Creates a new avatar matching the type of heaven.
        @param avatarId:
        @type avatarId: string
        @returns: the avatar from the matching heaven for a new object.
        """

    def removeAvatar(avatarId):
        """Remove the avatar with the given Id from the heaven.
        """


class IFeedServerParent(Interface):
    """I am an interface for objects that manage a FeedServer, allowing the
    FeedServer to hand off file descriptors to eaters and feeders managed
    by the parent.
    """
    def feedToFD(componentId, feedName, fd):
        """Make the component feed the given feed to the fd.
        @param componentId:
        @param feedName: a feed name
        @param fd: a file descriptor
        """


class IFile(Interface):
    """I am an interface representing a file and it's metadata.
    """
    filename = Attribute('the name of the file')
    iconNames = Attribute("""icon names that should be used to represent
      this file in a graphical interface""")

    def getPath():
        """Returns the complete path to the file, including
        the filename itself.
        @returns: the complete path to the file
        @rtype: str
        """


class IDirectory(IFile):
    """I am an interface representing a directory and it's metadata.
    I extend the IFile interface.
    To list files of a certain directory you first need to call
    L{flumotion.common.vfs.listDirectory}, which will return
    an object implementing this interface.
    """

    def getFiles():
        """Fetches all the files in the directory specified.
        @returns: list of files
        @rtype: a deferred firing a list of objects implementing L{IFile}.
        """
