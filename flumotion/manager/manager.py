# -*- Mode: Python; test-case-name: flumotion.test.test_manager_manager -*-
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
manager implementation and related classes

API Stability: semi-stable
"""

__all__ = ['ManagerServerFactory', 'Vishnu']

import os

from twisted.internet import reactor, defer
from twisted.cred import error
from twisted.python import components, failure
from twisted.spread import pb
from twisted.cred import portal

from flumotion.common import bundle, config, errors, interfaces, log, registry
from flumotion.common import planet, common
from flumotion.common.planet import moods
from flumotion.configure import configure
from flumotion.manager import admin, component, worker, base
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

        raise errors.NoPerspectiveError("%s requesting iface %r" % (
            avatarId, repr(ifaces)))
        
    def registerHeaven(self, heaven, interface):
        """
        Register a Heaven as managing components with the given interface.

        @type interface:  L{twisted.python.components.Interface}
        @param interface: a component interface to register the heaven with.
        """
        assert isinstance(heaven, base.ManagerHeaven)
       
        self._interfaceHeavens[interface] = heaven

class ComponentMapper:
    """
    I am an object that ties together different objects related to a
    component.  I am used as values in a lookup hash in the vishnu.
    """
    def __init__(self):
        self.state = None       # ManagerComponentState; created first
        self.id = None          # avatarId of the eventual ComponentAvatar
        self.avatar = None      # ComponentAvatar
        self.jobState = None    # ManagerJobState of a running component

class Vishnu(log.Loggable):
    """
    I am the toplevel manager object that knows about all heavens and factories.
    """
    logCategory = "vishnu"
    def __init__(self, unsafeTracebacks=0):
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

        self._componentMappers = {} # any object -> ComponentMapper

        self.state = planet.ManagerPlanetState()
        # FIXME: name
        self.state.set('name', 'gimmeaname')

        # create a portal so that I can be connected to, through our dispatcher
        # implementing the IRealm and a bouncer
        # FIXME: decide if we allow anonymous login in this small (?) window
        self.portal = fportal.BouncerPortal(self.dispatcher, None)
        #unsafeTracebacks = 1 # for debugging tracebacks to clients
        self.factory = pb.PBServerFactory(self.portal,
            unsafeTracebacks=unsafeTracebacks)

        self.configuration = None

    # FIXME: do we want a filename to load config, or data directly ?
    # FIXME: well, I think we want to have an "object" with an "interface"
    # FIXME: that gives you "the config", instead of this broken piece
    def loadConfiguration(self, filename, data=None):
        """
        Load the configuration from the given filename, merging it on
        top of the currently running configuration.
        """
        self.debug('loading configuration')
        # FIXME: we should be able to create "wanted" config/state from
        # something else than XML as well
        conf = config.FlumotionConfigXML(filename, data)

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

        # make component heaven
        # load the configuration as well
        # FIXME: we should only handle the added conf, so we get the changes
        # parsing should also be done only once
        self.componentHeaven.loadConfiguration(filename, data)

        # now add stuff from the config that did not exist in self.state yet
        self.debug('syncing up planet state with config')
        if conf.atmosphere:
            for c in conf.atmosphere.components:
                self.debug('FIXME: checking config component %s' % c.name)

        if conf.flows:
            for f in conf.flows:
                self.debug('checking flow %s' % f.name)
                # check if we have this flow yet
                isOurFlow = lambda x: x.get('name') == f.name
                l = filter(isOurFlow, self.state.get('flows'))
                if len(l) == 0:
                    self.info('Creating flow "%s"' % f.name)
                    flow = planet.ManagerFlowState()
                    flow.set('name', f.name)
                    flow.set('parent', self.state)
                    self.state.append('flows', flow)
                else:
                    flow = l[0]
                
                for c in f.components.values():
                    self.info('Adding component "%s" to flow "%s"' % (
                        c.name, f.name))
                    self.debug('checking config component %s' % c.name)
                    isOurComponent = lambda x: x.get('name') == c.name
                    l = filter(isOurComponent, flow.get('components'))
                    if len(l) == 0:
                        self.debug('adding component %s' % c.name)
                        comp = planet.ManagerComponentState()
                        comp.set('name', c.name)
                        comp.set('type', c.getType())
                        comp.set('workerRequested', c.worker)
                        comp.set('parent', flow)
                        comp.set('mood', moods.sleeping.value)
                        comp.set('config', c.getConfigDict())
                        flow.append('components', comp)

                        # FIXME: when we use full paths for avatarId
                        #parentName = flow.get('name')
                        #avatarId = common.componentPath(c.name, parentName)
                        avatarId = c.name

                        # add to mapper
                        m = ComponentMapper()
                        m.state = comp
                        m.id = avatarId
                        self._componentMappers[comp] = m
                        self._componentMappers[avatarId] = m

        # now start all components that need starting
        components = self._getComponentsToStart()
        for workerId in self.workerHeaven.avatars.keys():
            # filter the ones that have no worker requested or a match
            isRightWorker = lambda c: not (c.get('workerRequested') and
            c.get('workerRequested') != workerId)
            ours = filter(isRightWorker, components)

            if not ours:
                self.debug('no components scheduled for worker %s' % workerId)
            else:
                avatar = self.workerHeaven.avatars[workerId]
                self._workerStartComponents(avatar, ours)
            # make sure components with no worker specified don't get started
            # on all different workers
            for c in ours:
                components.remove(c)
 
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
       
    # FIXME: unify naming of stuff like this
    def workerAttached(self, workerAvatar):
        # called when a worker logs in
        workerId = workerAvatar.avatarId
        self.debug('vishnu.workerAttached(): id %s' % workerId)

        # get all components that are supposed to start on this worker
        # FIXME: we start them one by one to make port assignment more
        # deterministic
        # FIXME: we should probably start them in the correct order,
        # respecting the graph
        components = self._getComponentsToStart()

        # filter the ones that have no worker requested or a match
        isRightWorker = lambda c: not (c.get('workerRequested') and
            c.get('workerRequested') != workerId)
        components = filter(isRightWorker, components)

        if not components:
            self.debug('vishnu.workerAttached(): no components for this worker')
            return

        self._workerStartComponents(workerAvatar, components)
            
    def _workerStartComponents(self, workerAvatar, components):
        """
        Start the list of components on the given worker, sequentially.

        @type  workerAvatar: L{flumotion.manager.worker.WorkerAvatar}
        @type  components:   list of
                             L{flumotion.common.planet.ManagerComponentState}
        """
        names = [c.get('name') for c in components]
        self.debug('starting components %r' % names)
        
        d = defer.Deferred()

        for c in components:
            componentName = c.get('name')
            parentName = c.get('parent').get('name')
            type = c.get('type')
            config = c.get('config')
            self.debug('workerAttached(): scheduling start of /%s/%s on %s' % (
                parentName, componentName, workerAvatar.avatarId))
            
            # FIXME: put in parent when we use it everywhere
            #d.addCallback(self._workerStartComponentDelay,
            #    workerName, componentName, parentName,
            #    entry.getType(), entry.getConfigDict())
            d.addCallback(self._workerStartComponentDelayed,
                workerAvatar, c, type, config)

        d.addCallback(lambda result: self.debug(
            'workerAttached(): completed start chain'))

        # now trigger the chain
        self.debug('workerAttached(): triggering start chain')
        d.callback(None)
        #reactor.callLater(0, d.callback, None)

        #def _workerStartComponentDelay(self, result, worker, component, parent,
        #type, config):
        #    d = self.workerStartComponent(worker, component, parent, type, config)
    def _workerStartComponentDelayed(self, result, workerAvatar,
            componentState, type, config):

        m = self._componentMappers[componentState]
        avatarId = m.id

        # FIXME: rename to startComp
        d = workerAvatar.start(avatarId, type, config)
        # FIXME: here we get the avatar Id of the component we wanted
        # started, so now attach it to the planetState's component state
        d.addCallback(self._startCallback, componentState)

    def _startCallback(self, result, componentState):
        self.debug('got avatarId %s for state %s' % (result, componentState))
        m = self._componentMappers[componentState]
        assert result == m.id, "received id %s is not the expected id %s" % (
            result, m.id)

    def workerDetached(self, workerAvatar):
        # called when a worker logs out
        workerId = workerAvatar.avatarId
        self.debug('vishnu.workerDetached(): id %s' % workerId)

    def componentAttached(self, componentAvatar):
        id = componentAvatar.avatarId
        if not id in self._componentMappers.keys():
            self.warning('id %s not found' % id)
            return
        m = self._componentMappers[id]
        m.avatar = componentAvatar
        self._componentMappers[componentAvatar] = m

    def registerComponent(self, componentAvatar):
        # called when the jobstate is retrieved
        self.debug('registering component %r' % componentAvatar)

        #if not componentAvatar in self._componentMappers.keys():
        #    self.warning('avatar %r not found' % componentAvatar)
        #    return

        # map jobState
        jobState = componentAvatar.jobState
        m = self._componentMappers[componentAvatar]
        m.jobState = jobState
        self._componentMappers[jobState] = m

        # attach jobState to state
        m.state.setJobState(jobState)

        # attach componentstate to avatar
        componentAvatar.componentState = m.state
        
    def unregisterComponent(self, componentAvatar):
        # called when the component has logged out
        # clear up jobState and avatar
        self.debug('unregisterComponent(%r): cleaning up state' %
            componentAvatar)

        m = self._componentMappers[componentAvatar]

        # unmap jobstate
        del self._componentMappers[m.jobState]
        m.jobState = None
        
        m.state.set('mood', moods.sleeping.value)
        m.state.set('pid', None)
        m.state.set('workerName', None)
        m.state.set('message', 'Component "%s" logged out' %
            m.state.get('name'))

        # detach componentstate from avatar
        componentAvatar.componentState = None

        # unmap avatar
        del self._componentMappers[m.avatar]
        m.avatar = None
        
    def getComponentStates(self):
        list = self.state.getComponents()
        self.debug('getComponentStates(): %d components' % len(list))
        for c in list:
            self.log(repr(c))
            mood = c.get('mood')
            if mood == None:
                self.warning('%s has mood None' % c.get('name'))

        return list

    def emptyPlanet(self):
        """
        Empty the planet of all atmospheres, components, and flows.
        """
        # first get all components to sleep
        components = self.getComponentStates()

        # if any component is already in a mood change/command, fail
        isPending = lambda c: c.get('moodPending') != None
        components = filter(isPending, components)
        if len(components) > 0:
            raise errors.BusyComponentError(components[0])

        # filter out the ones that aren't sleeping and stop them
        components = self.getComponentStates()
        isNotSleeping = lambda c: c.get('mood') is not moods.sleeping.value
        components = filter(isNotSleeping, components)

        # create a big deferred for stopping everything
        d = defer.Deferred()
        
        self.debug('need to stop %d components: %r' % (
            len(components), components))

        for c in components:
            avatar = self._componentMappers[c].avatar
            d.addCallback(lambda result, a: a.stop(), avatar)

        d.addCallback(self._emptyPlanetCallback)

        # trigger the deferred after returning
        reactor.callLater(0, d.callback, None)

        return d
        
    def _emptyPlanetCallback(self, result):
        # gets called after all components have stopped
        # cleans up the rest of the planet state
        components = self.getComponentStates()

        for c in components:
            if c.get('mood') is not moods.sleeping.value:
                self.warning('Component %s is not sleeping' % c.get('name'))
            # clear mapper; componentstate should be the last thing in here
            del self._componentMappers[c]

        # if anything's left, we have a mistake somewhere
        l = self._componentMappers.keys()
        if len(l) > 0:
            self.warning('mappers still has keys %r' % (repr(l)))

        self.state.get('atmosphere').empty()

        for f in self.state.get('flows'):
            f.empty()
            self.state.remove('flows', f)
       
    def _getComponentsToStart(self):
        # return a list of components that are sleeping and not pending
        components = self.state.getComponents()

        # filter the ones that are sleeping and not pending
        isSleeping = lambda c: c.get('mood') == moods.sleeping.value
        components = filter(isSleeping, components)
        isNotPending = lambda c: c.get('moodPending') == None
        components = filter(isNotPending, components)

        return components

 
