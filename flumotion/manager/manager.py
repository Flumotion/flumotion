# -*- Mode: Python -*-
# vi:si:et:sw=4:sts=4:ts=4

# Flumotion - a video streaming server
# Copyright (C) 2004 Fluendo
#
# manager/manager.py: manager functionality
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

"""Manager implementation and related classes

API Stability: semi-stable

Maintainer: U{Johan Dahlin <johan@fluendo.com>}
"""

__all__ = ['ManagerServerFactory', 'Vishnu']

from twisted.internet import reactor
from twisted.python import components
from twisted.spread import pb

from flumotion.manager import admin, component, worker
from flumotion.common import errors, interfaces
from flumotion.twisted import cred, portal
from flumotion.utils import log

# an internal class
class Dispatcher(log.Loggable):
    """
    I implement L{portal.IRealm}.
    I make sure that when a L{pb.Avatar} is requested through me, the
    Avatar being returned knows about the mind (client) requesting
    the Avatar.
    """
    
    __implements__ = portal.IRealm

    logCategory = 'dispatcher'

    def __init__(self):
        self.heavens = {} # registered heavens, keyed on interface
        self.avatars = {} # avatarId -> heaven
        
    ### IRealm methods

    # requestAvatar gets called through ClientFactory.login()
    # An optional second argument can be passed to login, which should be
    # a L{twisted.spread.flavours.Referenceable}
    # A L{twisted.spread.pb.RemoteReference} to it is passed to
    # requestAvatar as mind.
    # So in short, the mind is a reference to the client passed in login()
    # on the peer, allowing any object that has the mind to call back
    # to the piece that called login(),
    # which in our case is a component or an admin client.
    def requestAvatar(self, avatarId, mind, *ifaces):
        avatar = self.createAvatarFor(avatarId, ifaces)

        self.debug("returning Avatar: id %s, avatar %s" % (avatarId, avatar))

        # schedule a perspective attached for after this function
        reactor.callLater(0, avatar.attached, mind)

        # return a tuple of interface, aspect, and logout function 
        return (pb.IPerspective, avatar,
                lambda a=avatar, m=mind, i=avatarId: self.removeAvatar(i, a, m))

    ### our methods

    def removeAvatar(self, avatarId, avatar, mind):
        heaven = self.avatars[avatarId]
        del self.avatars[avatarId]
        
        avatar.detached(mind)
        heaven.removeAvatar(avatarId)

    def getAvatarFor(self, avatarId, ifaces):
        if not pb.IPerspective in ifaces:
            raise errors.NoPerspectiveError(avatarId)

        for iface in ifaces:
            heaven = self.heavens.get(iface, None)
            if heaven:
                avatar = heaven.getAvatar(avatarId)
                self.avatars[avatarId] = heaven
                return avatar

        raise errors.NoPerspectiveError(avatarId)
        
    def registerHeaven(self, interface, heaven):
        """
        register a Heaven implementing the given interface.
        """
        assert components.implements(heaven, interfaces.IHeaven)
        
        self.heavens[interface] = heaven

class ManagerCredentials(cred.FlexibleCredentials):
    def requestAvatarId(self, credentials):
        # XXX: If it's component, allow anonymous access.
        #      This is a big hack, but it emulates the current behavior
        #      Do we need to authenticate components and workers?
        if interfaces.IBaseComponent in credentials.interfaces:
            return credentials.username

        return cred.FlexibleCredentials.requestAvatarId(self, credentials)

class Vishnu:
    """
    I am the toplevel manager object that knows about all heavens and factories
    """
    def __init__(self):
        # create a Dispatcher which will hand out avatars to clients
        # connecting to me
        self.dispatcher = Dispatcher()

        self.workerheaven = self._createHeaven(interfaces.IWorkerComponent,
                                               worker.WorkerHeaven)
        self.componentheaven = self._createHeaven(interfaces.IBaseComponent,
                                                  component.ComponentHeaven)
        self.adminheaven = self._createHeaven(interfaces.IAdminComponent,
                                              admin.AdminHeaven)

        # create a portal so that I can be connected to, through our dispatcher
        # implementing the IRealm and a checker that allows anonymous access
        self.checker = ManagerCredentials()
        self.checker.allowAnonymous(True) # XXX: False
        
        p = portal.FlumotionPortal(self.dispatcher, [self.checker])
        #unsafeTracebacks = 1 # for debugging tracebacks to clients
        self.factory = pb.PBServerFactory(p)

    def _createHeaven(self, interface, klass):
        heaven = klass(self)
        self.dispatcher.registerHeaven(interface, heaven)
        return heaven
    
    def getFactory(self):
        return self.factory
