# -*- Mode: Python -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# flumotion/manager/manager.py: manager functionality
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
Manager implementation and related classes

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
        self._interfaceHeavens = {} # interface -> heaven
        self._avatarHeavens = {} # avatarId -> heaven
        
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
        heaven = self._avatarHeavens[avatarId]
        del self._avatarHeavens[avatarId]
        
        avatar.detached(mind)
        heaven.removeAvatar(avatarId)

    def createAvatarFor(self, avatarId, ifaces):
        """
        Create an avatar from the heaven implementing the given interface.

        @type avatarId:  string
        @param avatarId: the name of the new avatar
        @type ifaces:    tuple of interfaces linked to heaven
        @param ifaces:   a list of heaven interfaces to get avatar from

        @returns:        an avatar from the heaven managing the given interface.
        """
        if not pb.IPerspective in ifaces:
            raise errors.NoPerspectiveError(avatarId)

        for iface in ifaces:
            heaven = self._interfaceHeavens.get(iface, None)
            if heaven:
                avatar = heaven.createAvatar(avatarId)
                self._avatarHeavens[avatarId] = heaven
                return avatar

        raise errors.NoPerspectiveError(avatarId)
        
    def registerHeaven(self, heaven, interface):
        """
        Register a Heaven as managing components with the given interface.

        @type interface:  L{twisted.python.components.Interface}
        @param interface: a component interface to register the heaven with.
        """
        assert components.implements(heaven, interfaces.IHeaven)
        
        self._interfaceHeavens[interface] = heaven

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
        self.dispatcher.registerHeaven(heaven, interface)
        return heaven
    
    def getFactory(self):
        return self.factory
