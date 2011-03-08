# -*- Mode: Python; test-case-name: flumotion.test.test_manager_manager -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# Flumotion - a streaming media server
# Copyright (C) 2004,2005,2006,2007 Fluendo, S.L. (www.fluendo.com).
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

@var  LOCAL_IDENTITY: an identity for the manager itself; can be used
                      to compare against to verify that the manager
                      requested an action
@type LOCAL_IDENTITY: L{LocalIdentity}
"""

import os

from twisted.internet import reactor, defer
from twisted.spread import pb
from twisted.cred import portal
from zope.interface import implements

from flumotion.common import errors, interfaces, log, registry
from flumotion.common import planet, common, messages, reflectcall, server
from flumotion.common.i18n import N_, gettexter
from flumotion.common.identity import RemoteIdentity, LocalIdentity
from flumotion.common.netutils import addressGetHost
from flumotion.common.planet import moods
from flumotion.configure import configure
from flumotion.manager import admin, component, worker, base, config
from flumotion.twisted import portal as fportal
from flumotion.project import project

__all__ = ['ManagerServerFactory', 'Vishnu']
__version__ = "$Rev$"
T_ = gettexter()
LOCAL_IDENTITY = LocalIdentity('manager')


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
        """
        @param computeIdentity: see L{Vishnu.computeIdentity}
        @type  computeIdentity: callable
        """
        self._interfaceHeavens = {} # interface -> heaven
        self._computeIdentity = computeIdentity
        self._bouncer = None
        self._avatarKeycards = {} # avatarId -> keycard

    def setBouncer(self, bouncer):
        """
        @param bouncer: the bouncer to authenticate with
        @type bouncer: L{flumotion.component.bouncers.bouncer}
        """
        self._bouncer = bouncer

    def registerHeaven(self, heaven, interface):
        """
        Register a Heaven as managing components with the given interface.

        @type interface:  L{twisted.python.components.Interface}
        @param interface: a component interface to register the heaven with.
        """
        assert isinstance(heaven, base.ManagerHeaven)

        self._interfaceHeavens[interface] = heaven

    ### IRealm methods

    def requestAvatar(self, avatarId, keycard, mind, *ifaces):

        def got_avatar(avatar):
            if avatar.avatarId in heaven.avatars:
                raise errors.AlreadyConnectedError(avatar.avatarId)
            heaven.avatars[avatar.avatarId] = avatar
            self._avatarKeycards[avatar.avatarId] = keycard

            # OK so this is byzantine, but test_manager_manager actually
            # uses these kwargs to set its own info. so don't change
            # these args or their order or you will break your test
            # suite.

            def cleanup(avatarId=avatar.avatarId, avatar=avatar, mind=mind):
                self.info('lost connection to client %r', avatar)
                del heaven.avatars[avatar.avatarId]
                avatar.onShutdown()
                # avoid leaking the keycard
                keycard = self._avatarKeycards.pop(avatarId)
                if self._bouncer:
                    try:
                        self._bouncer.removeKeycard(keycard)
                    except KeyError:
                        self.warning("bouncer forgot about keycard %r",
                                     keycard)

            return (pb.IPerspective, avatar, cleanup)

        def got_error(failure):
            # If we failed for some reason, we want to drop the connection.
            # However, we want the failure to get to the client, so we don't
            # call loseConnection() immediately - we return the failure first.
            # loseConnection() will then not drop the connection until it has
            # finished sending the current data to the client.
            reactor.callLater(0, mind.broker.transport.loseConnection)
            return failure

        if pb.IPerspective not in ifaces:
            raise errors.NoPerspectiveError(avatarId)
        if len(ifaces) != 2:
            # IPerspective and the specific avatar interface.
            raise errors.NoPerspectiveError(avatarId)
        iface = [x for x in ifaces if x != pb.IPerspective][0]
        if iface not in self._interfaceHeavens:
            self.warning('unknown interface %r', iface)
            raise errors.NoPerspectiveError(avatarId)

        heaven = self._interfaceHeavens[iface]
        klass = heaven.avatarClass
        host = addressGetHost(mind.broker.transport.getPeer())
        d = self._computeIdentity(keycard, host)
        d.addCallback(lambda identity: \
                      klass.makeAvatar(heaven, avatarId, identity, mind))
        d.addCallbacks(got_avatar, got_error)
        return d


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
    I am the toplevel manager object that knows about all
    heavens and factories.

    @cvar dispatcher:      dispatcher to create avatars
    @type dispatcher:      L{Dispatcher}
    @cvar workerHeaven:    the worker heaven
    @type workerHeaven:    L{worker.WorkerHeaven}
    @cvar componentHeaven: the component heaven
    @type componentHeaven: L{component.ComponentHeaven}
    @cvar adminHeaven:     the admin heaven
    @type adminHeaven:     L{admin.AdminHeaven}
    @cvar configDir:       the configuration directory for
                           this Vishnu's manager
    @type configDir:       str
    """

    implements(server.IServable)

    logCategory = "vishnu"

    def __init__(self, name, unsafeTracebacks=0, configDir=None):
        # create a Dispatcher which will hand out avatars to clients
        # connecting to me
        self.dispatcher = Dispatcher(self.computeIdentity)

        self.workerHeaven = self._createHeaven(interfaces.IWorkerMedium,
                                               worker.WorkerHeaven)
        self.componentHeaven = self._createHeaven(interfaces.IComponentMedium,
                                                  component.ComponentHeaven)
        self.adminHeaven = self._createHeaven(interfaces.IAdminMedium,
                                              admin.AdminHeaven)

        self.running = True

        def setStopped():
            self.running = False
        reactor.addSystemEventTrigger('before', 'shutdown', setStopped)

        if configDir is not None:
            self.configDir = configDir
        else:
            self.configDir = os.path.join(configure.configdir,
                                          "managers", name)

        self.bouncer = None # used by manager to authenticate worker/component

        self.bundlerBasket = registry.getRegistry().makeBundlerBasket()

        self._componentMappers = {} # any object -> ComponentMapper

        self.state = planet.ManagerPlanetState()
        self.state.set('name', name)
        self.state.set('version', configure.version)

        self.plugs = {} # socket -> list of plugs

        # create a portal so that I can be connected to, through our dispatcher
        # implementing the IRealm and a bouncer
        self.portal = fportal.BouncerPortal(self.dispatcher, None)
        #unsafeTracebacks = 1 # for debugging tracebacks to clients
        self.factory = pb.PBServerFactory(self.portal,
            unsafeTracebacks=unsafeTracebacks)
        self.connectionInfo = {}
        self.setConnectionInfo(None, None, None)

    def shutdown(self):
        """Cancel any pending operations in preparation for shutdown.

        This method is mostly useful for unit tests; currently, it is
        not called during normal operation. Note that the caller is
        responsible for stopping listening on the port, as the the
        manager does not have a handle on the twisted port object.

        @returns: A deferred that will fire when the manager has shut
        down.
        """
        if self.bouncer:
            return self.bouncer.stop()
        else:
            return defer.succeed(None)

    def setConnectionInfo(self, host, port, use_ssl):
        info = dict(host=host, port=port, use_ssl=use_ssl)
        self.connectionInfo.update(info)

    def getConfiguration(self):
        """Returns the manager's configuration as a string suitable for
        importing via loadConfiguration().
        """
        return config.exportPlanetXml(self.state)

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
            registry.getRegistry().verify(force=True)
            self.bundlerBasket = registry.getRegistry().makeBundlerBasket()
        elif not self.bundlerBasket.isUptodate(registry.getRegistry().mtime):
            self.info("BundlerBasket is older than the Registry, rebuilding")
            self.bundlerBasket = registry.getRegistry().makeBundlerBasket()
        return self.bundlerBasket

    def addMessage(self, level, mid, format, *args, **kwargs):
        """
        Convenience message to construct a message and add it to the
        planet state. `format' should be marked as translatable in the
        source with N_, and *args will be stored as format arguments.
        Keyword arguments are passed on to the message constructor. See
        L{flumotion.common.messages.Message} for the meanings of the
        rest of the arguments.

        For example::

          self.addMessage(messages.WARNING, 'foo-warning',
                          N_('The answer is %d'), 42, debug='not really')
        """
        self.addMessageObject(messages.Message(level,
                                               T_(format, *args),
                                               mid=mid, **kwargs))

    def addMessageObject(self, message):
        """
        Add a message to the planet state.

        @type message: L{flumotion.common.messages.Message}
        """
        self.state.setitem('messages', message.id, message)

    def clearMessage(self, mid):
        """
        Clear any messages with the given message ID from the planet
        state.

        @type  mid: message ID, normally a str
        """
        if mid in self.state.get('messages'):
            self.state.delitem('messages', mid)

    def adminAction(self, identity, message, args, kw):
        """
        @param identity: L{flumotion.common.identity.Identity}
        """
        socket = 'flumotion.component.plugs.adminaction.AdminActionPlug'
        if socket in self.plugs:
            for plug in self.plugs[socket]:
                plug.action(identity, message, args, kw)

    def computeIdentity(self, keycard, remoteHost):
        """
        Compute a suitable identity for a remote host. First looks to
        see if there is a
        L{flumotion.component.plugs.identity.IdentityProviderPlug} plug
        installed on the manager, falling back to user@host.

        The identity is only used in the adminaction interface. An
        example of its use is when you have an adminaction plug that
        checks an admin's privileges before actually doing an action;
        the identity object you use here might store the privileges that
        the admin has.

        @param keycard:    the keycard that the remote host used to log in.
        @type  keycard:    L{flumotion.common.keycards.Keycard}
        @param remoteHost: the ip of the remote host
        @type  remoteHost: str

        @rtype: a deferred that will fire a
                L{flumotion.common.identity.RemoteIdentity}
        """

        socket = 'flumotion.component.plugs.identity.IdentityProviderPlug'
        if socket in self.plugs:
            for plug in self.plugs[socket]:
                identity = plug.computeIdentity(keycard, remoteHost)
                if identity:
                    return identity
        username = getattr(keycard, 'username', None)
        return defer.succeed(RemoteIdentity(username, remoteHost))

    def _addComponent(self, conf, parent, identity):
        """
        Add a component state for the given component config entry.

        @rtype: L{flumotion.common.planet.ManagerComponentState}
        """

        self.debug('adding component %s to %s'
                   % (conf.name, parent.get('name')))

        if identity != LOCAL_IDENTITY:
            self.adminAction(identity, '_addComponent', (conf, parent), {})

        state = planet.ManagerComponentState()
        state.set('name', conf.name)
        state.set('type', conf.getType())
        state.set('workerRequested', conf.worker)
        state.setMood(moods.sleeping.value)
        state.set('config', conf.getConfigDict())

        state.set('parent', parent)
        parent.append('components', state)

        avatarId = conf.getConfigDict()['avatarId']

        self.clearMessage('loadComponent-%s' % avatarId)

        configDict = conf.getConfigDict()
        projectName = configDict['project']
        versionTuple = configDict['version']

        projectVersion = None
        try:
            projectVersion = project.get(projectName, 'version')
        except errors.NoProjectError:
            m = messages.Warning(T_(N_(
                "This component is configured for Flumotion project '%s', "
                "but that project is not installed.\n"),
                    projectName))
            state.append('messages', m)

        if projectVersion:
            self.debug('project %s, version %r, project version %r' % (
                projectName, versionTuple, projectVersion))
            if not common.checkVersionsCompat(
                    versionTuple,
                    common.versionStringToTuple(projectVersion)):
                m = messages.Warning(T_(N_(
                    "This component is configured for "
                    "Flumotion '%s' version %s, "
                    "but you are running version %s.\n"
                    "Please update the configuration of the component.\n"),
                        projectName, common.versionTupleToString(versionTuple),
                        projectVersion))
                state.append('messages', m)

        # add to mapper
        m = ComponentMapper()
        m.state = state
        m.id = avatarId
        self._componentMappers[state] = m
        self._componentMappers[avatarId] = m

        return state

    def _updateStateFromConf(self, _, conf, identity):
        """
        Add a new config object into the planet state.

        @returns: a list of all components added
        @rtype:   list of L{flumotion.common.planet.ManagerComponentState}
        """

        self.debug('syncing up planet state with config')
        added = [] # added components while parsing

        def checkNotRunning(comp, parentState):
            name = comp.getName()

            comps = dict([(x.get('name'), x)
                          for x in parentState.get('components')])
            runningComps = dict([(x.get('name'), x)
                                  for x in parentState.get('components')
                                  if x.get('mood') != moods.sleeping.value])
            if name not in comps:
                # We don't have it at all; allow it
                return True
            elif name not in runningComps:
                # We have it, but it's not running. Allow it after deleting
                # the old one.
                oldComp = comps[name]
                self.deleteComponent(oldComp)
                return True

            # if we get here, the component is already running; warn if
            # the running configuration is different. Return False in
            # all cases.
            parent = comps[name].get('parent').get('name')
            newConf = c.getConfigDict()
            oldConf = comps[name].get('config')

            if newConf == oldConf:
                self.debug('%s already has component %s running with '
                           'same configuration', parent, name)
                self.clearMessage('loadComponent-%s' % oldConf['avatarId'])
                return False

            self.info('%s already has component %s, but configuration '
                      'not the same -- notifying admin', parent, name)

            diff = config.dictDiff(oldConf, newConf)
            diffMsg = config.dictDiffMessageString(diff, 'existing', 'new')

            self.addMessage(messages.WARNING,
                            'loadComponent-%s' % oldConf['avatarId'],
                            N_('Could not load component %r into %r: '
                               'a component is already running with '
                               'this name, but has a different '
                               'configuration.'), name, parent,
                            debug=diffMsg)
            return False

        state = self.state
        atmosphere = state.get('atmosphere')
        for c in conf.atmosphere.components.values():
            if checkNotRunning(c, atmosphere):
                added.append(self._addComponent(c, atmosphere, identity))

        flows = dict([(x.get('name'), x) for x in state.get('flows')])
        for f in conf.flows:
            if f.name in flows:
                flow = flows[f.name]
            else:
                self.info('creating flow %r', f.name)
                flow = planet.ManagerFlowState(name=f.name, parent=state)
                state.append('flows', flow)

            for c in f.components.values():
                if checkNotRunning(c, flow):
                    added.append(self._addComponent(c, flow, identity))

        return added

    def _startComponents(self, components, identity):
        # now start all components that need starting -- collecting into
        # an temporary dict of the form {workerId => [components]}
        componentsToStart = {}
        for c in components:
            workerId = c.get('workerRequested')
            if not workerId in componentsToStart:
                componentsToStart[workerId] = []
            componentsToStart[workerId].append(c)
        self.debug('_startComponents: componentsToStart %r' %
                   (componentsToStart, ))

        for workerId, componentStates in componentsToStart.items():
            self._workerCreateComponents(workerId, componentStates)

    def _loadComponentConfiguration(self, conf, identity):
        # makeBouncer only makes a bouncer if there is one in the config
        d = defer.succeed(None)
        d.addCallback(self._updateStateFromConf, conf, identity)
        d.addCallback(self._startComponents, identity)
        return d

    def loadComponentConfigurationXML(self, file, identity):
        """
        Load the configuration from the given XML, merging it on top of
        the currently running configuration.

        @param file:     file to parse, either as an open file object,
                         or as the name of a file to open
        @type  file:     str or file
        @param identity: The identity making this request.. This is used by the
                         adminaction logging mechanism in order to say who is
                         performing the action.
        @type  identity: L{flumotion.common.identity.Identity}
        """
        self.debug('loading configuration')
        mid = 'loadComponent-parse-error'
        if isinstance(file, str):
            mid += '-%s' % file
        try:
            self.clearMessage(mid)
            conf = config.PlanetConfigParser(file)
            conf.parse()
            return self._loadComponentConfiguration(conf, identity)
        except errors.ConfigError, e:
            self.addMessage(messages.WARNING, mid,
                            N_('Invalid component configuration.'),
                            debug=e.args[0])
            return defer.fail(e)
        except errors.UnknownComponentError, e:
            if isinstance(file, str):
                debug = 'Configuration loaded from file %r' % file
            else:
                debug = 'Configuration loaded remotely'
            self.addMessage(messages.WARNING, mid,
                            N_('Unknown component in configuration: %s.'),
                            e.args[0], debug=debug)
            return defer.fail(e)
        except Exception, e:
            self.addMessage(messages.WARNING, mid,
                            N_('Unknown error while loading configuration.'),
                            debug=log.getExceptionMessage(e))
            return defer.fail(e)

    def _loadManagerPlugs(self, conf):
        # Load plugs
        for socket, plugs in conf.plugs.items():
            if not socket in self.plugs:
                self.plugs[socket] = []

            for args in plugs:
                self.debug('loading plug type %s for socket %s'
                           % (args['type'], socket))
                defs = registry.getRegistry().getPlug(args['type'])
                e = defs.getEntry()
                call = reflectcall.reflectCallCatching

                plug = call(errors.ConfigError,
                            e.getModuleName(), e.getFunction(), args)
                self.plugs[socket].append(plug)

    def startManagerPlugs(self):
        for socket in self.plugs:
            for plug in self.plugs[socket]:
                self.debug('starting plug %r for socket %s', plug, socket)
                plug.start(self)

    def _loadManagerBouncer(self, conf):
        if not (conf.bouncer):
            self.warning('no bouncer defined, nothing can access the '
                         'manager')
            return defer.succeed(None)

        self.debug('going to start manager bouncer %s of type %s',
                   conf.bouncer.name, conf.bouncer.type)

        defs = registry.getRegistry().getComponent(conf.bouncer.type)
        entry = defs.getEntryByType('component')
        # FIXME: use entry.getModuleName() (doesn't work atm?)
        moduleName = defs.getSource()
        methodName = entry.getFunction()
        bouncer = reflectcall.createComponent(moduleName, methodName,
                                              conf.bouncer.getConfigDict())
        d = bouncer.waitForHappy()

        def setupCallback(result):
            bouncer.debug('started')
            self.setBouncer(bouncer)

        def setupErrback(failure):
            self.warning('Error starting manager bouncer')
        d.addCallbacks(setupCallback, setupErrback)
        return d

    def loadManagerConfigurationXML(self, file):
        """
        Load manager configuration from the given XML. The manager
        configuration is currently used to load the manager's bouncer
        and plugs, and is only run once at startup.

        @param file:     file to parse, either as an open file object,
                         or as the name of a file to open
        @type  file:     str or file
        """
        self.debug('loading configuration')
        conf = config.ManagerConfigParser(file)
        conf.parseBouncerAndPlugs()
        self._loadManagerPlugs(conf)
        self._loadManagerBouncer(conf)
        conf.unlink()

    __pychecker__ = 'maxargs=11' # hahaha

    def loadComponent(self, identity, componentType, componentId,
                      componentLabel, properties, workerName,
                      plugs, eaters, isClockMaster, virtualFeeds):
        """
        Load a component into the manager configuration.

        See L{flumotion.manager.admin.AdminAvatar.perspective_loadComponent}
        for a definition of the argument types.
        """
        self.debug('loading %s component %s on %s',
                   componentType, componentId, workerName)
        parentName, compName = common.parseComponentId(componentId)

        if isClockMaster:
            raise NotImplementedError("Clock master components are not "
                                      "yet supported")
        if worker is None:
            raise errors.ConfigError("Component %r needs to specify the"
                                     " worker on which it should run"
                                     % componentId)

        state = self.state
        compState = None

        compConf = config.ConfigEntryComponent(compName, parentName,
                                               componentType,
                                               componentLabel,
                                               properties,
                                               plugs, workerName,
                                               eaters, isClockMaster,
                                               None, None, virtualFeeds)

        if compConf.defs.getNeedsSynchronization():
            raise NotImplementedError("Components that need "
                                      "synchronization are not yet "
                                      "supported")

        if parentName == 'atmosphere':
            parentState = state.get('atmosphere')
        else:
            flows = dict([(x.get('name'), x) for x in state.get('flows')])
            if parentName in flows:
                parentState = flows[parentName]
            else:
                self.info('creating flow %r', parentName)
                parentState = planet.ManagerFlowState(name=parentName,
                                                      parent=state)
                state.append('flows', parentState)

        components = [x.get('name') for x in parentState.get('components')]
        if compName in components:
            self.debug('%r already has component %r', parentName, compName)
            raise errors.ComponentAlreadyExistsError(compName)

        compState = self._addComponent(compConf, parentState, identity)

        self._startComponents([compState], identity)

        return compState

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
        self.dispatcher.setBouncer(bouncer)

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
                "%r already has a pending mood %s" % (
                    componentState, moods.get(p).name))

        # find a worker this component can start on
        workerId = (componentState.get('workerName')
                    or componentState.get('workerRequested'))

        if not workerId in self.workerHeaven.avatars:
            raise errors.ComponentNoWorkerError(
                "worker %s is not logged in" % workerId)
        else:
            return self._workerCreateComponents(workerId, [componentState])

    def _componentStopNoAvatar(self, componentState, avatarId):
        # NB: reset moodPending if asked to stop without an avatar
        # because we changed above to allow stopping even if moodPending
        # is happy

        def stopSad():
            self.debug('asked to stop a sad component without avatar')
            for mid in componentState.get('messages')[:]:
                self.debug("Deleting message %r", mid)
                componentState.remove('messages', mid)

            componentState.setMood(moods.sleeping.value)
            componentState.set('moodPending', None)
            return defer.succeed(None)

        def stopLost():

            def gotComponents(comps):
                return avatarId in comps

            def gotJobRunning(running):
                if running:
                    self.warning('asked to stop lost component %r, but '
                                 'it is still running', avatarId)
                    # FIXME: put a message on the state to suggest a
                    # kill?
                    msg = "Cannot stop lost component which is still running."
                    raise errors.ComponentMoodError(msg)
                else:
                    self.debug('component %r seems to be really lost, '
                               'setting to sleeping')
                    componentState.setMood(moods.sleeping.value)
                    componentState.set('moodPending', None)
                    return None

            self.debug('asked to stop a lost component without avatar')
            workerName = componentState.get('workerRequested')
            if workerName and self.workerHeaven.hasAvatar(workerName):
                self.debug('checking if component has job process running')
                d = self.workerHeaven.getAvatar(workerName).getComponents()
                d.addCallback(gotComponents)
                d.addCallback(gotJobRunning)
                return d
            else:
                self.debug('component lacks a worker, setting to sleeping')
                d = defer.maybeDeferred(gotJobRunning, False)
                return d

        def stopUnknown():
            msg = ('asked to stop a component without avatar in mood %s'
                   % moods.get(mood))
            self.warning(msg)
            return defer.fail(errors.ComponentMoodError(msg))

        mood = componentState.get('mood')
        stoppers = {moods.sad.value: stopSad,
                    moods.lost.value: stopLost}
        return stoppers.get(mood, stopUnknown)()

    def _componentStopWithAvatar(self, componentState, componentAvatar):
        # FIXME: This deferred is just the remote call; there's no actual
        # deferred for completion of shutdown.
        d = componentAvatar.stop()

        return d

    def componentStop(self, componentState):
        """
        Stop the given component.
        If the component was sad, we clear its sad state as well,
        since the stop was explicitly requested by the admin.

        @type componentState: L{planet.ManagerComponentState}

        @rtype: L{twisted.internet.defer.Deferred}
        """
        self.debug('componentStop(%r)', componentState)
        # We permit stopping a component even if it has a pending mood of
        # happy, so that if it never gets to happy, we can still stop it.
        if (componentState.get('moodPending') != None and
            componentState.get('moodPending') != moods.happy.value):
            self.debug("Pending mood is %r", componentState.get('moodPending'))

            raise errors.BusyComponentError(componentState)

        m = self.getComponentMapper(componentState)
        if not m:
            # We have a stale componentState for an already-deleted
            # component
            self.warning("Component mapper for component state %r doesn't "
                "exist", componentState)
            raise errors.UnknownComponentError(componentState)
        elif not m.avatar:
            return self._componentStopNoAvatar(componentState, m.id)
        else:
            return self._componentStopWithAvatar(componentState, m.avatar)

    def componentAddMessage(self, avatarId, message):
        """
        Set the given message on the given component's state.
        Can be called e.g. by a worker to report on a crashed component.
        Sets the mood to sad if it is an error message.
        """
        if not avatarId in self._componentMappers:
            self.warning('asked to set a message on non-mapped component %s' %
                avatarId)
            return

        m = self._componentMappers[avatarId]
        m.state.append('messages', message)
        if message.level == messages.ERROR:
            self.debug('Error message makes component sad')
            m.state.setMood(moods.sad.value)

    # FIXME: unify naming of stuff like this

    def workerAttached(self, workerAvatar):
        # called when a worker logs in
        workerId = workerAvatar.avatarId
        self.debug('vishnu.workerAttached(): id %s' % workerId)

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
            # list() is called to work around a pychecker bug. FIXME.
            lostComponents = list([c for c in self.getComponentStates()
                              if c.get('workerRequested') == workerId and \
                                 c.get('mood') == moods.lost.value])
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
                self.info(
                    "Restarting previously lost component %s on worker %s",
                    self._componentMappers[compState].id, workerId)
                # We set mood to sleeping first. This allows things to
                # distinguish between a newly-started component and a lost
                # component logging back in.
                compState.set('moodPending', None)
                compState.setMood(moods.sleeping.value)

            allComponents = components + lostComponents

            if not allComponents:
                self.debug(
                    "vishnu.workerAttached(): no components for this worker")
                return

            self._workerCreateComponents(workerId, allComponents)
        d.addCallback(workerAvatarComponentListReceived)

        reactor.callLater(0, self.componentHeaven.feedServerAvailable,
                          workerId)

    def _workerCreateComponents(self, workerId, components):
        """
        Create the list of components on the given worker, sequentially, but
        in no specific order.

        @param workerId:   avatarId of the worker
        @type  workerId:   string
        @param components: components to start
        @type  components: list of
                           L{flumotion.common.planet.ManagerComponentState}
        """
        self.debug("_workerCreateComponents: workerId %r, components %r" % (
            workerId, components))

        if not workerId in self.workerHeaven.avatars:
            self.debug('worker %s not logged in yet, delaying '
                       'component start' % workerId)
            return defer.succeed(None)

        workerAvatar = self.workerHeaven.avatars[workerId]

        d = defer.Deferred()

        for c in components:
            componentType = c.get('type')
            conf = c.get('config')
            self.debug('scheduling create of %s on %s'
                       % (conf['avatarId'], workerId))
            d.addCallback(self._workerCreateComponentDelayed,
                workerAvatar, c, componentType, conf)

        d.addCallback(lambda result: self.debug(
            '_workerCreateComponents(): completed setting up create chain'))

        # now trigger the chain
        self.debug('_workerCreateComponents(): triggering create chain')
        d.callback(None)
        #reactor.callLater(0, d.callback, None)
        return d

    def _workerCreateComponentDelayed(self, result, workerAvatar,
            componentState, componentType, conf):

        avatarId = conf['avatarId']
        nice = conf.get('nice', 0)

        # we set the moodPending to HAPPY, so this component only gets
        # asked to start once
        componentState.set('moodPending', moods.happy.value)

        d = workerAvatar.createComponent(avatarId, componentType, nice,
                                         conf)
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
        self.warning('failed to create component %s: %s',
                     state.get('name'), log.getFailureMessage(failure))

        if failure.check(errors.ComponentAlreadyRunningError):
            if self._componentMappers[state].jobState:
                self.info('component appears to have logged in in the '
                          'meantime')
            else:
                self.info('component appears to be running already; '
                          'treating it as lost until it logs in')
                state.setMood(moods.lost.value)
        else:
            message = messages.Error(T_(
                N_("The component could not be started.")),
                debug=log.getFailureMessage(failure))

            state.setMood(moods.sad.value)
            state.append('messages', message)

        return None

    def workerDetached(self, workerAvatar):
        # called when a worker logs out
        workerId = workerAvatar.avatarId
        self.debug('vishnu.workerDetached(): id %s' % workerId)
        # Get all sad components for the detached worker and set the mood to
        # sleeping
        sadComponents = list([c for c in self.getComponentStates()
                         if c.get('workerRequested') == workerId and \
                                 c.get('mood') == moods.sad.value])
        map(lambda c: c.setMood(moods.sleeping.value), sadComponents)

    def addComponentToFlow(self, componentState, flowName):
        # check if we have this flow yet and add if not
        if flowName == 'atmosphere':
            # treat the atmosphere like a flow, although it's not
            flow = self.state.get('atmosphere')
        else:
            flow = self._getFlowByName(flowName)
        if not flow:
            self.info('Creating flow "%s"' % flowName)
            flow = planet.ManagerFlowState()
            flow.set('name', flowName)
            flow.set('parent', self.state)
            self.state.append('flows', flow)

        componentState.set('parent', flow)
        flow.append('components', componentState)

    def registerComponent(self, componentAvatar):
        # fetch or create a new mapper
        m = (self.getComponentMapper(componentAvatar.avatarId)
             or ComponentMapper())

        m.state = componentAvatar.componentState
        m.jobState = componentAvatar.jobState
        m.id = componentAvatar.avatarId
        m.avatar = componentAvatar

        self._componentMappers[m.state] = m
        self._componentMappers[m.jobState] = m
        self._componentMappers[m.id] = m
        self._componentMappers[m.avatar] = m

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
        m.state.set('workerName', None)
        m.state.set('moodPending', None)

        # unmap avatar
        del self._componentMappers[m.avatar]
        m.avatar = None

    def getComponentStates(self):
        cList = self.state.getComponents()
        self.debug('getComponentStates(): %d components' % len(cList))
        for c in cList:
            self.log(repr(c))
            mood = c.get('mood')
            if mood == None:
                self.warning('%s has mood None' % c.get('name'))

        return cList

    def deleteComponent(self, componentState):
        """
        Empty the planet of the given component.

        @returns: a deferred that will fire when all listeners have been
        notified of the removal of the component.
        """
        self.debug('deleting component %r from state', componentState)
        c = componentState
        if c not in self._componentMappers:
            raise errors.UnknownComponentError(c)

        flow = componentState.get('parent')
        if (c.get('moodPending') != None
            or c.get('mood') is not moods.sleeping.value):
            raise errors.BusyComponentError(c)

        del self._componentMappers[self._componentMappers[c].id]
        del self._componentMappers[c]
        return flow.remove('components', c)

    def _getFlowByName(self, flowName):
        for flow in self.state.get('flows'):
            if flow.get('name') == flowName:
                return flow

    def deleteFlow(self, flowName):
        """
        Empty the planet of a flow.

        @returns: a deferred that will fire when the flow is removed.
        """

        flow = self._getFlowByName(flowName)
        if flow is None:
            raise ValueError("No flow called %s found" % (flowName, ))

        components = flow.get('components')
        for c in components:
            # if any component is already in a mood change/command, fail
            if (c.get('moodPending') != None or
                c.get('mood') is not moods.sleeping.value):
                raise errors.BusyComponentError(c)
        for c in components:
            del self._componentMappers[self._componentMappers[c].id]
            del self._componentMappers[c]
        d = flow.empty()
        d.addCallback(lambda _: self.state.remove('flows', flow))
        return d

    def emptyPlanet(self):
        """
        Empty the planet of all components, and flows. Also clears all
        messages.

        @returns: a deferred that will fire when the planet is empty.
        """
        for mid in self.state.get('messages').keys():
            self.clearMessage(mid)

        # first get all components to sleep
        components = self.getComponentStates()

        # if any component is already in a mood change/command, fail
        components = [c for c in components
                            if c.get('moodPending') != None]
        if components:
            state = components[0]
            raise errors.BusyComponentError(
                state,
                "moodPending is %s" % moods.get(state.get('moodPending')))

        # filter out the ones that aren't sleeping and stop them
        components = [c for c in self.getComponentStates()
                            if c.get('mood') is not moods.sleeping.value]

        # create a big deferred for stopping everything
        d = defer.Deferred()

        self.debug('need to stop %d components: %r' % (
            len(components), components))

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
            if c.get('mood') is not moods.sleeping.value:
                self.warning('Component %s is not sleeping', c.get('name'))
            # clear mapper; remove componentstate and id
            m = self._componentMappers[c]
            del self._componentMappers[m.id]
            del self._componentMappers[c]

        # if anything's left, we have a mistake somewhere
        l = self._componentMappers.keys()
        if len(l) > 0:
            self.warning('mappers still has keys %r' % (repr(l)))

        dList = []

        dList.append(self.state.get('atmosphere').empty())

        for f in self.state.get('flows'):
            self.debug('appending deferred for emptying flow %r' % f)
            dList.append(f.empty())
            self.debug('appending deferred for removing flow %r' % f)
            dList.append(self.state.remove('flows', f))
            self.debug('appended deferreds')

        dl = defer.DeferredList(dList)
        return dl

    def _getComponentsToCreate(self):
        """
        @rtype: list of L{flumotion.common.planet.ManagerComponentState}
        """
        # return a list of components that are sleeping
        components = self.state.getComponents()

        # filter the ones that are sleeping
        # NOTE: now sleeping indicates that there is no existing job
        # as when jobs are created, mood becomes waking, so no need to
        # filter on moodPending
        isSleeping = lambda c: c.get('mood') == moods.sleeping.value
        components = filter(isSleeping, components)
        return components

    def _getWorker(self, workerName):
        # returns the WorkerAvatar with the given name
        if not workerName in self.workerHeaven.avatars:
            raise errors.ComponentNoWorkerError("Worker %s not logged in?"
                                                % workerName)

        return self.workerHeaven.avatars[workerName]

    def getWorkerFeedServerPort(self, workerName):
        if workerName in self.workerHeaven.avatars:
            return self._getWorker(workerName).feedServerPort
        return None

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

    def getManagerComponentState(self, object):
        """
        Look up an object mapper given the object.

        @rtype: L{ComponentMapper} or None
        """
        if object in self._componentMappers.keys():
            return self._componentMappers[object].state

        return None

    def invokeOnComponents(self, componentType, methodName, *args, **kwargs):
        """
        Invokes method on all components of a certain type
        """

        def invokeOnOneComponent(component, methodName, *args, **kwargs):
            m = self.getComponentMapper(component)
            if not m:
                self.warning('Component %s not mapped. Maybe deleted.',
                    component.get('name'))
                raise errors.UnknownComponentError(component)

            avatar = m.avatar
            if not avatar:
                self.warning('No avatar for %s, cannot call remote',
                    component.get('name'))
                raise errors.SleepingComponentError(component)

            try:
                return avatar.mindCallRemote(methodName, *args, **kwargs)
            except Exception, e:
                log_message = log.getExceptionMessage(e)
                msg = "exception on remote call %s: %s" % (methodName,
                    log_message)
                self.warning(msg)
                raise errors.RemoteMethodError(methodName,
                    log_message)

        # only do this on happy or hungry components of type componentType
        dl_array = []
        for c in self.getComponentStates():
            if c.get('type') == componentType and \
               (c.get('mood') is moods.happy.value or
                c.get('mood') is moods.hungry.value):
                self.info("component %r to have %s run", c, methodName)
                d = invokeOnOneComponent(c, methodName, *args, **kwargs)
                dl_array.append(d)
        dl = defer.DeferredList(dl_array)
        return dl
