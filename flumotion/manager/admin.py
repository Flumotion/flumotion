# -*- Mode: Python; test-case-name: flumotion.test.test_manager_admin -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# flumotion/manager/admin.py: manager-side objects to handle admin clients
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
Manager-side objects to handle administrative clients.
"""

from twisted.internet import reactor
from twisted.spread import pb

from flumotion.common import errors, interfaces, log

class ComponentView(pb.Copyable):
    """
    I present state of a component through a L{RemoteComponentView} in the peer.
    I get the state I present from a
    L{flumotion.manager.component.ComponentAvatar}.
    I live in the manager.
    """
    def __init__(self, component):
        """
        @type component: L{flumotion.manager.component.ComponentAvatar}
        """
        self.name = component.getName()
        # forced to int so it's jellyable
        self.state = int(component.state)
        self.eaters = component.getEaters()
        self.feeders = component.getFeeders()
        self.options = component.options.dict

# FIXME: move this out to flumotion.admin
class RemoteComponentView(pb.RemoteCopy):
    """
    I represent state of a component.
    I am a copy of a manager-side L{ComponentView}
    I live in an admin client.
    """
    def __cmp__(self, other):
        if not isinstance(other, RemoteComponentView):
            return False
        return cmp(self.name, other.name)
    
    def __repr__(self):
        return '<RemoteComponentView %s>' % self.name
pb.setUnjellyableForClass(ComponentView, RemoteComponentView)

# FIXME: rename to Avatar since we are in the admin. namespace ?
class AdminAvatar(pb.Avatar, log.Loggable):
    """
    I am an avatar created for an administrative client interface.
    A reference to me is given (for example, to gui.AdminInterface)
    when logging in and requesting an "admin" avatar.
    I live in the manager.
    """
    logCategory = 'admin-avatar'
    def __init__(self, heaven, avatarId):
        """
        @type heaven: L{flumotion.manager.admin.AdminHeaven}
        """
        self.heaven = heaven
        self.workerHeaven = heaven.vishnu.workerHeaven
        self.componentHeaven = heaven.vishnu.componentHeaven

        self.mind = None
        self.avatarId = avatarId
        self.debug("created new AdminAvatar with id %s" % avatarId)
        
    def hasRemoteReference(self):
        """
        Check if the avatar has a remote reference to the peer.

        @rtype: boolean
        """
        return self.mind != None
    
    def _mindCallRemote(self, name, *args, **kwargs):
        if not self.hasRemoteReference():
            self.warning("Can't call remote method %s, no mind" % name)
            return
        
        # we can't do a .debug here, since it will trigger a resend of the
        # debug message as well, causing infinite recursion !
        # self.debug('Calling remote method %s%r' % (name, args))
        try:
            return self.mind.callRemote(name, *args, **kwargs)
        except pb.DeadReferenceError:
            mind = self.mind
            self.mind = None
            self.warning("mind %s is a dead reference, removing" % mind)
            return
        
    def getComponents(self):
        """
        Return all components logged in to the manager.
        
        @rtype: C{list} of L{flumotion.manager.admin.ComponentView}
        """
        # FIXME: should we use an accessor to get at components from c ?
        components = map(ComponentView, self.componentHeaven.avatars.values())
        return components

    def getWorkers(self):
        """
        Return all workers logged in to the manager.
        
        @rtype: C{list} of workers
        """

        return [worker.getName()
                    for worker in self.workerHeaven.getAvatars()]

    def sendLog(self, category, type, message):
        """
        Send the given log message to the peer.
        """
        # don't send if we don't have a remote reference yet.
        # this avoids recursion from the remote caller trying to warn
        if self.hasRemoteReference():
            self._mindCallRemote('log', category, type, message)
        
    def componentAdded(self, component):
        """
        Tell the avatar that a component has been added.
        """
        self.debug("AdminAvatar.componentAdded: %s" % component)
        self._mindCallRemote('componentAdded', ComponentView(component))
        
    def componentStateChanged(self, component, state):
        self.debug("AdminAvatar.componentStateChanged: %s %s" % (component, state))
        self._mindCallRemote('componentStateChanged', ComponentView(component), state)

    def componentRemoved(self, component):
        """
        Tell the avatar that a component has been removed.
        """
        self.debug("AdminAvatar.componentRemoved: %s" % component)
        self._mindCallRemote('componentRemoved', ComponentView(component))

    def uiStateChanged(self, name, state):
        self.debug("AdminAvatar.uiStateChanged: %s %s" % (name, state))
        self._mindCallRemote('uiStateChanged', name, state)

    def attached(self, mind):
        """
        Give the avatar a remote reference to the
        peer's client that logged in and requested the avatar.
        Also make the avatar send the initial clients to the peer.

        @type mind: L{twisted.spread.pb.RemoteReference}
        """
        self.mind = mind
        ip = self.mind.broker.transport.getPeer().host
        self.debug('Client from %s attached, sending client components' % ip)
        self.log('Client attached is mind %s' % mind)

        self._mindCallRemote('initial',
                             self.getComponents(),
                             self.getWorkers())

    def detached(self, mind):
        """
        Tell the avatar that the peer's client referenced by the mind
        has detached.
        """
        assert(self.mind == mind)
        ip = self.mind.broker.transport.getPeer().host
        self.mind = None
        self.debug('Client from %s detached' % ip)
        self.log('Client detached is mind %s' % mind)

    ### pb.Avatar IPerspective methods
    def perspective_shutdown(self):
        print 'SHUTTING DOWN'
        reactor.stop()
        raise SystemExit

    # Generic interface to call into a component
    def perspective_callComponentRemote(self, componentName, method_name,
                                        *args, **kwargs):
        component = self.componentHeaven.getComponent(componentName)
        try:
            return component.callComponentRemote(method_name, *args, **kwargs)
        except Exception, e:
            self.warning(str(e))
            raise
        
    def perspective_setComponentElementProperty(self, componentName, element, property, value):
        """Set a property on an element in a component."""
        component = self.componentHeaven.getComponent(componentName)
        try:
            return component.setElementProperty(element, property, value)
        except errors.PropertyError, exception:
            self.warning(str(exception))
            raise

    def perspective_getComponentElementProperty(self, componentName, element, property):
        """Get a property on an element in a component."""
        component = self.componentHeaven.getComponent(componentName)
        try:
            return component.getElementProperty(element, property)
        except errors.PropertyError, exception:
            self.warning(str(exception))
            raise

    def perspective_getUIZip(self, componentName, domain, style):
        """
        Get the zip data of the bundle for the user interface.

        @type  domain: string
        @param domain: the domain of the user interface to get the zip for
        @type  style:  string
        @param style:  the style of the user interface to get the zip for
        """
        component = self.componentHeaven.getComponent(componentName)
        try:
            return component.getUIZip(domain, style)
        except Exception, e:
            self.warning(str(e))
            raise

    def perspective_getUIMD5Sum(self, componentName, domain, style):
        """
        Get the MD5 sum of the bundle for the user interface.

        @type  domain: string
        @param domain: the domain of the user interface to get the MD5 sum for
        @type style:  string
        @param style: the style of the user interface to get MD5 sum for
        """
        component = self.componentHeaven.getComponent(componentName)
        try:
            return component.getUIMD5Sum(domain, style)
        except Exception, e:
            self.warning(str(e))
            raise

    def perspective_reloadComponent(self, componentName):
        """Reload modules in the given component."""
        def _reloaded(result, self, name):
            self.info("reloaded component %s code" % name)

        self.info("reloading component %s code" % componentName)
        avatar = self.componentHeaven.getComponent(componentName)
        cb = avatar.reloadComponent()
        cb.addCallback(_reloaded, self, componentName)
        return cb

    def perspective_reloadManager(self):
        """Reload modules in the manager."""
        import sys
        from twisted.python.rebuild import rebuild
        self.info('reloading manager code')
        # reload ourselves first
        rebuild(sys.modules[__name__])

        # now rebuild relevant modules
        import flumotion.utils.reload
        rebuild(sys.modules['flumotion.utils'])
        flumotion.utils.reload.reload()
        self._reloaded()

    def perspective_loadConfiguration(self, xml):
        self.info('loadConfiguration ...')
        self.workerHeaven.loadConfiguration(None, xml)

    def perspective_checkElements(self, workerId, elements):
        workerAvatar = self.workerHeaven.getAvatar(workerId)
        return workerAvatar.checkElements(elements)
        
    # separate method so it runs the newly reloaded one :)
    def _reloaded(self):
        self.info('reloaded manager code')

class AdminHeaven(pb.Root, log.Loggable):
    """
    I interface between the Manager and administrative clients.
    For each client I create an L{AdminAvatar} to handle requests.
    I live in the manager.
    """

    logCategory = "admin-heaven"
    __implements__ = interfaces.IHeaven

    def __init__(self, vishnu):
        """
        @type vishnu: L{flumotion.manager.manager.Vishnu}
        @param vishnu: the Vishnu in control of all the heavens
        """
        self.vishnu = vishnu
        self.avatars = {} # adminName -> adminAvatar
        #FIXME: don't add a log handler here until we have a good way
        #of filtering client-side again
        #log.addLogHandler(self.logHandler)
        self.logcache = []

    def logHandler(self, category, type, message):
        self.logcache.append((category, type, message))
        for avatar in self.avatars.values():
            avatar.sendLog(category, type, message)

    def sendCache(self, avatar):
        if not avatar.hasRemoteReference():
            reactor.callLater(0.25, self.sendCache, avatar)
            return
        
        # FIXME: do this on request only
        #self.debug('sending logcache to client (%d messages)' % len(self.logcache))
        #for category, type, message in self.logcache:
        #    avatar.sendLog(category, type, message)
        
    ### IHeaven methods

    def createAvatar(self, avatarId):
        """
        Create a new administration avatar and manage it.
        @rtype:   L{flumotion.manager.admin.AdminAvatar}
        @returns: a new avatar for the admin client.
        """
        self.debug('creating new AdminAvatar')
        avatar = AdminAvatar(self, avatarId)
        reactor.callLater(0.25, self.sendCache, avatar)
        
        self.avatars[avatarId] = avatar
        return avatar

    def removeAvatar(self, avatarId):
        """
        Stop managing the given avatar.

        @type avatarId:  string
        @param avatarId: id of the avatar to remove
        """
        self.debug('removing AdminAvatar with id %s' % avatarId)
        del self.avatars[avatarId]
    
    ### my methods

    def componentAdded(self, component):
        """
        Tell all created AdminAvatars that a component was added.

        @type component: L{flumotion.manager.component.ComponentAvatar}
        """
        for avatar in self.avatars.values():
            avatar.componentAdded(component)

    def componentRemoved(self, component):
        """
        Tell all created AdminAvatars that a component was removed.

        @type component: L{flumotion.manager.component.ComponentAvatar}
        """
        for avatar in self.avatars.values():
            avatar.componentRemoved(component)
            
    def componentStateChanged(self, component, state):
        """
        Tell all created AdminAvatars that a component has changed state.

        @type component: L{flumotion.manager.component.ComponentAvatar}
        """
        for avatar in self.avatars.values():
            avatar.componentStateChanged(component, state)


    def uiStateChanged(self, name, state):
        """
        Tell all created AdminAvatars that an ui state for a component was changed

        @type name:      name of the component
        @type state:     new ui state
        """
        
        for avatar in self.avatars.values():
            avatar.uiStateChanged(name, state)
        
