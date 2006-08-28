# -*- Mode: Python; test-case-name: flumotion.test.test_manager_manager -*-
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
manager implementation and related classes

API Stability: semi-stable
"""

__all__ = ['ManagerServerFactory', 'Vishnu']

from twisted.internet import reactor, defer
from twisted.cred import error
from twisted.python import components, failure
from twisted.spread import pb
from twisted.cred import portal

from flumotion.common import bundle, config, errors, interfaces, log, registry
from flumotion.common import planet, common, dag, messages, reflectcall, server
from flumotion.common.identity import RemoteIdentity
from flumotion.common.planet import moods
from flumotion.configure import configure
from flumotion.manager import admin, component, worker, base, depgraph
from flumotion.twisted import checkers
from flumotion.twisted import portal as fportal
from flumotion.twisted.defer import defer_generator_method
from flumotion.twisted.compat import implements
from flumotion.common.messages import N_
T_ = messages.gettexter('flumotion')

def _find(list, value, proc=lambda x: x):
    return list[[proc(x) for x in list].index(value)]

def _first(list, proc=lambda x: x):
    for x in list:
        if proc(x): return x

def _any(list, proc=lambda x: x):
    return filter(proc, list)

def _fint(*procs):
    # intersection of functions
    def int(*args, **kwargs):
        for p in procs:
            if not p(*args, **kwargs): return False
        return True
    return int

RUNNING_LOCALLY = ('loadConfiguration being called from main.py, no '
                   'need for authentication')

# an internal class
class Dispatcher(log.Loggable):
    """
    I implement L{twisted.cred.portal.IRealm}.
    I make sure that when a L{pb.Avatar} is requested through me, the
    Avatar being returned knows about the mind (client) requesting
    the Avatar.
    """
    
    implements(portal.IRealm)

    logCategory = 'dispatcher'

    def __init__(self, computeIdentity):
        self._interfaceHeavens = {} # interface -> heaven
        self._avatarHeavens = {} # avatarId -> heaven
        self._computeIdentity = computeIdentity
        
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
    def requestAvatar(self, avatarId, keycard, mind, *ifaces):
        def got_avatar(avatar):
            # OK so this is byzantine, but test_manager_manager actually
            # uses these kwargs to set its own info. so don't change
            # these args or their order or you will break your test
            # suite.
            def cleanup(avatarId=avatarId, avatar=avatar, mind=mind):
                self.removeAvatar(avatarId, avatar, mind)
            # schedule a perspective attached for after this function
            # FIXME: there needs to be a way to not have to do a callLater
            # blindly so cleanup can be guaranteed
            reactor.callLater(0, avatar.attached, mind)
            return (pb.IPerspective, avatar, cleanup)
        def got_error(failure):
            failure.trap(errors.AlreadyConnectedError)
            self.info("component with id %s already logged in" % (avatarId))
            return failure

        host = common.addressGetHost(mind.broker.transport.getPeer())
        d = self.createAvatarFor(avatarId, keycard, host, ifaces)
        d.addCallbacks(got_avatar, got_error)
        return d

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

    def createAvatarFor(self, avatarId, keycard, remoteHost, ifaces):
        """
        Create an avatar from the heaven implementing the given interface.

        @type avatarId:    string
        @param avatarId:   the name of the new avatar
        @type keycard:     L{flumotion.common.keycards.Keycard}
        @param keycard:    the credentials being used to log in
        @type remoteHost:  str
        @param remoteHost: the remote host
        @type ifaces:      tuple of interfaces linked to heaven
        @param ifaces:     a list of heaven interfaces to get avatar from,
                           including pb.IPerspective

        @returns:          a deferred that will fire with an avatar from
                           the heaven managing the given interface.
        """
        def got_identity(identity):
            for iface in ifaces:
                heaven = self._interfaceHeavens.get(iface, None)
                if heaven:
                    avatar = heaven.createAvatar(avatarId, identity)
                    self._avatarHeavens[avatarId] = heaven
                    return avatar
            raise errors.NoPerspectiveError("%s requesting iface %r",
                                            avatarId, ifaces)
            

        if not pb.IPerspective in ifaces:
            raise errors.NoPerspectiveError(avatarId)
        d = self._computeIdentity(keycard, remoteHost)
        d.addCallback(got_identity)
        return d

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

    @cvar dispatcher:      dispatcher to create avatars
    @type dispatcher:      L{Dispatcher}
    @cvar workerHeaven:    the worker heaven
    @type workerHeaven:    L{worker.WorkerHeaven}
    @cvar componentHeaven: the component heaven
    @type componentHeaven: L{component.ComponentHeaven}
    @cvar adminHeaven:     the admin heaven
    @type adminHeaven:     L{admin.AdminHeaven}
    """

    implements(server.IServable)

    logCategory = "vishnu"

    def __init__(self, name, unsafeTracebacks=0):
        # create a Dispatcher which will hand out avatars to clients
        # connecting to me
        self.dispatcher = Dispatcher(self.computeIdentity)

        self.workerHeaven = self._createHeaven(interfaces.IWorkerMedium,
                                               worker.WorkerHeaven)
        self.componentHeaven = self._createHeaven(interfaces.IComponentMedium,
                                                  component.ComponentHeaven)
        self.adminHeaven = self._createHeaven(interfaces.IAdminMedium,
                                              admin.AdminHeaven)
        
        self.bouncer = None # used by manager to authenticate worker/component
        
        self.bundlerBasket = registry.getRegistry().makeBundlerBasket()

        self._componentMappers = {} # any object -> ComponentMapper

        self.state = planet.ManagerPlanetState()
        self.state.set('name', name)

        self.plugs = {} # socket -> list of plugs

        self._depgraph = depgraph.DepGraph()
        
        # create a portal so that I can be connected to, through our dispatcher
        # implementing the IRealm and a bouncer
        # FIXME: decide if we allow anonymous login in this small (?) window
        self.portal = fportal.BouncerPortal(self.dispatcher, None)
        #unsafeTracebacks = 1 # for debugging tracebacks to clients
        self.factory = pb.PBServerFactory(self.portal,
            unsafeTracebacks=unsafeTracebacks)

        self.connectionInfo = {}
        self.setConnectionInfo(None, None, None)

        self.configuration = None

    def setConnectionInfo(self, host, port, use_ssl):
        info = dict(host=host, port=port, use_ssl=use_ssl)
        self.connectionInfo.update(info)

    def getConfiguration(self):
        """Returns the manager's configuration as a string suitable for
        importing via loadConfiguration().
        """
        if self.configuration:
            return self.configuration.export()
        else:
            return None

    def getBundlerBasket(self):
        """
        Return a bundler basket to unbundle from.
        If the registry files were updated since the last time, the
        bundlerbasket will be rebuilt.

        @since: 0.2.2
        @rtype: L{flumotion.common.bundle.BundlerBasket}
        """
        if registry.getRegistry().rebuildNeeded():
            self.info("Registry changed, rebuilding")
            registry.getRegistry().verify()
            self.bundlerBasket = registry.getRegistry().makeBundlerBasket()
        return self.bundlerBasket
        
    def adminAction(self, remoteIdentity, message, args, kw):
        socket = 'flumotion.component.plugs.adminaction.AdminAction'
        if self.plugs.has_key(socket):
            for plug in self.plugs[socket]:
                plug.action(remoteIdentity, message, args, kw)

    def computeIdentity(self, keycard, host):
        """
        Compute a suitable identity for a remote host. First looks to
        see if there is a
        flumotion.component.plugs.identity.IdentityProvider plug
        installed on the manager, falling back to user@host.

        The identity is only used in the adminaction interface. An
        example of its use is when you have an adminaction plug that
        checks an admin's privileges before actually doing an action;
        the identity object you use here might store the privileges that
        the admin has.

        @param keycard: the keycard that the remote host used to log in.
        @type  keycard: L{flumotion.common.keycards.Keycard}
        @param host: the ip of the remote host
        @type  host: str

        @rtype: a deferred that will fire a
        L{flumotion.common.identity.RemoteIdentity}
        """

        socket = 'flumotion.component.plugs.identity.IdentityProvider'
        if self.plugs.has_key(socket):
            for plug in self.plugs[socket]:
                identity = plug.computeIdentity(keycard, host)
                if identity:
                    return identity
        username = getattr(keycard, 'username', None)
        return defer.succeed(RemoteIdentity(username, host))

    def _makeBouncer(self, conf, remoteIdentity):
        # returns a deferred, always
        if not (conf.manager and conf.manager.bouncer):
            self.log('no bouncer in config')
            return defer.succeed(None)

        self.debug('going to start manager bouncer %s of type %s' % (
            conf.manager.bouncer.name, conf.manager.bouncer.type))

        if remoteIdentity != RUNNING_LOCALLY:
            self.adminAction(remoteIdentity, '_makeBouncer', (conf,), {})

        defs = registry.getRegistry().getComponent(
            conf.manager.bouncer.type)
        entry = defs.getEntryByType('component')
        # FIXME: use entry.getModuleName() (doesn't work atm?)
        moduleName = defs.getSource()
        methodName = entry.getFunction()
        bouncer = reflectcall.createComponent(moduleName, methodName)

        configDict = conf.manager.bouncer.getConfigDict()
        self.debug('setting up manager bouncer')
        d = bouncer.setup(configDict)
        def setupCallback(result):
            bouncer.debug('started')
            self.setBouncer(bouncer)
        def setupErrback(failure):
            failure.trap(errors.ConfigError)
            self.warning('Configuration error in manager bouncer: %s' %
                failure.value.args[0])
        d.addCallback(setupCallback)
        d.addErrback(setupErrback)
        return d

    def _addManagerPlug(self, socket, args, remoteIdentity):
        self.debug('loading plug type %s for socket %s'
                   % (args['type'], socket))

        if remoteIdentity != RUNNING_LOCALLY:
            self.adminAction(remoteIdentity, '_addManagerPlug',
                             (socket, args), {})

        defs = registry.getRegistry().getPlug(args['type'])
        e = defs.getEntry()
        call = reflectcall.reflectCallCatching
    
        plug = call(errors.ConfigError,
                    e.getModuleName(), e.getFunction(), args)
        self.plugs[socket].append(plug)
        plug.start(self)

    def _addManagerPlugs(self, _, conf, remoteIdentity):
        if not conf.manager:
            return

        for socket, plugs in conf.manager.plugs.items():
            if not socket in self.plugs:
                self.plugs[socket] = []

            for args in plugs:
                self._addManagerPlug(socket, args, remoteIdentity)

    def _addComponent(self, conf, parent, remoteIdentity):
        """
        Add a component state for the given component config entry.

        @returns: L{flumotion.common.planet.ManagerComponentState}
        """

        self.debug('adding component %s to %s'
                   % (conf.name, parent.get('name')))
        
        if remoteIdentity != RUNNING_LOCALLY:
            self.adminAction(remoteIdentity, '_addComponent',
                             (conf, parent), {})

        state = planet.ManagerComponentState()
        state.set('name', conf.name)
        state.set('type', conf.getType())
        state.set('workerRequested', conf.worker)
        state.set('mood', moods.sleeping.value)
        state.set('config', conf.getConfigDict())

        state.set('parent', parent)
        parent.append('components', state)

        avatarId = conf.getConfigDict()['avatarId']

        # add to mapper
        m = ComponentMapper()
        m.state = state
        m.id = avatarId
        self._componentMappers[state] = m
        self._componentMappers[avatarId] = m

        return state

    def _updateFlowDependencies(self, state):
        self.debug('registering dependencies of %r' % state)

        self._depgraph.addComponent(state)

        conf = state.get('config')

        # If this component has the same id as the clock-master, then it is the
        # clock master; add to the dependency graph.
        componentAvatarId = common.componentId(
            state.get('parent').get('name'), state.get('name'))

        if componentAvatarId == conf['clock-master']:
            self._depgraph.addClockMaster(state)

    def _updateStateFromConf(self, _, conf, remoteIdentity):
        self.debug('syncing up planet state with config')
        added = [] # added components while parsing
        
        state = self.state
        atmosphere = state.get('atmosphere')
        for name, c in conf.atmosphere.components.items():
            if name in [x.get('name') for x in atmosphere.get('components')]:
                self.debug('atmosphere already has component %s' % name)
            else:
                added.append(self._addComponent(c, atmosphere,
                                                remoteIdentity))

        flows = dict([(x.get('name'), x) for x in state.get('flows')])
        for f in conf.flows:
            try:
                flow = flows[f.name]
                self.debug('checking existing flow %s' % f.name)
            except KeyError:
                self.info('creating flow "%s"' % f.name)
                flow = planet.ManagerFlowState(name=f.name, parent=state)
                state.append('flows', flow)
                
            components = [x.get('name') for x in flow.get('components')]
            for name, c in f.components.items():
                if name in components:
                    self.debug('component %s already in flow %s'
                               % (c.name, f.name))
                else:
                    added.append(self._addComponent(c, flow,
                                                    remoteIdentity))

        for componentState in added:
            self._updateFlowDependencies(componentState)

        self._depgraph.mapEatersToFeeders()

        return added

    def _startComponents(self, _, conf, remoteIdentity):
        # now start all components that need starting -- collecting into
        # an temporary dict of the form {workerId => [components]}
        # if workerName is None, we can start the component on any
        # worker
        componentsToStart = {}
        for c in self._getComponentsToCreate():
            workerId = c.get('workerRequested')
            if not workerId in componentsToStart:
                componentsToStart[workerId] = []
            componentsToStart[workerId].append(c)
        self.debug('_startComponents: componentsToStart %r' % componentsToStart)
        
        for workerId, componentStates in componentsToStart.items():
            self._workerCreateComponents(workerId, componentStates)

    def _loadConfiguration(self, conf, remoteIdentity):
        # makeBouncer only makes a bouncer if there is one in the config
        d = self._makeBouncer(conf, remoteIdentity)
        d.addCallback(self._addManagerPlugs, conf, remoteIdentity)
        d.addCallback(self._updateStateFromConf, conf, remoteIdentity)
        d.addCallback(self._startComponents, conf, remoteIdentity)
        return d
 
    def loadConfigurationXML(self, file, remoteIdentity):
        """
        Load the configuration from the given XML, merging it on top of
        the currently running configuration.
        
        @param file: The file to parse, either as an open file object,
        or as the name of a file to open.
        @type  file: str or file.
        @param remoteIdentity: The identity of the remote host making
        this request, or None for debugging. This is used by the
        adminaction logging mechanism in order to say who is performing
        the action.
        @type  remoteIdentity: anything
        """
        self.debug('loading configuration')
        self.configuration = conf = config.FlumotionConfigXML(file)
        conf.parse()
        return self._loadConfiguration(conf, remoteIdentity)

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
        if self.bouncer:
            self.warning("manager already had a bouncer, setting anyway")

        self.bouncer = bouncer
        self.portal.bouncer = bouncer

    def getFactory(self):
        return self.factory
       
    def componentCreate(self, componentState):
        """
        Create the given component.  This will currently also trigger
        a start eventually when the component avatar attaches.

        The component should be sleeping.
        The worker it should be started on should be present.
        """
        m = componentState.get('mood')
        if m != moods.sleeping.value:
            raise errors.ComponentMoodError("%r not sleeping but %s" % (
                componentState, moods.get(m).name))

        p = componentState.get('moodPending')
        if p != None:
            raise errors.ComponentMoodError(
                "%r already has a pending mood %s" % moods.get(p).name)

        # find a worker this component can start on
        workerId = (componentState.get('workerName')
                    or componentState.get('workerRequested'))

        if workerId and not workerId in self.workerHeaven.avatars:
            raise errors.ComponentNoWorkerError(
                "worker %s is not logged in" % workerId)
        elif not self.workerHeaven.avatars:
            raise errors.ComponentNoWorkerError(
                "no workers are logged in")
        else:
            return self._workerCreateComponents(workerId, [componentState])

    def componentStop(self, componentState):
        """
        Stop the given component.
        If the component was sad, we clear its sad state as well,
        since the stop was explicitly requested by the admin.

        @type componentState: L{planet.ManagerComponentState}

        @rtype: L{defer.Deferred}
        """
        self.debug('componentStop(%r)' % componentState)
        # clear all messages
        for m in componentState.get('messages'):
            self.debug('Removing message %r' % m)
            componentState.remove('messages', m)

        componentState.set('moodPending', None)

        avatar = self.getComponentMapper(componentState).avatar
        if componentState.get('mood') == moods.sad.value and not avatar:
            self.debug('asked to stop a sad component without avatar')
            componentState.set('mood', planet.moods.sleeping.value)
            return defer.succeed(None)

        d = avatar.mindCallRemote('stop')
        def clearSadCallback(result):
            if componentState.get('mood') == planet.moods.sad.value:
                self.debug('clearing sad mood after stopping component')
                componentState.set('mood', planet.moods.sleeping.value)
            return result
        d.addCallback(clearSadCallback)
        return d

    def componentAddMessage(self, avatarId, message):
        """
        Set the given message on the given component's state.
        Can be called e.g. by a worker to report on a crashed component.
        """
        if not avatarId in self._componentMappers:
            self.warning('asked to set a message on non-mapped component %s' %
                avatarId)
            return

        m = self._componentMappers[avatarId]
        m.state.append('messages', message)
        if message.level == messages.ERROR:
            self.debug('Error message makes component sad')
            m.state.set('mood', moods.sad.value)
        
    # FIXME: unify naming of stuff like this
    def workerAttached(self, workerAvatar):
        # called when a worker logs in
        workerId = workerAvatar.avatarId
        self.debug('vishnu.workerAttached(): id %s' % workerId)

        self._depgraph.addWorker(workerId)
        self._depgraph.setWorkerStarted(workerId)

        # Create all components assigned to this worker. Note that the
        # order of creation is unimportant, it's only the order of
        # starting that matters (and that's different code).
        components = [c for c in self._getComponentsToCreate()
                      if c.get('workerRequested') in (workerId, None)]

        # So now, check what components worker is running
        # so we can remove them from this components list
        # also add components we have that are lost but not
        # in list given by worker
        d = workerAvatar.getComponents()
        def workerAvatarComponentListReceived(workerComponents):
            lostComponents = [c for c in self.getComponentStates()
                              if c.get('workerRequested') == workerId and \
                                 c.get('mood') == moods.lost.value]
            for comp in workerComponents:
                # comp is an avatarId string
                # components is a list of {ManagerComponentState}
                if comp in self._componentMappers:
                    compState = self._componentMappers[comp].state
                    if compState in components:
                        components.remove(compState)
                    if compState in lostComponents:
                        lostComponents.remove(compState)
            
            for compState in lostComponents:
                self.info("Component %s was lost but is running on worker %r "
                    "that logged in. Not starting again.",
                    (self._componentMappers[compState].id, workerId))

            allComponents = components + lostComponents

            if not allComponents:
                self.debug('vishnu.workerAttached(): no components for this "
                    "worker')
                return
        
            self._workerCreateComponents(workerId, allComponents)
        d.addCallback(workerAvatarComponentListReceived)
            
    def _workerCreateComponents(self, workerId, components):
        """
        Create the list of components on the given worker, sequentially, but
        in no specific order.

        @param workerId:   avatarId of the worker
        @type  workerId:   string, or None to start it on any worker
        @param components: components to start
        @type  components: list of
                           L{flumotion.common.planet.ManagerComponentState}
        """
        self.debug("_workerCreateComponents: workerId %r, components %r" % (
            workerId, components))
        if not workerId:
            if not self.workerHeaven.avatars:
                self.debug('no workers yet, cannot start jobs yet')
                return defer.succeed(None)
            workerId = self.workerHeaven.avatars.keys()[0]

        if not workerId in self.workerHeaven.avatars:
            self.debug('worker %s not logged in yet, delaying '
                       'component start' % workerId)
            return defer.succeed(None)

        workerAvatar = self.workerHeaven.avatars[workerId]

        d = defer.Deferred()

        for c in components:
            type = c.get('type')
            conf = c.get('config')
            self.debug('scheduling create of %s on %s'
                       % (conf['avatarId'], workerId))
            d.addCallback(self._workerCreateComponentDelayed,
                workerAvatar, c, type, conf)

        d.addCallback(lambda result: self.debug(
            '_workerCreateComponents(): completed setting up create chain'))

        # now trigger the chain
        self.debug('_workerCreateComponents(): triggering create chain')
        d.callback(None)
        #reactor.callLater(0, d.callback, None)
        return d

    def _workerCreateComponentDelayed(self, result, workerAvatar,
            componentState, type, conf):

        avatarId = conf['avatarId']
        nice = conf.get('nice', 0)

        # we set the moodPending to HAPPY, so this component only gets
        # asked to start once
        componentState.set('moodPending', moods.happy.value)

        d = workerAvatar.createComponent(avatarId, type, nice)
        # FIXME: here we get the avatar Id of the component we wanted
        # started, so now attach it to the planetState's component state
        d.addCallback(self._createCallback, componentState)
        d.addErrback(self._createErrback, componentState)

        # FIXME: shouldn't we return d here to make sure components
        # wait on each other to be started ?

    def _createCallback(self, result, componentState):
        self.debug('got avatarId %s for state %s' % (result, componentState))
        m = self._componentMappers[componentState]
        assert result == m.id, "received id %s is not the expected id %s" % (
            result, m.id)

    def _createErrback(self, failure, state):
        # FIXME: make ConfigError copyable so we can .check() it here
        # and print a nicer warning
        self.warning('failed to create component %s: %s'
                  % (state.get('name'), log.getFailureMessage(failure)))

        message = messages.Error(T_(
            N_("The component could not be started.")),
                debug=log.getFailureMessage(failure))

        state.set('mood', moods.sad.value)
        state.append('messages', message)

        return None

    def workerDetached(self, workerAvatar):
        # called when a worker logs out
        workerId = workerAvatar.avatarId
        self.debug('vishnu.workerDetached(): id %s' % workerId)
        self._depgraph.setWorkerStopped(workerId)

    def _configToComponentState(self, conf, avatar):
        assert not avatar.avatarId in self._componentMappers.keys()

        state = planet.ManagerComponentState()
        state.set('name', conf['name'])
        state.set('type', conf['type'])
        state.set('workerRequested', None)
        state.set('config', conf)

        # check if we have this flow yet and add if not
        isOurFlow = lambda x: x.get('name') == conf['parent']
        flow = _first(self.state.get('flows'), isOurFlow)
        if not flow:
            self.info('Creating flow "%s"' % conf['parent'])
            flow = planet.ManagerFlowState()
            flow.set('name', conf['parent'])
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

        return self.componentAttached(avatar)

    def componentAttached(self, componentAvatar):
        # called when a component logs in and gets a component avatar created
        id = componentAvatar.avatarId
        self.debug("%s component attached", id)
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
        self._depgraph.setJobStopped(componentAvatar.componentState)

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

        self._depgraph.setJobStarted(m.state)
        # If this is a reconnecting component, we might also need to set the
        # component as setup and/or started.
        # If mood is happy or hungry, then the component is running.
        mood = m.state.get('mood')
        if mood == moods.happy.value or mood == moods.hungry.value:
            self.debug("Component %s is already in mood %s.  Set depgraph "
                "appropriately", moods.get(mood).name, componentAvatar.avatarId)
            self._depgraph.setComponentSetup(m.state)
            self._depgraph.setComponentStarted(m.state)
        elif mood == moods.waking.value:
            self.debug("Component %s is waking, noting in depgraph", 
                componentAvatar.avatarId)
            self._depgraph.setComponentSetup(m.state)

        self.debug('vishnu registered component %r' % componentAvatar)
        self.componentHeaven._tryWhatCanBeStarted()

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
        
        m.state.set('pid', None)
        m.state.set('cpu', None)
        m.state.set('workerName', None)

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

    def deleteComponent(self, componentState):
        """
        Empty the planet of the given component.

        @returns: a deferred that will fire when all listeners have been
        notified of the removal of the component.
        """
        self.debug('deleting component %r from state', componentState)
        c = componentState
        flow = componentState.get('parent')
        if (c.get('moodPending') != None
            or c.get('mood') is not moods.sleeping.value):
            raise errors.BusyComponentError(c)

        self._depgraph.removeComponent(c)

        del self._componentMappers[self._componentMappers[c].id]
        del self._componentMappers[c]
        return flow.remove('components', c)
        
    def deleteFlow(self, flowName):
        """
        Empty the planet of a flow.

        @returns: a deferred that will fire when the flow is removed.
        """

        # first get all components to sleep
        flow = _find(self.state.get('flows'), flowName, lambda x: x.get('name'))
        components = flow.get('components')

        # if any component is already in a mood change/command, fail
        isBusy = lambda c: c.get('moodPending') != None
        isNotSleeping = lambda c: c.get('mood') is not moods.sleeping.value
        pred = _fint(isBusy, isNotSleeping)
        if _any(components, pred):
            raise errors.BusyComponentError(_first(components, pred))

        for c in components:
            self._depgraph.removeComponent(c)
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
            state = components[0]
            raise errors.BusyComponentError(state, 
                "moodPending is %s" % moods.get(state.get('moodPending')))

        # filter out the ones that aren't sleeping and stop them
        components = self.getComponentStates()
        isNotSleeping = lambda c: c.get('mood') is not moods.sleeping.value
        components = filter(isNotSleeping, components)

        # create a big deferred for stopping everything
        d = defer.Deferred()
        
        self.debug('need to stop %d components: %r' % (
            len(components), components))

        # FIXME: we should shut components down in the correct order (according
        # to the dependency graph); this uses an undefined ordering.
        for c in components:
            avatar = self._componentMappers[c].avatar
            # If this has logged out, but isn't sleeping (so is sad or lost),
            # we won't have an avatar. So, stop if it we can.
            if avatar:
                d.addCallback(lambda result, a: a.stop(), avatar)
            else:
                assert (c.get('mood') is moods.sad.value or 
                    c.get('mood') is moods.lost.value)

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
            # remove from depgraph
            self._depgraph.removeComponent(c)

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
       
    def _getComponentsToCreate(self):
        """
        @rtype: list of L{flumotion.common.planet.ManagerComponentState}
        """
        # return a list of components that are sleeping and not pending
        components = self.state.getComponents()

        # filter the ones that are sleeping and not pending
        isSleeping = lambda c: c.get('mood') == moods.sleeping.value
        components = filter(isSleeping, components)
        isNotPending = lambda c: c.get('moodPending') == None
        components = filter(isNotPending, components)

        return components

    def _getWorker(self, workerName):
        # returns the WorkerAvatar with the given name
        if not workerName in self.workerHeaven.avatars:
            raise errors.ComponentNoWorkerError("Worker %s not logged in?"
                                                % workerName)

        return self.workerHeaven.avatars[workerName]

    def getWorkerFeedServerPort(self, workerName):
        return self._getWorker(workerName).feedServerPort
    
    def reservePortsOnWorker(self, workerName, numPorts):
        """
        Requests a number of ports on the worker named workerName. The
        ports will be reserved for the use of the caller until
        releasePortsOnWorker is called.

        @returns: a list of ports as integers
        """
        return self._getWorker(workerName).reservePorts(numPorts)
        
    def releasePortsOnWorker(self, workerName, ports):
        """
        Tells the manager that the given ports are no longer being used,
        and may be returned to the allocation pool.
        """
        try:
            return self._getWorker(workerName).releasePorts(ports)
        except errors.ComponentNoWorkerError, e:
            self.warning('could not release ports: %r' % e.args)
        
    def getComponentMapper(self, object):
        """
        Look up an object mapper given the object.

        @rtype: L{ComponentMapper} or None
        """
        if object in self._componentMappers.keys():
            return self._componentMappers[object]

        return None
