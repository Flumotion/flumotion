# -*- Mode: Python; test-case-name: flumotion.test.test_manager_admin -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# Flumotion - a streaming media server
# Copyright (C) 2004,2005,2006 Fluendo, S.L. (www.fluendo.com).
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

"""
manager-side objects to handle administrative clients
"""

import os
from StringIO import StringIO

from twisted.internet import reactor, defer
from twisted.spread import pb
from twisted.python import failure

from flumotion.manager import base
from flumotion.common import errors, interfaces, log, planet, registry

# make Result and Message proxyable
from flumotion.common import messages

# make ComponentState proxyable
from flumotion.twisted import flavors
from flumotion.twisted.compat import implements
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
        
        @rtype: list of L{planet.ManagerComponentState}
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
        
    # override pb.Avatar implementation so we can run admin actions
    def perspectiveMessageReceived(self, broker, message, args, kw):
        args = broker.unserialize(args, self)
        kw = broker.unserialize(kw, self)
        method = getattr(self, "perspective_%s" % message)

        benignMethods = ('ping',)
        if message not in benignMethods:
            self.vishnu.adminAction(self.remoteIdentity, message, args, kw)

        try:
            state = method(*args, **kw)
        except TypeError:
            self.debug("%s didn't accept %s and %s" % (method, args, kw))
            raise
        return broker.serialize(state, self, method, args, kw)

    ### pb.Avatar IPerspective methods
    def perspective_getPlanetState(self):
        """
        Get the planet state.

        @rtype: L{flumotion.common.planet.ManagerPlanetState}
        """
        self.debug("returning planet state %r" % self.vishnu.state)
        return self.vishnu.state

    def perspective_getWorkerHeavenState(self):
        """
        Get the worker heaven state.

        @rtype: L{flumotion.common.worker.ManagerWorkerHeavenState}
        """
        self.debug("returning worker heaven state %r" % self.vishnu.state)
        return self.vishnu.workerHeaven.state

    def perspective_shutdown(self):
        """
        Shut down the manager.

        @raise SystemExit: always
        """
        print 'SHUTTING DOWN'
        reactor.stop()
        raise SystemExit

    def perspective_componentStart(self, componentState):
        """
        Start the given component.  The component should be sleeping before
        this.

        @type componentState: L{planet.ManagerComponentState}
        """
        self.debug('perspective_componentStart(%r)' % componentState)
        return self.vishnu.componentCreate(componentState)
        
    def perspective_componentStop(self, componentState):
        """
        Stop the given component.
        If the component was sad, we clear its sad state as well,
        since the stop was explicitly requested by the admin.

        @type componentState: L{planet.ManagerComponentState}
        """
        self.debug('perspective_componentStop(%r)' % componentState)
        d = self.perspective_componentCallRemote(componentState, 'stop')
        def clearSadCallback(result):
            if componentState.get('mood') == planet.moods.sad.value:
                self.debug('clearing sad mood after stopping component')
                componentState.set('mood', planet.moods.sleeping.value)
            return result
        d.addCallback(clearSadCallback)

        return d
        
    def perspective_componentRestart(self, componentState):
        """
        Restart the given component.

        @type componentState: L{planet.ManagerComponentState}
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
        
        @param componentState: state of the component to call the method on
        @type  componentState: L{planet.ManagerComponentState}
        @param methodName:     name of the method to call.  Gets proxied to
                               L{flumotion.component.component.""" \
                               """BaseComponentMedium}'s remote_(methodName)
        @type  methodName:     str

        @rtype: L{twisted.internet.defer.Deferred}
        """
        assert isinstance(componentState, planet.ManagerComponentState)

        if methodName == "start":
            self.warning('forwarding "start" to perspective_componentStart')
            return self.perspective_componentStart(componentState)

        m = self.vishnu.getComponentMapper(componentState)
        avatar = m.avatar

        # if the component is sad, not running, and we're asked to stop it,
        # do so so the state gets cleared
        if methodName == "stop" and componentState.get('mood') == planet.moods.sad.value and not avatar:
            self.debug('asked to stop a sad component without avatar')
            componentState.set('mood', planet.moods.sleeping.value)
            return defer.succeed(None)
        
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

        @param workerName: the worker to call
        @type  workerName: str
        @param methodName: Name of the method to call.  Gets proxied to
                           L{flumotion.worker.worker.WorkerMedium} 's
                           remote_(methodName)
        @type  methodName: str
        """
        
        self.debug('AdminAvatar.workerCallRemote(%r, %r)' % (
            workerName, methodName))
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

        Returns: a (filename, methodName) tuple, or raises a Failure
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
        """
        Reload modules in the given component.

        @param componentState: state of the component to reload
        @type  componentState: L{planet.ManagerComponentState}
        """
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
        """
        Reload modules in the manager.
        """
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

        @rtype: str
        """
        return self.vishnu.getConfiguration()

    def perspective_loadConfiguration(self, xml):
        """
        Load the given XML configuration into the manager.
        @type  xml: str
        """
        self.info('loadConfiguration ...')
        f = StringIO(xml)
        res = self.vishnu.loadConfigurationXML(f, self.remoteIdentity)
        f.close()
        return res

    def perspective_deleteFlow(self, flowName):
        return self.vishnu.deleteFlow(flowName)

    def perspective_deleteComponent(self, componentState):
        """Delete a component from the manager.

        A component can only be deleted when it is sleeping or sad. It
        is the caller's job to ensure this is the case; calling this
        function on a running component will raise a ComponentBusyError.

        @returns: a deferred that will fire when all listeners have been
        notified of the component removal
        """
        return self.vishnu.deleteComponent(componentState)

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
    implements(interfaces.IHeaven)
    avatarClass = AdminAvatar

    def __init__(self, vishnu):
        # doc in base class
        base.ManagerHeaven.__init__(self, vishnu)
        #FIXME: don't add a log handler here until we have a good way
        #of filtering client-side again
        #log.addLogHandler(self.logHandler)
        self._logcache = []

    #def logHandler(self, category, type, message):
    #    self.logcache.append((category, type, message))
    #    for avatar in self.getAvatars():
    #        avatar.sendLog(category, type, message)

    #def sendCache(self, avatar):
    #    if not avatar.hasRemoteReference():
    #        reactor.callLater(0.25, self.sendCache, avatar)
    #        return
        
        # FIXME: do this on request only
        #self.debug('sending logcache to client (%d messages)' % len(self.logcache))
        #for category, type, message in self.logcache:
        #    avatar.sendLog(category, type, message)
        
    ### my methods

    def avatarsCallRemote(self, methodName, *args, **kwargs):
        """
        Call a remote method on all AdminAvatars in this heaven.

        @param methodName: Name of the method to call.  Gets proxied to
                           L{flumotion.admin.admin.AdminModel}'s
                           remote_(methodName)
        @type  methodName: str
        """
        for avatar in self.getAvatars():
            avatar.mindCallRemote(methodName, *args, **kwargs)
