# -*- Mode: Python -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# flumotion/manager/manager.py: manager functionality
# 
# Flumotion - a streaming media server
# Copyright (C) 2004 Fluendo, S.L. (www.fluendo.com). All rights reserved.

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
manager implementation and related classes

API Stability: semi-stable

Maintainer: U{Johan Dahlin <johan@fluendo.com>}
"""

__all__ = ['ManagerServerFactory', 'Vishnu']

import os

from twisted.internet import reactor
from twisted.cred import error
from twisted.python import components, failure
from twisted.spread import pb
from twisted.cred import portal

from flumotion.common import bundle, config, errors, interfaces, log, registry
from flumotion.configure import configure
from flumotion.manager import admin, component, worker, common
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
        """
        Remove an avatar because it logged out of the manager.
        
        This function is registered by requestAvatar.
        """
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
        assert isinstance(heaven, common.ManagerHeaven)
       
        self._interfaceHeavens[interface] = heaven

class Vishnu(log.Loggable):
    """
    I am the toplevel manager object that knows about all heavens and factories.
    """
    logCategory = "vishnu"
    def __init__(self):
        # create a Dispatcher which will hand out avatars to clients
        # connecting to me
        self.dispatcher = Dispatcher()

        self.workerHeaven = self._createHeaven(interfaces.IWorkerMedium,
                                               worker.WorkerHeaven)
        self.componentHeaven = self._createHeaven(interfaces.IComponentMedium,
                                                  component.ComponentHeaven)
        self.adminHeaven = self._createHeaven(interfaces.IAdminMedium,
                                              admin.AdminHeaven)
        self.bouncer = None # used by manager to authenticate worker/component
        self.bundlerBasket = None
        self._setupBundleBasket()

        # create a portal so that I can be connected to, through our dispatcher
        # implementing the IRealm and a bouncer
        # FIXME: decide if we allow anonymous login in this small (?) window
        self.portal = fportal.BouncerPortal(self.dispatcher, None)
        #unsafeTracebacks = 1 # for debugging tracebacks to clients
        self.factory = pb.PBServerFactory(self.portal)

        self.configuration = None

    # FIXME: do we want a filename to load config, or data directly ?
    def loadConfiguration(self, filename):
        """
        Load the configuration from the given filename, merging it on
        top of the currently running configuration.
        """
        # FIXME: we should be able to create "wanted" config/state from
        # something else than XML as well
        conf = config.FlumotionConfigXML(filename)

        # scan filename for a bouncer component in the manager
        # FIXME: we should have a "running" state object layout similar
        # to config that we can then merge somehow with an .update method
        if conf.manager and conf.manager.bouncer:
            if self.bouncer:
                self.warning("manager already had a bouncer")

            self.debug('going to start manager bouncer %s of type %s' % (
                conf.manager.bouncer.name, conf.manager.bouncer.type))
            from flumotion.common.registry import registry
            defs = registry.getComponent(conf.manager.bouncer.type)
            configDict = conf.manager.bouncer.getConfigDict()
            import flumotion.worker.job
            self.setBouncer(flumotion.worker.job.getComponent(configDict, defs))
            self.bouncer.debug('started')
            log.info('manager', "Started manager's bouncer")

        # make the worker heaven and component heaven
        # load the configuration as well
        # FIXME: we should only handle the added conf, so we get the changes
        # parsing should also be done only once
        self.workerHeaven.loadConfiguration(filename)
        self.componentHeaven.loadConfiguration(filename)

    def _setupBundleBasket(self):
        self.bundlerBasket = bundle.BundlerBasket()

        for b in registry.registry.getBundles():
            bundleName = b.getName()
            self.debug('Adding bundle %s' % bundleName)
            for d in b.getDirectories():
                directory = d.getName()
                for filename in d.getFiles():
                    fullpath = os.path.join(configure.pythondir, directory,
                                            filename.getLocation())
                    relative = filename.getRelative()
                    self.log('Adding path %s as %s to bundle %s' % (
                        fullpath, relative, bundleName))
                    self.bundlerBasket.add(bundleName, fullpath, relative)

            for d in b.getDependencies():
                self.log('Adding dependency of %s on %s' % (bundleName, d))
                self.bundlerBasket.depend(bundleName, d)
        
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
        self.portal.bouncer = bouncer

    def getFactory(self):
        return self.factory
