# -*- Mode: Python; test-case-name: flumotion.test.test_manager_admin -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# flumotion/manager/admin.py: manager-side objects to handle admin clients
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
manager-side objects to handle administrative clients
"""

import os

from twisted.internet import reactor
from twisted.spread import pb
from twisted.python import failure

from flumotion.manager import common
from flumotion.common import errors, interfaces, log
from flumotion.common.registry import registry

# make ComponentState proxyable
from flumotion.common import component

# FIXME: rename to Avatar since we are in the admin. namespace ?
class AdminAvatar(common.ManagerAvatar):
    """
    I am an avatar created for an administrative client interface.
    A reference to me is given (for example, to gui.AdminInterface)
    when logging in and requesting an "admin" avatar.
    I live in the manager.
    """
    logCategory = 'admin-avatar'
       
    # override base methods
    def attached(self, mind):
        self.info('admin client "%s" logged in' % self.avatarId)
        common.ManagerAvatar.attached(self, mind)
        self.mindCallRemote('initial', self.getComponentStates(),
            self.getWorkers())

    def detached(self, mind):
        self.info('admin client "%s" logged out' % self.avatarId)
        common.ManagerAvatar.detached(self, mind)
    

    # FIXME: instead of doing this, give a RemoteCache of the heaven state ?
    def getComponentStates(self):
        """
        Return all component states logged in to the manager.
        The list gets serialized to a list of
        L{flumotion.common.component.AdminComponentState}
        
        @rtype: C{list} of L{flumotion.common.component.ManagerComponentState}
        """
        states = []
        for avatar in self.vishnu.componentHeaven.avatars.values():
            states.append(getattr(avatar, 'state', None))
        return states

    def getWorkers(self):
        """
        Return all workers logged in to the manager.
        
        @rtype: C{list} of workers
        """

        return [worker.getName()
                    for worker in self.vishnu.workerHeaven.getAvatars()]

    def sendLog(self, category, type, message):
        """
        Send the given log message to the peer.
        """
        # don't send if we don't have a remote reference yet.
        # this avoids recursion from the remote caller trying to warn
        if self.hasRemoteReference():
            self.mindCallRemote('log', category, type, message)
        
    def componentAdded(self, component):
        """
        Tell the avatar that a component has been added.
        """
        self.debug("AdminAvatar.componentAdded: %s" % component)
        self.mindCallRemote('componentAdded', component.state)
        
    def componentRemoved(self, component):
        """
        Tell the avatar that a component has been removed.
        """
        self.debug("AdminAvatar.componentRemoved: %s" % component)
        self.mindCallRemote('componentRemoved', component.state)

    ### pb.Avatar IPerspective methods
    def perspective_shutdown(self):
        print 'SHUTTING DOWN'
        reactor.stop()
        raise SystemExit

    # Generic interface to call into a component
    def perspective_componentCallRemote(self, componentName, methodName,
                                        *args, **kwargs):
        component = self.vishnu.componentHeaven.getComponent(componentName)
        
        # XXX: Maybe we need to have a prefix, so we can limit what an
        # admin interface can call on a component
        
        try:
            return component.mindCallRemote(methodName, *args, **kwargs)
        except Exception, e:
            msg = "exception on remote call %s: %s" % (methodName, str(e))
            self.warning(msg)
            return failure.Failure(errors.RemoteMethodError(str(e)))

    def perspective_workerCallRemote(self, workerName, methodName,
                                     *args, **kwargs):
        """
        Call a remote method on the worker.
        This is used so that admin clients can call methods from the interface
        to the worker.

        @type  workerName: string
        @param workerName: the worker to call.
        @type  methodName: string
        @param methodName: the method to call on the worker.
        """
        
        workerAvatar = self.vishnu.workerHeaven.getAvatar(workerName)
        
        # XXX: Maybe we need to a prefix, so we can limit what an admin
        # interface can call on a worker
        try:
            return workerAvatar.mindCallRemote(methodName, *args, **kwargs)
        except Exception, e:
            self.warning("exception on remote call: %s" % str(e))
            return failure.Failure(errors.RemoteMethodError(str(e)))
        
    # FIXME: deprecate both of these
    def perspective_setComponentElementProperty(self, componentName, element, property, value):
        """Set a property on an element in a component."""
        component = self.vishnu.componentHeaven.getComponent(componentName)
        try:
            return component.setElementProperty(element, property, value)
        except errors.PropertyError, exception:
            self.warning(str(exception))
            raise

    def perspective_getComponentElementProperty(self, componentName, element, property):
        """Get a property on an element in a component."""
        component = self.vishnu.componentHeaven.getComponent(componentName)
        try:
            return component.getElementProperty(element, property)
        except errors.PropertyError, exception:
            self.warning(str(exception))
            raise

    def perspective_getEntryByType(self, componentName, type):
        """
        Get the entry point for a piece of bundled code by the type.

        Returns: a (filename, methodName) tuple, or None if not found.
        """
        componentAvatar = self.vishnu.componentHeaven.getComponent(
            componentName)
        componentType = componentAvatar.getType()
        self.debug('getting entry of type %s for component %s of type %s' % (
            type, componentName, componentType))
        try:
            componentRegistryEntry = registry.getComponent(componentType)
            # FIXME: add logic here for default entry points and functions
            entry = componentRegistryEntry.getEntryByType(type)
        except KeyError:
            self.warning("Could not find bundle for %s(%s)" % (
                componentType, type))
            raise errors.NoBundleError("entry type %s in component type %s" %
                (type, componentType))

        filename = os.path.join(componentRegistryEntry.base, entry.location)
        self.debug('entry point is in file path %s and function %s' % (
            filename, entry.function))
        return (filename, entry.function)

    def perspective_reloadComponent(self, componentName):
        """Reload modules in the given component."""
        def _reloaded(result, self, name):
            self.info("reloaded component %s code" % name)

        self.info("reloading component %s code" % componentName)
        avatar = self.vishnu.componentHeaven.getComponent(componentName)
        d = avatar.reloadComponent()
        d.addCallback(_reloaded, self, componentName)
        return d

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
        self.vishnu.workerHeaven.loadConfiguration(None, xml)
        self.vishnu.componentHeaven.loadConfiguration(None, xml)

    def perspective_cleanComponents(self):
        return self.vishnu.componentHeaven.shutdown()

    # separate method so it runs the newly reloaded one :)
    def _reloaded(self):
        self.info('reloaded manager code')

class AdminHeaven(common.ManagerHeaven):
    """
    I interface between the Manager and administrative clients.
    For each client I create an L{AdminAvatar} to handle requests.
    I live in the manager.
    """

    logCategory = "admin-heaven"
    __implements__ = interfaces.IHeaven
    avatarClass = AdminAvatar

    def __init__(self, vishnu):
        """
        @type vishnu: L{flumotion.manager.manager.Vishnu}
        @param vishnu: the Vishnu in control of all the heavens
        """
        common.ManagerHeaven.__init__(self, vishnu)
        #FIXME: don't add a log handler here until we have a good way
        #of filtering client-side again
        #log.addLogHandler(self.logHandler)
        self.logcache = []

    def logHandler(self, category, type, message):
        self.logcache.append((category, type, message))
        for avatar in self.getAvatars():
            avatar.sendLog(category, type, message)

    def sendCache(self, avatar):
        if not avatar.hasRemoteReference():
            reactor.callLater(0.25, self.sendCache, avatar)
            return
        
        # FIXME: do this on request only
        #self.debug('sending logcache to client (%d messages)' % len(self.logcache))
        #for category, type, message in self.logcache:
        #    avatar.sendLog(category, type, message)
        
    ### my methods

    # FIXME: all of these could be generalized instead of implementing them
    # every step of the way
    def componentAdded(self, component):
        """
        Tell all created AdminAvatars that a component was added.

        @type component: L{flumotion.manager.component.ComponentAvatar}
        """
        for avatar in self.getAvatars():
            avatar.componentAdded(component)

    def componentRemoved(self, component):
        """
        Tell all created AdminAvatars that a component was removed.

        @type component: L{flumotion.manager.component.ComponentAvatar}
        """
        for avatar in self.getAvatars():
            avatar.componentRemoved(component)
            
# FIXME: deprecated; use avatarsCallRemote and use moods
    def componentStateChanged(self, component, state):
        """
        Tell all created AdminAvatars that a component has changed state.

        @type component: L{flumotion.manager.component.ComponentAvatar}
        """
        for avatar in self.getAvatars():
            avatar.componentStateChanged(component, state)

    def avatarsCallRemote(self, methodName, *args, **kwargs):
        """
        Call a remote method on all AdminAvatars in this heaven.

        @type methodName: string
        """
        for avatar in self.getAvatars():
            avatar.mindCallRemote(methodName, *args, **kwargs)
  
