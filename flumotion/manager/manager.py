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
Manager implementation and related classes.

API Stability: semi-stable

Maintainer: U{Johan Dahlin <johan@fluendo.com>}
"""

__all__ = ['ManagerServerFactory', 'Vishnu']

from twisted.internet import reactor
from twisted.cred import error
from twisted.python import components, failure
from twisted.spread import pb
from twisted.cred import portal

from flumotion.manager import admin, component, worker
from flumotion.common import errors, interfaces, log
from flumotion.twisted import checkers
from flumotion.twisted import portal as fportal

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
        @param ifaces:   a list of heaven interfaces to get avatar from,
                         including pb.IPerspective

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

class ManagerCredentialsChecker(checkers.FlexibleCredentialsChecker):
    # FIXME: maybe we should get the actual checker used by bouncer
    def __init__(self):
        checkers.FlexibleCredentialsChecker.__init__(self)
        self.bouncer = None

    def requestAvatarId(self, creds):
        # until we figure out component auth, we pass components freely
        if interfaces.IComponentMedium in creds.interfaces:
            return creds.avatarId

        # if we have a bouncer, we make workers and admin authenticate
        if self.bouncer:
            result = self.bouncer.authenticate(creds)
            if not result:
                self.log('refusing credentials %r' % creds)
                return failure.Failure(error.UnauthorizedLogin())
                
        # XXX: If it's component or admin, allow anonymous access.
        #      This is a big hack, but it emulates the current behavior
        #      Do we need to authenticate components and workers?
        if (interfaces.IComponentMedium in creds.interfaces or
            interfaces.IAdminMedium in creds.interfaces):
            return creds.username

        return checkers.FlexibleCredentialsChecker.requestAvatarId(self, creds)

class Vishnu(log.Loggable):
    """
    I am the toplevel manager object that knows about all heavens and factories.
    """
    logCategory = "vishnu"
    def __init__(self):
        # create a Dispatcher which will hand out avatars to clients
        # connecting to me
        self.dispatcher = Dispatcher()

        self.workerheaven = self._createHeaven(interfaces.IWorkerMedium,
                                               worker.WorkerHeaven)
        self.componentheaven = self._createHeaven(interfaces.IComponentMedium,
                                                  component.ComponentHeaven)
        self.adminheaven = self._createHeaven(interfaces.IAdminMedium,
                                              admin.AdminHeaven)
        self.bouncer = None # used by manager to authenticate worker/component

        # create a portal so that I can be connected to, through our dispatcher
        # implementing the IRealm and a checker that allows anonymous access

        # FIXME: depcrecated
        self.checker = ManagerCredentialsChecker()
        # the WorkerHeaven sets this to True later on if the config file
        # uses a password policy
        self.checker.allowAnonymous(True) # XXX: False
        
        # FIXME: decide if we allow anonymous login in this small (?) window
        self.portal = fportal.BouncerPortal(self.dispatcher, None)
        #unsafeTracebacks = 1 # for debugging tracebacks to clients
        self.factory = pb.PBServerFactory(self.portal)

    def _createHeaven(self, interface, klass):
        """
        Create a heaven of the given klass that will send avatars to clients
        implementing the given medium interface.

        @param interface: the medium interface to create a heaven for
        @type interface: L{flumotion.common.interfaces.IMedium}
        @param klass: the type of heaven to create
        @type klass: an implementor of L{flumotion.common.interfaces.IHeaven}
        """
        assert issubclass(interface, interfaces.IMedium)
        heaven = klass(self)
        self.dispatcher.registerHeaven(heaven, interface)
        return heaven
    
    def setBouncer(self, bouncer):
        """
        @type bouncer: L{flumotion.component.bouncers.bouncer.Bouncer}
        """
        self.bouncer = bouncer
        self.checker.bouncer = bouncer
        self.portal.bouncer = bouncer

    def getFactory(self):
        return self.factory
