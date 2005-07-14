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
from flumotion.common import planet, common, dag
from flumotion.common.planet import moods
from flumotion.configure import configure
from flumotion.manager import admin, component, worker, base
from flumotion.twisted import checkers
from flumotion.twisted import portal as fportal
from flumotion.twisted.defer import defer_generator_method


def find(list, value, proc=lambda x: x):
    return list[[proc(x) for x in list].index(value)]

def first(list, proc=lambda x: x):
    for x in list:
        if proc(x): return x

def any(list, proc=lambda x: x):
    return filter(proc, list)

def fint(*procs):
    # intersection of functions
    def int(*args, **kwargs):
        for p in procs:
            if not p(*args, **kwargs): return False
        return True
    return int


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
        # FIXME: there needs to be a way to not have to do a callLater
        # blindly so cleanup can be guaranteed
        reactor.callLater(0, avatar.attached, mind)

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
    def __init__(self, name, unsafeTracebacks=0):
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
        self.state.set('name', name)

        self._dag = dag.DAG() # component dependency graph
        
        # create a portal so that I can be connected to, through our dispatcher
        # implementing the IRealm and a bouncer
        # FIXME: decide if we allow anonymous login in this small (?) window
        self.portal = fportal.BouncerPortal(self.dispatcher, None)
        #unsafeTracebacks = 1 # for debugging tracebacks to clients
        self.factory = pb.PBServerFactory(self.portal,
            unsafeTracebacks=unsafeTracebacks)

        self.configuration = None

    def getConfiguration(self):
        """Returns the manager's configuration as a string suitable for
        importing via loadConfiguration().
        """
        if self.configuration:
            return self.configuration.export()
        else:
            return None

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
        self.configuration = conf = config.FlumotionConfigXML(filename, data)

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
            from flumotion.worker import job
            bouncer = job.getComponent(configDict, defs)
            self.setBouncer(bouncer)
            self.bouncer.debug('started')
            log.info('manager', "Started manager's bouncer")

        # make component heaven
        # load the configuration as well
        # FIXME: we should only handle the added conf, so we get the changes
        # parsing should also be done only once
        self.componentHeaven.loadConfiguration(filename, data)

        # now add stuff from the config that did not exist in self.state yet
        self.debug('syncing up planet state with config')
        added = [] # added components while parsing
        
        if conf.atmosphere:
            self.debug('checking atmosphere components %r' % conf.atmosphere.components)
            for c in conf.atmosphere.components.values():
                self.debug('checking atmosphere config component %s' % c.name)
                isOurComponent = lambda x: x.get('name') == c.name
                atmosphere = self.state.get('atmosphere')
                l = filter(isOurComponent, atmosphere.get('components'))
                if len(l) == 0:
                    self.info('Adding component "%s" to atmosphere' % c.name)
                    state = self._addComponent(c, atmosphere)
                    added.append(state)

        if conf.flows:
            for f in conf.flows:
                self.debug('checking flow %s' % f.name)
                # check if we have this flow yet and add if not
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
                    self.debug('checking config component %s' % c.name)
                    isOurComponent = lambda x: x.get('name') == c.name
                    l = filter(isOurComponent, flow.get('components'))
                    if len(l) == 0:
                        self.info('Adding component "%s" to flow "%s"' % (
                            c.name, f.name))
                        state = self._addComponent(c, flow)
                        added.append(state)

        # register dependencies of added components
        for state in added:
            self.debug('registering dependencies of %r' % state)
            dict = state.get('config')

            if not dict.has_key('source'):
                continue

            list = dict['source']

            # FIXME: there's a bug in config parsing - sometimes this gives us
            # one string, and sometimes a list of one string, and sometimes
            # a list
            if isinstance(list, str):
                list = [list, ]
            for eater in list:
                name = eater
                if ':' in name:
                    name = eater.split(':')[0]

                flowName = state.get('parent').get('name')
                avatarId = common.componentPath(name, flowName)
                parentState = self._componentMappers[avatarId].state
                self.debug('depending %r on %r' % (state, parentState))
                self._dag.addEdge(parentState, state)

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
 
    def _addComponent(self, config, parent):
        """
        Add a component state for the given component config entry.

        @returns: L{flumotion.common.planet.ManagerComponentState}
        """

        self.debug('adding component %s' % config.name)
        
        state = planet.ManagerComponentState()
        state.set('name', config.name)
        state.set('type', config.getType())
        state.set('workerRequested', config.worker)
        state.set('mood', moods.sleeping.value)
        state.set('config', config.getConfigDict())

        state.set('parent', parent)
        parent.append('components', state)

        parentName = parent.get('name')
        avatarId = common.componentPath(config.name, parentName)

        # add to mapper
        m = ComponentMapper()
        m.state = state
        m.id = avatarId
        self._componentMappers[state] = m
        self._componentMappers[avatarId] = m

        # add nodes to graph
        self._dag.addNode(state)

        return state

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
       
    def componentStart(self, componentState):
        """
        Start the given component.

        The component should be sleeping.
        The worker it should be started on should be present.
        """
        m = componentState.get('mood')
        if m != moods.sleeping.value:
            raise errors.ComponentMoodError("%r not sleeping" % componentState)

        p = componentState.get('moodPending')
        if p != None:
            raise errors.ComponentMoodError(
                "%r already has a pending mood %s" % moods.get(p).name)

        # find a worker this component can start on
        worker = None

        # prefer the worker name in the state if it's there - it's the name
        # of the worker it last ran on
        w = componentState.get('workerName')
        if w:
            if not self.workerHeaven.hasAvatar(w):
                raise errors.ComponentNoWorkerError(
                    "worker %s is not logged in" % w)
            worker = self.workerHeaven.getAvatar(w)

        # otherwise, check workerRequested, and find a matching worker
        if not worker:
            r = componentState.get('workerRequested')
            if r:
                if not self.workerHeaven.hasAvatar(r):
                    raise errors.ComponentNoWorkerError(
                        "worker %s is not logged in" % r)
                worker = self.workerHeaven.getAvatar(r)
            else:
                # any worker will do
                list = self.workerHeaven.getAvatars()
                if list:
                    worker = list[0]

        if not worker:
            raise errors.ComponentNoWorkerError(
                "Could not find any worker to start on")

        # now that we have a worker, get started
        return self._workerStartComponents(worker, [componentState])

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
            self.debug('_workerStartComponents(): scheduling start of /%s/%s on %s' % (
                parentName, componentName, workerAvatar.avatarId))
            
            d.addCallback(self._workerStartComponentDelayed,
                workerAvatar, c, type, config)

        d.addCallback(lambda result: self.debug(
            '_workerStartComponents(): completed start chain'))

        # now trigger the chain
        self.debug('_workerStartComponents(): triggering start chain')
        d.callback(None)
        #reactor.callLater(0, d.callback, None)
        return d

    def _workerStartComponentDelayed(self, result, workerAvatar,
            componentState, type, config):

        m = self._componentMappers[componentState]
        avatarId = m.id

        # FIXME: rename to startComp
        d = workerAvatar.start(avatarId, type, config)
        # FIXME: here we get the avatar Id of the component we wanted
        # started, so now attach it to the planetState's component state
        d.addCallback(self._startCallback, componentState)
        d.addErrback(self._startErrback, componentState)

    def _startCallback(self, result, componentState):
        self.debug('got avatarId %s for state %s' % (result, componentState))
        m = self._componentMappers[componentState]
        assert result == m.id, "received id %s is not the expected id %s" % (
            result, m.id)

    def _startErrback(self, error, state):
        # FIXME: make ConfigError copyable so we can .check() it here
        # and print a nicer warning
        self.warning('failed to start component %s: %s'
                  % (state.get('name'), error.getErrorMessage()))
        return None

    def workerDetached(self, workerAvatar):
        # called when a worker logs out
        workerId = workerAvatar.avatarId
        self.debug('vishnu.workerDetached(): id %s' % workerId)

    def _configToComponentState(self, config, avatar):
        assert not avatar.avatarId in self._componentMappers.keys()

        state = planet.ManagerComponentState()
        state.set('name', config['name'])
        state.set('type', config['type'])
        state.set('workerRequested', None)
        state.set('mood', moods.waking.value)
        state.set('config', config)

        # check if we have this flow yet and add if not
        isOurFlow = lambda x: x.get('name') == config['parent']
        flow = first(self.state.get('flows'), isOurFlow)
        if not flow:
            self.info('Creating flow "%s"' % config['parent'])
            flow = planet.ManagerFlowState()
            flow.set('name', config['parent'])
            flow.set('parent', self.state)
            self.state.append('flows', flow)

        state.set('parent', flow)
        flow.append('components', state)

        # add to mapper
        m = ComponentMapper()
        m.state = state
        m.id = avatar.avatarId
        self._componentMappers[m.state] = m
        self._componentMappers[m.id] = m

        # add nodes to graph
        self._dag.addNode(state)

        return self.componentAttached(avatar)

    def componentAttached(self, componentAvatar):
        # called when a component logs in and gets a component avatar created
        id = componentAvatar.avatarId
        if not id in self._componentMappers.keys():
            # the manager quit and the component is logging back in
            d = componentAvatar.mindCallRemote('getConfig')
            d.addCallback(self._configToComponentState, componentAvatar)
            return d
        m = self._componentMappers[id]
        m.avatar = componentAvatar
        self._componentMappers[componentAvatar] = m

        # attach componentstate to avatar
        componentAvatar.componentState = m.state
        return defer.succeed(None)

    def componentDetached(self, componentAvatar):
        # called when the component has detached

        # detach componentstate fom avatar
        componentAvatar.componentState = None
        
    def registerComponent(self, componentAvatar):
        # called when the jobstate is retrieved
        self.debug('vishnu registering component %r' % componentAvatar)

        # map jobState
        jobState = componentAvatar.jobState
        m = self._componentMappers[componentAvatar]
        m.jobState = jobState
        self._componentMappers[jobState] = m

        # attach jobState to state
        m.state.setJobState(jobState)

        self.debug('vishnu registered component %r' % componentAvatar)
        
    def unregisterComponent(self, componentAvatar):
        # called when the component is logging out
        # clear up jobState and avatar
        self.debug('unregisterComponent(%r): cleaning up state' %
            componentAvatar)

        m = self._componentMappers[componentAvatar]

        # unmap jobstate
        try:
            del self._componentMappers[m.jobState]
        except KeyError:
            self.warning('Could not remove jobState for %r' % componentAvatar)
        m.jobState = None
        
        m.state.set('mood', moods.sleeping.value)
        m.state.set('pid', None)
        m.state.set('cpu', None)
        m.state.set('workerName', None)
        m.state.set('message', 'Component "%s" logged out' %
            m.state.get('name'))

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

    def deleteFlow(self, flowName):
        """
        Empty the planet of all components, and flows.

        @returns: a deferred that will fire when the planet is empty.
        """

        # first get all components to sleep
        flow = find(self.state.get('flows'), flowName, lambda x: x.get('name'))
        components = flow.get('components')

        # if any component is already in a mood change/command, fail
        isBusy = lambda c: c.get('moodPending') != None
        isNotSleeping = lambda c: c.get('mood') is not moods.sleeping.value
        pred = fint(isBusy, isNotSleeping)
        if any(components, pred):
            raise errors.BusyComponentError(first(components, pred))

        for c in components:
            del self._componentMappers[self._componentMappers[c].id]
            del self._componentMappers[c]
        yield flow.empty()
        yield self.state.remove('flows', flow)
    deleteFlow = defer_generator_method(deleteFlow)
        
    def emptyPlanet(self):
        """
        Empty the planet of all components, and flows.

        @returns: a deferred that will fire when the planet is empty.
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

        # FIXME: this is where we need some order
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
        self.debug('_emptyPlanetCallback: need to delete %d components' %
            len(components))

        for c in components:
            if c.get('mood') is not moods.sleeping.value:
                self.warning('Component %s is not sleeping' % c.get('name'))
            # clear mapper; remove componentstate and id
            m = self._componentMappers[c]
            del self._componentMappers[m.id]
            del self._componentMappers[c]

        # if anything's left, we have a mistake somewhere
        l = self._componentMappers.keys()
        if len(l) > 0:
            self.warning('mappers still has keys %r' % (repr(l)))

        list = []

        list.append(self.state.get('atmosphere').empty())

        for f in self.state.get('flows'):
            self.debug('appending deferred for emptying flow %r' % f)
            list.append(f.empty())
            self.debug('appending deferred for removing flow %r' % f)
            list.append(self.state.remove('flows', f))
            self.debug('appended deferreds')

        dl = defer.DeferredList(list)
        return dl
       
    def _getComponentsToStart(self):
        # return a list of components that are sleeping and not pending
        components = self.state.getComponents()

        # filter the ones that are sleeping and not pending
        isSleeping = lambda c: c.get('mood') == moods.sleeping.value
        components = filter(isSleeping, components)
        isNotPending = lambda c: c.get('moodPending') == None
        components = filter(isNotPending, components)

        return components

 
    def getComponentMapper(self, object):
        """
        Look up an object mapper given the object.

        @rtype: L{ComponentMapper} or None
        """
        if object in self._componentMappers.keys():
            return self._componentMappers[object]

        return None
