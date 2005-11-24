# -*- Mode: Python; test-case-name: flumotion.test.test_manager_admin -*-
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
manager-side objects to handle administrative clients
"""

import os

from twisted.internet import reactor
from twisted.spread import pb
from twisted.python import failure

from flumotion.manager import base
from flumotion.common import errors, interfaces, log, planet, registry

# make ComponentState proxyable
from flumotion.twisted import flavors
from flumotion.common import componentui

# FIXME: rename to Avatar since we are in the admin. namespace ?
class AdminAvatar(base.ManagerAvatar):
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
        base.ManagerAvatar.attached(self, mind)

    def detached(self, mind):
        self.info('admin client "%s" logged out' % self.avatarId)
        base.ManagerAvatar.detached(self, mind)

    # FIXME: instead of doing this, give a RemoteCache of the heaven state ?
    def getComponentStates(self):
        """
        Return all component states logged in to the manager.
        The list gets serialized to a list of
        L{flumotion.common.planet.AdminComponentState}
        
        @rtype: C{list} of L{flumotion.common.planet.ManagerComponentState}
        """
        return self.vishnu.getComponentStates()

    def sendLog(self, category, type, message):
        """
        Send the given log message to the peer.
        """
        # don't send if we don't have a remote reference yet.
        # this avoids recursion from the remote caller trying to warn
        if self.hasRemoteReference():
            self.mindCallRemote('log', category, type, message)
        
    ### pb.Avatar IPerspective methods
    def perspective_getPlanetState(self):
        self.debug("returning planet state %r" % self.vishnu.state)
        return self.vishnu.state

    def perspective_getWorkerHeavenState(self):
        self.debug("returning worker heaven state %r" % self.vishnu.state)
        return self.vishnu.workerHeaven.state

    def perspective_shutdown(self):
        print 'SHUTTING DOWN'
        reactor.stop()
        raise SystemExit

    def perspective_componentStart(self, componentState):
        """
        Start the given component.  The component should be sleeping before
        this.
        """
        self.debug('perspective_componentStart(%r)' % componentState)
        return self.vishnu.componentStart(componentState)
        
    def perspective_componentStop(self, componentState):
        """
        Stop the given component.
        """
        self.debug('perspective_componentStop(%r)' % componentState)
        return self.perspective_componentCallRemote(componentState, 'stop')
        
    def perspective_componentRestart(self, componentState):
        """
        Restart the given component.
        """
        self.debug('perspective_componentRestart(%r)' % componentState)
        d = self.perspective_componentStop(componentState)
        d.addCallback(lambda *x: self.perspective_componentStart(componentState))
        return d
        
    # Generic interface to call into a component
    def perspective_componentCallRemote(self, componentState, methodName,
                                        *args, **kwargs):
        """
        Call a method on the given component on behalf of an admin client.
        
        @type componentState: L{flumotion.common.planet.ManagerComponentState}
        """
        assert isinstance(componentState, planet.ManagerComponentState)

        if methodName == "start":
            self.warning('forwarding "start" to perspective_componentStart')
            return self.perspective_componentStart(componentState)

        m = self.vishnu.getComponentMapper(componentState)
        avatar = m.avatar
        
        if not avatar:
            self.warning('No avatar for %s, cannot call remote' %
                componentState.get('name'))
            raise errors.SleepingComponentError()

        # XXX: Maybe we need to have a prefix, so we can limit what an
        # admin interface can call on a component
        try:
            return avatar.mindCallRemote(methodName, *args, **kwargs)
        except Exception, e:
            msg = "exception on remote call %s: %s" % (methodName, str(e))
            self.warning(msg)
            raise errors.RemoteMethodError(str(e))

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
        
    def perspective_getEntryByType(self, componentState, type):
        """
        Get the entry point for a piece of bundled code by the type.

        Returns: a (filename, methodName) tuple, or raises a Failure.
        """
        m = self.vishnu.getComponentMapper(componentState)
        componentName = componentState.get('name')

        if not m.avatar:
            self.debug('component %s not logged in yet, no entry' %
                componentName)
            raise errors.SleepingComponentError(componentName)

        componentType = m.avatar.getType()
        self.debug('getting entry of type %s for component %s of type %s' % (
            type, componentName, componentType))
        try:
            componentRegistryEntry = registry.getRegistry().getComponent(
                componentType)
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

    def perspective_reloadComponent(self, componentState):
        """Reload modules in the given component."""
        def _reloaded(result, self, name):
            self.info("reloaded component %s code" % name)

        name = componentState.get('name')
        self.info("reloading component %s code" % name)
        m = self.vishnu.getComponentMapper(componentState)
        avatar = m.avatar
        d = avatar.reloadComponent()
        d.addCallback(_reloaded, self, name)
        return d

    def perspective_reloadManager(self):
        """Reload modules in the manager."""
        import sys
        from twisted.python.rebuild import rebuild
        self.info('reloading manager code')
        # reload ourselves first
        rebuild(sys.modules[__name__])

        # now rebuild relevant modules
        import flumotion.common.reload
        rebuild(sys.modules['flumotion.common'])
        flumotion.common.reload.reload()
        self._reloaded()

    def perspective_getConfiguration(self):
        """
        Get the configuration of the manager as an XML string.

        @returns: string
        """
        return self.vishnu.getConfiguration()

    def perspective_loadConfiguration(self, xml):
        """
        @type  xml: string
        """
        self.info('loadConfiguration ...')
        self.vishnu.loadConfiguration(None, xml)

    def perspective_deleteFlow(self, flowName):
        return self.vishnu.deleteFlow(flowName)

    # Deprecated -- remove me when no one uses me any more
    def perspective_cleanComponents(self):
        return self.vishnu.emptyPlanet()

    # separate method so it runs the newly reloaded one :)
    def _reloaded(self):
        self.info('reloaded manager code')

class AdminHeaven(base.ManagerHeaven):
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
        base.ManagerHeaven.__init__(self, vishnu)
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

    def avatarsCallRemote(self, methodName, *args, **kwargs):
        """
        Call a remote method on all AdminAvatars in this heaven.

        @type methodName: string
        """
        for avatar in self.getAvatars():
            avatar.mindCallRemote(methodName, *args, **kwargs)
  
