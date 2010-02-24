# -*- Mode: Python; test-case-name: flumotion.test.test_component -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# Flumotion - a streaming media server
# Copyright (C) 2004,2005,2006,2007,2008 Fluendo, S.L. (www.fluendo.com).
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
worker-side objects for components
"""

import os
import time
import socket

from twisted.internet import reactor, error, defer
from twisted.spread import pb
from twisted.python import reflect
from zope.interface import implements

from flumotion.configure import configure
from flumotion.common import interfaces, errors, log, planet, medium
from flumotion.common import componentui, common, messages
from flumotion.common import interfaces, reflectcall, debug
from flumotion.common.i18n import N_, gettexter
from flumotion.common.planet import moods
from flumotion.common.poller import Poller
from flumotion.twisted import credentials
from flumotion.twisted import pb as fpb
from flumotion.twisted.flavors import IStateCacheableListener


__version__ = "$Rev$"
T_ = gettexter()


class ComponentClientFactory(fpb.ReconnectingFPBClientFactory):
    """
    I am a client factory for a component logging in to the manager.
    """
    logCategory = 'component'
    perspectiveInterface = interfaces.IComponentMedium

    def __init__(self, component):
        """
        @param component: L{flumotion.component.component.BaseComponent}
        """
        # doing this as a class method triggers a doc error
        fpb.ReconnectingFPBClientFactory.__init__(self)

        self.component = component
        # make a medium to interface with the manager
        self.medium = component.componentMediumClass(component)
        component.setMedium(self.medium)

        self.maxDelay = 10
        # get the interfaces implemented by the component medium class
        #FIXME: interface
        #self.interfaces = self.medium.__class__.__implements__

        self.logName = component.name

    def clientConnectionMade(self, broker):
        self.medium.broker = broker
        fpb.ReconnectingFPBClientFactory.clientConnectionMade(self, broker)

    # vmethod implementation

    def gotDeferredLogin(self, d):

        def remoteDisconnected(remoteReference):
            if reactor.killed:
                self.log('Connection to manager lost due to shutdown')
            else:
                self.warning('Lost connection to manager, '
                             'will attempt to reconnect')

        def loginCallback(reference):
            self.info("Logged in to manager")
            self.debug("remote reference %r" % reference)

            self.medium.setRemoteReference(reference)
            reference.notifyOnDisconnect(remoteDisconnected)

        def loginFailedDisconnect(failure):
            # We _always_ disconnect. Then, we may log a more specific failure
            # message at a higher warning level.
            self.debug('Login failed, reason: %s, disconnecting', failure)
            self.disconnect()
            return failure

        def accessDeniedErrback(failure):
            failure.trap(errors.NotAuthenticatedError)
            self.warning('Access denied.')

        def connectionRefusedErrback(failure):
            failure.trap(error.ConnectionRefusedError)
            self.warning('Connection to manager refused.')

        def alreadyLoggedInErrback(failure):
            failure.trap(errors.AlreadyConnectedError)
            self.warning('Component with id %s is already logged in.',
                self.medium.authenticator.avatarId)

        def loginFailedErrback(failure):
            self.warning('Login failed, reason: %s' % failure)

        d.addCallback(loginCallback)
        d.addErrback(loginFailedDisconnect)
        d.addErrback(accessDeniedErrback)
        d.addErrback(connectionRefusedErrback)
        d.addErrback(alreadyLoggedInErrback)
        d.addErrback(loginFailedErrback)

    # we want to save the authenticator

    def startLogin(self, authenticator):
        self.medium.setAuthenticator(authenticator)
        return fpb.ReconnectingFPBClientFactory.startLogin(self, authenticator)


def _maybeDeferredChain(procs, *args, **kwargs):
    """
    Creates a deferred chain created by chaining calls to the given
    procedures, each of them made with the given args and kwargs.
    Only the result of the last procedure is returned; results for the
    other procedures are discarded.

    Failures triggered during any of the procedure short-circuit execution
    of the other procedures and should be handled by the errbacks attached
    to the deferred returned here.

    @rtype: L{twisted.internet.defer.Deferred}
    """

    def call_proc(_, p):
        log.debug('', 'calling %r', p)
        return p(*args, **kwargs)
    p, procs = procs[0], procs[1:]
    d = defer.maybeDeferred(call_proc, None, p)
    for p in procs:
        d.addCallback(call_proc, p)
    return d

# needs to be before BaseComponent because BaseComponent references it


class BaseComponentMedium(medium.PingingMedium):
    """
    I am a medium interfacing with a manager-side avatar.
    I implement a Referenceable for the manager's avatar to call on me.
    I have a remote reference to the manager's avatar to call upon.
    I am created by the L{ComponentClientFactory}.

    @cvar authenticator: the authenticator used to log in to manager
    @type authenticator: L{flumotion.twisted.pb.Authenticator}
    """

    implements(interfaces.IComponentMedium)
    logCategory = 'basecompmed'

    def __init__(self, component):
        """
        @param component: L{flumotion.component.component.BaseComponent}
        """
        self.comp = component
        self.authenticator = None
        self.broker = None

    def setRemoteReference(self, reference):
        self.broker = None # We no longer need that reference
        medium.PingingMedium.setRemoteReference(self, reference)

    ### our methods

    def setup(self, config):
        pass

    def getManagerIP(self):
        """
        Return the manager IP as seen by us.
        """
        assert self.remote or self.broker
        broker = self.broker or self.remote.broker
        peer = broker.transport.getPeer()
        try:
            host = peer.host
        except AttributeError:
            host = peer[1]

        res = socket.gethostbyname(host)
        self.debug("getManagerIP(): we think the manager's IP is %r" % res)
        return res

    def getIP(self):
        """
        Return the IP of this component based on connection to the manager.

        Note: this is insufficient in general, and should be replaced by
        network mapping stuff later.
        """
        assert self.remote
        host = self.remote.broker.transport.getHost()
        self.debug("getIP(): using %r as our IP", host.host)
        return host.host

    def setAuthenticator(self, authenticator):
        """
        Set the authenticator the client factory has used to log in to the
        manager.  Can be reused by the component's medium to make
        feed connections which also get authenticated by the manager's
        bouncer.

        @type  authenticator: L{flumotion.twisted.pb.Authenticator}
        """
        self.authenticator = authenticator

    ### pb.Referenceable remote methods
    ### called from manager by our avatar

    def remote_getState(self):
        """
        Return the state of the component, which will be serialized to a
        L{flumotion.common.planet.ManagerJobState} object.

        @rtype:   L{flumotion.common.planet.WorkerJobState}
        @returns: state of component
        """
        # we can only get the IP after we have a remote reference, so add it
        # here
        self.comp.state.set('manager-ip', self.getManagerIP())
        return self.comp.state

    def remote_getConfig(self):
        """
        Return the configuration of the component.

        @rtype:   dict
        @returns: component's current configuration
        """
        return self.comp.config

    def remote_stop(self):
        self.info('Stopping component')
        return self.comp.stop()

    def remote_reloadComponent(self):
        """Reload modules in the component."""
        from flumotion.common.reload import reloadFlumotion
        reloadFlumotion()

    def remote_getUIState(self):
        """Get a WorkerComponentUIState containing details needed to
        present an admin-side UI state
        """
        return self.comp.uiState

    def remote_getMasterClockInfo(self):
        """
        Base implementation of getMasterClockInfo, can be overridden by
        subclasses. By default, just returns None.
        """
        return None

    def remote_getVersions(self):
        return debug.getVersions()

    def remote_setFluDebug(self, debug):
        """
        Sets the Flumotion debugging levels based on the passed debug string.

        @since: 0.6.0
        """
        self.debug('Setting Flumotion debug level to %s' % debug)
        log.setDebug(debug)


class BaseComponent(common.InitMixin, log.Loggable):
    """
    I am the base class for all Flumotion components.

    @ivar name:    the name of the component
    @type name:    string
    @ivar medium:  the component's medium
    @type medium:  L{BaseComponentMedium}
    @ivar uiState: state of the component to be shown in a UI.
                   Contains at least the following keys.
                    - cpu-percent:  percentage of CPU use in last interval
                    - start-time:   time when component was started, in epoch
                                    seconds
                    - current-time: current time in epoch seconds, as seen on
                                    component's machine, which might be out of
                                    sync
                    - virtual-size: virtual memory size in bytes
                   Subclasses can add additional keys for their respective UI.
    @type uiState: L{componentui.WorkerComponentUIState}

    @cvar componentMediumClass: the medium class to use for this component
    @type componentMediumClass: child class of L{BaseComponentMedium}
    """

    logCategory = 'basecomp'
    componentMediumClass = BaseComponentMedium

    implements(IStateCacheableListener)

    def __init__(self, config, haveError=None):
        """
        Subclasses should not override __init__ at all.

        Instead, they should implement init(), which will be called
        by this implementation automatically.

        L{flumotion.common.common.InitMixin} for more details.
        """
        self.debug("initializing %r with config %r", type(self), config)
        self.config = config
        self._haveError = haveError

        # this will call self.init() for all implementors of init()
        common.InitMixin.__init__(self)

        self.setup()

    # BaseComponent interface for subclasses related to component protocol

    def init(self):
        """
        A subclass should do as little as possible in its init method.
        In particular, it should not try to access resources.

        Failures during init are marshalled back to the manager through
        the worker's remote_create method, since there is no component state
        proxied to the manager yet at the time of init.
        """
        self.state = planet.WorkerJobState()

        self.name = self.config['name']

        self.state.set('pid', os.getpid())
        self.setMood(moods.waking)

        self.medium = None # the medium connecting us to the manager's avatar

        self.uiState = componentui.WorkerComponentUIState()
        self.uiState.addKey('cpu-percent')
        self.uiState.addKey('start-time')
        self.uiState.addKey('current-time')
        self.uiState.addKey('virtual-size')
        self.uiState.addKey('total-memory')

        self.uiState.addHook(self)

        self.plugs = {}

        self._happyWaits = []

        # Start the cpu-usage updating.
        self._lastTime = time.time()
        self._lastClock = time.clock()
        self._cpuPoller = Poller(self._pollCPU, 5, start=False)
        self._memoryPoller = Poller(self._pollMemory, 60, start=False)
        self._cpuPollerDC = None
        self._memoryPollerDC = None
        self._shutdownHook = None

    ### IStateCacheable Interface

    def observerAppend(self, observer, num):
        """
        Triggered when a uiState observer was added.

        Default implementation is to start the memory and cpu pollers.

        Note:
        Subclasses can override me but should chain me up to start these
        pollers
        """
        self.debug("observer has started watching us, starting pollers")
        if not self._cpuPoller.running and not self._cpuPollerDC:
            self._cpuPollerDC = reactor.callLater(0,
                                                  self._cpuPoller.start,
                                                  immediately=True)
        if not self._memoryPoller.running and not self._memoryPollerDC:
            self._memoryPollerDC = reactor.callLater(0,
                                                     self._memoryPoller.start,
                                                     immediately=True)

    def observerRemove(self, observer, num):
        """
        Triggered when a uiState observer has left.

        Default implementation is to stop the memory and cpu pollers
        when the total number of observers denoted by the 'num'
        argument becomes zero.

        Note:
        Subclasses can override me but should chain me up to stop these
        pollers
        """
        if num == 0:
            self.debug("no more observers left, shutting down pollers")
            # Cancel any pending callLaters
            if self._cpuPollerDC:
                self._cpuPollerDC.cancel()
                self._cpuPollerDC = None
            if self._memoryPollerDC:
                self._memoryPollerDC.cancel()
                self._memoryPollerDC = None

            if self._cpuPoller:
                self._cpuPoller.stop()
            if self._memoryPoller:
                self._memoryPoller.stop()

    def do_check(self):
        """
        Subclasses can implement me to run any checks before the component
        performs setup.

        Messages can be added to the component state's 'messages' list key.
        Any error messages added will trigger the component going to sad,
        with L{flumotion.common.errors.ComponentSetupError} being raised
        before getting to setup stage; do_setup() will not be called.

        In the event of a fatal problem that can't be expressed through an
        error message, this method should raise an exception or return a
        failure.

        It is not necessary to chain up in this function. The return
        value may be a deferred.
        """
        return defer.maybeDeferred(self.check_properties,
                                   self.config['properties'],
                                   self.addMessage)

    def check_properties(self, properties, addMessage):
        """
        BaseComponent convenience vmethod for running checks.

        A component implementation can override this method to run any
        checks that it needs to. Typically, a check_properties
        implementation will call the provided addMessage() callback to
        note warnings or errors. For errors, addMessage() will set
        component's mood to sad, which will abort the init process
        before getting to do_setup().

        @param properties: The component's properties
        @type properties: dict of string => object
        @param addMessage: Thunk to add a message to the component
                           state. Will raise an exception if the
                           message is of level ERROR.
        @type addMessage: L{flumotion.common.messages.Message} -> None
        """
        pass

    def do_setup(self):
        """
        Subclasses can implement me to set up the component before it is
        started.  It should set up the component, possibly opening files
        and resources.
        Non-programming errors should not be raised, but returned as a
        failing deferred.

        The return value may be a deferred.
        """
        for socket, plugs in self.config['plugs'].items():
            self.plugs[socket] = []
            for plug in plugs:
                entry = plug['entries']['default']
                instance = reflectcall.reflectCall(entry['module-name'],
                                                   entry['function-name'],
                                                   plug)
                self.plugs[socket].append(instance)
                self.debug('Starting plug %r on socket %s',
                           instance, socket)
                instance.start(self)

        # Call check methods, starting from the base class and working down to
        # subclasses.
        checks = common.get_all_methods(self, 'do_check', False)

        def checkErrorCallback(result):
            # if the mood is now sad, it means an error was encountered
            # during check, and we should return a failure here.
            # since the checks are responsible for adding a message,
            # this is a handled error.
            current = self.state.get('mood')
            if current == moods.sad.value:
                self.warning('Running checks made the component sad.')
                raise errors.ComponentSetupHandledError()

        checks.append(checkErrorCallback)
        return _maybeDeferredChain(checks, self)

    def do_stop(self):
        """
        BaseComponent vmethod for stopping.
        The component should do any cleanup it needs, but must not set the
        component's mood to sleeping.

        @Returns: L{twisted.internet.defer.Deferred}
        """
        for socket, plugs in self.plugs.items():
            for plug in plugs:
                self.debug('Stopping plug %r on socket %s', plug, socket)
                plug.stop(self)

        for message in self.state.get('messages'):
            # FIXME: not necessary
            self.state.remove('messages', message)

        # Cancel any pending callLaters
        if self._cpuPollerDC:
            self._cpuPollerDC.cancel()
            self._cpuPollerDC = None
        if self._memoryPollerDC:
            self._memoryPollerDC.cancel()
            self._memoryPollerDC = None

        if self._cpuPoller:
            self._cpuPoller.stop()
            self._cpuPoller = None
        if self._memoryPoller:
            self._memoryPoller.stop()
            self._memoryPoller = None

        if self._shutdownHook:
            self.debug('_stoppedCallback: firing shutdown hook')
            self._shutdownHook()

    ### BaseComponent implementation related to compoment protocol

    def setup(self):
        """
        Sets up the component.  Called during __init__, so be sure not
        to raise exceptions, instead adding messages to the component
        state.
        """

        def run_setups():
            setups = common.get_all_methods(self, 'do_setup', False)
            return _maybeDeferredChain(setups, self)

        def setup_complete(_):
            self.debug('setup completed')
            self.setup_completed()

        def got_error(failure):
            txt = log.getFailureMessage(failure)
            self.debug('got_error: %s', txt)
            if not failure.check(errors.ComponentSetupHandledError):
                self.warning('Setup failed: %s', txt)
                m = messages.Error(T_(N_("Could not setup component.")),
                                   debug=txt,
                                   mid="component-setup-%s" % self.name)
                # will call setMood(moods.sad)
                self.addMessage(m)

            # swallow
            return None

        self.setMood(moods.waking)
        self.uiState.set('start-time', time.time())

        self.uiState.set('total-memory', self._getTotalMemory())
        d = run_setups()
        d.addCallbacks(setup_complete, got_error)
        # all status info via messages and the mood

    def setup_completed(self):
        self.debug('turning happy')
        self.setMood(moods.happy)

    def setShutdownHook(self, shutdownHook):
        """
        Set the shutdown hook for this component (replacing any previous hook).
        When a component is stopped, then this hook will be fired.
        """
        self._shutdownHook = shutdownHook

    def stop(self):
        """
        Tell the component to stop.
        The connection to the manager will be closed.
        The job process will also finish.
        """
        self.debug('BaseComponent.stop')

        # Set ourselves to waking while we're shutting down.
        self.setMood(moods.waking)

        # Run stop methods, starting from the subclass, up to this base class.
        stops = common.get_all_methods(self, 'do_stop', True)
        return _maybeDeferredChain(stops, self)

    ### BaseComponent public methods

    def getName(self):
        return self.name

    def setWorkerName(self, workerName):
        self.state.set('workerName', workerName)

    def getWorkerName(self):
        return self.state.get('workerName')

    def setMedium(self, medium):
        assert isinstance(medium, BaseComponentMedium)
        self.medium = medium
        self.medium.logName = self.getName()

    def setMood(self, mood):
        """
        Set the given mood on the component if it's different from the current
        one.
        """
        current = self.state.get('mood')

        if current == mood.value:
            self.log('already in mood %r' % mood)
            return
        elif current == moods.sad.value:
            self.info('tried to set mood to %r, but already sad :-(' % mood)
            return

        self.doLog(log.DEBUG, -2, 'MOOD changed to %r by caller', mood)
        self.state.set('mood', mood.value)

        if mood == moods.happy:
            while self._happyWaits:
                self._happyWaits.pop(0).callback(None)
        elif mood == moods.sad:
            while self._happyWaits:
                self._happyWaits.pop(0).errback(errors.ComponentStartError())

    def getMood(self):
        """
        Gets the mood on the component.

        @rtype: int
        """
        return self.state.get('mood')

    def waitForHappy(self):
        mood = self.getMood()
        if mood == moods.happy.value:
            return defer.succeed(None)
        elif mood == moods.sad.value:
            return defer.fail(errors.ComponentStartError())
        else:
            d = defer.Deferred()
            self._happyWaits.append(d)
            return d

    def addMessage(self, message):
        """
        Add a message to the component.
        If any of the messages is an error, the component will turn sad.

        @type  message: L{flumotion.common.messages.Message}
        """
        self.state.append('messages', message)
        if message.level == messages.ERROR:
            self.debug('error message, turning sad')
            self.setMood(moods.sad)
            if self._haveError:
                self._haveError(message)

    def fixRenamedProperties(self, properties, list):
        """
        Fix properties that have been renamed from a previous version,
        and add a warning for them.

        @param properties: properties; will be modified as a result.
        @type  properties: dict
        @param list:       list of (old, new) tuples of property names.
        @type  list:       list of tuple of (str, str)
        """
        found = []
        for old, new in list:
            if old in properties:
                found.append((old, new))

        if found:
            m = messages.Warning(T_(N_(
                "Your configuration uses deprecated properties.  "
                "Please update your configuration and correct them.\n")),
                mid="deprecated")
            for old, new in found:
                m.add(T_(N_(
                "Please rename '%s' to '%s'.\n"),
                        old, new))
                self.debug("Setting new property '%s' to %r", new,
                    properties[old])
                properties[new] = properties[old]
                del properties[old]
            self.addMessage(m)

    def adminCallRemote(self, methodName, *args, **kwargs):
        """
        Call a remote method on all admin client views on this component.

        This gets serialized through the manager and multiplexed to all
        admin clients, and from there on to all views connected to each
        admin client model.

        Because there can be any number of admin clients that this call
        will go out do, it does not make sense to have one return value.
        This function will return None always.
        """
        if self.medium:
            self.medium.callRemote("adminCallRemote", methodName,
                                   *args, **kwargs)
        else:
            self.debug('asked to adminCallRemote(%s, *%r, **%r), but '
                       'no manager.'
                       % (methodName, args, kwargs))

    def _pollCPU(self):
        self._cpuPollerDC = None
        # update CPU time stats
        nowTime = time.time()
        nowClock = time.clock()
        deltaTime = nowTime - self._lastTime
        deltaClock = nowClock - self._lastClock
        self._lastTime = nowTime
        self._lastClock = nowClock
        # deltaClock can be < 0 if time.clock() wrapped around
        if deltaClock >= 0:
            CPU = deltaClock/deltaTime
            self.log('latest CPU use: %r', CPU)
            self.uiState.set('cpu-percent', CPU)

        self.uiState.set('current-time', nowTime)

    def _pollMemory(self):
        self._memoryPollerDC = None
        # Figure out our virtual memory size and report that.
        # I don't know a nicer way to find vsize than groping /proc/
        handle = open('/proc/%d/stat' % os.getpid())
        line = handle.read()
        handle.close()
        fields = line.split()
        # field 1 (comm) could potentially contain spaces and thus split over
        # multiple list items, but our processes do not contain spaces
        vsize = int(fields[22])
        self.log('vsize is %d', vsize)
        self.uiState.set('virtual-size', vsize)

    def _getTotalMemory(self):
        f = open("/proc/meminfo")
        memtotal = f.readline()
        f.close()
        return int(memtotal[memtotal.index(":") + 1: -3]) * 1024
