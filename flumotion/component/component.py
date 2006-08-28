# -*- Mode: Python; test-case-name: flumotion.test.test_component -*-
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
worker-side objects for components
"""

import os
import sys
import time
import socket

import gobject

from twisted.internet import reactor, error, defer
from twisted.cred import error as crederror
from twisted.spread import pb
from twisted.python import reflect

from flumotion.common import interfaces, errors, log, planet, medium, pygobject
from flumotion.common import componentui, common, registry, messages, interfaces
from flumotion.common.planet import moods
from flumotion.configure import configure
from flumotion.twisted import credentials
from flumotion.twisted import pb as fpb
from flumotion.twisted.compat import implements
from flumotion.common.pygobject import gsignal

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
        
    # override log.Loggable method so we don't traceback
    def error(self, format, *args):
        if args:
            message = format % args
        else:
            message = format
        self.warning('Shutting down because of %s' % message)
        print >> sys.stderr, 'ERROR: [%d] %s' % (os.getpid(), message)
        # FIXME: do we need to make sure that this cannot shut down the
        # manager if it's the manager's bouncer ?
        reactor.stop()
        self.component.setMood(moods.sad)

    # vmethod implementation
    def gotDeferredLogin(self, d):
        def remoteDisconnected(remoteReference):
            if reactor.killed:
                self.log('Connection to manager lost due to SIGINT shutdown')
            else:
                self.warning('Lost connection to manager, '
                             'will attempt to reconnect')

        def loginCallback(reference):
            self.info("Logged in to manager")
            self.debug("remote reference %r" % reference)
            self.medium.setRemoteReference(reference)
            reference.notifyOnDisconnect(remoteDisconnected)

        def accessDeniedErrback(failure):
            failure.trap(crederror.UnauthorizedLogin)
            self.error('Access denied.')
            
        def connectionRefusedErrback(failure):
            failure.trap(error.ConnectionRefusedError)
            self.error('Connection to manager refused.')
                                                          
        def alreadyLoggedInErrback(failure):
            failure.trap(errors.AlreadyConnectedError)
            # If we fail to connect (on the initial connection attempt), we 
            # won't have a name set yet. In that case, figure it out from 
            # avatarId, so we can give a decent  error message.
            name = self.component.name
            if not name:
                # Nasty hack!
                name = common.parseComponentId(
                    self.medium.authenticator.avatarId)[1]

            self.error('Component named %s is already logged in.', name)
                                                          
        def loginFailedErrback(failure):
            self.error('Login failed, reason: %s' % failure)

        d.addCallback(loginCallback)
        d.addErrback(accessDeniedErrback)
        d.addErrback(connectionRefusedErrback)
        d.addErrback(alreadyLoggedInErrback)
        d.addErrback(loginFailedErrback)

    # we want to save the authenticator
    def startLogin(self, authenticator):
        self.medium.setAuthenticator(authenticator)
        return fpb.ReconnectingFPBClientFactory.startLogin(self, authenticator)

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

        self.reactor_stopped = False
        
    ### our methods
    def setup(self, config):
        pass

    def getIP(self):
        """
        Return the manager IP as seen by us.
        """
        assert self.remote
        peer = self.remote.broker.transport.getPeer()
        try:
            host = peer.host
        except AttributeError:
            host = peer[1]

        res = socket.gethostbyname(host)
        self.debug("getIP(): we think the manager's IP is %r" % res)
        return res

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
        self.comp.state.set('ip', self.getIP())
        return self.comp.state
        
    def remote_getConfig(self):
        """
        Return the configuration of the component.

        @rtype:   dict
        @returns: component's current configuration
        """
        return self.comp.config
        
    def remote_setup(self, config):
        """
        Set up the component and the component's medium with the given config,
        in that order.
        """
        d = self.comp.setup(config)
        d.addCallback(lambda r, c: self.setup(c), config)
        return d
        
    def remote_start(self, *args, **kwargs):
        return self.comp.start(*args, **kwargs)
       
    def remote_stop(self):
        self.info('Stopping job')
        d = self.comp.stop()
        d.addCallback(self._destroyCallback)

        return d

    def _destroyCallback(self, result):
        self.debug('_destroyCallback: scheduling destroy')
        reactor.callLater(0, self._destroyCallLater)

    def _destroyCallLater(self):
        self.debug('_destroyCalllater: stopping reactor')
        self.reactor_stopped = True
        reactor.stop()

    def remote_reloadComponent(self):
        """Reload modules in the component."""
        import sys
        from twisted.python.rebuild import rebuild
        from twisted.python.reflect import filenameToModuleName
        name = filenameToModuleName(__file__)

        ## fixme: re-fetch bundles

        # reload ourselves first
        rebuild(sys.modules[name])

        # now rebuild relevant modules
        import flumotion.common.reload
        rebuild(sys.modules['flumotion.common'])
        try:
            flumotion.common.reload.reload()
        except SyntaxError, msg:
            raise errors.ReloadSyntaxError(msg)
        self._reloaded()

    def remote_getUIState(self):
        """Get a WorkerComponentUIState containing details needed to
        present an admin-side UI state
        """
        return self.comp.uiState

    # separate method so it runs the newly reloaded one :)
    def _reloaded(self):
        self.info('reloaded module code for %s' % __name__)

    def remote_callMethod(self, methodName, *args, **kwargs):
        method = getattr(self.comp, 'remote_' + methodName, None)
        if method:
            return method(*args, **kwargs)
        msg = "%r doesn't have method remote_%s" % (self.comp, methodName)
        self.warning(msg)
        raise errors.MoMethodError(msg)

class BaseComponent(common.InitMixin, log.Loggable, gobject.GObject):
    """
    I am the base class for all Flumotion components.

    @ivar name:   the name of the component
    @type name:   string
    @ivar medium: the component's medium
    @type medium: L{BaseComponentMedium}

    @cvar componentMediumClass: the medium class to use for this component
    @type componentMediumClass: child class of L{BaseComponentMedium}
    """

    logCategory = 'basecomp'
    componentMediumClass = BaseComponentMedium
    
    def __init__(self):
        # FIXME: name is unique where ? only in flow, so not in worker
        # need to use full path maybe ?
        """
        Subclasses should not override __init__ at all.
        
        Instead, they should implement init(), which will be called
        by this implementation automatically.

        See L{flumotion.common.common.InitMixin} for more details.
        """
        gobject.GObject.__init__(self)

        # this will call self.init() for all implementors of init()
        common.InitMixin.__init__(self)

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

        self.name = None
        
        #self.state.set('name', name)
        self.state.set('pid', os.getpid())

        self.medium = None # the medium connecting us to the manager's avatar
 
        self.uiState = componentui.WorkerComponentUIState()

        # FIXME: when we need this somewhere else, put this in a class and
        # use it that way
        self.baseTime = time.time()
        self.lastTime = time.time()
        self.lastClock = time.clock()

        self.plugs = {}

        # Start the cpu-usage updating.
        self._cpuCallLater = reactor.callLater(5, self._updateCPUUsage)

    def do_check(self):
        """
        Subclasses can implement me to run any checks before the component
        performs setup.

        Messages can be added to the component state's 'messages' list key.
        Any error messages added will trigger the component going to sad
        an L{flumotion.common.errors.ComponentSetupError} being raised;
        do_setup() will not be called.

        In the event of a fatal problem that can't be expressed through an
        error message, this method should set the mood to sad and raise the
        error on its own.

        self.config will be set when this is called.

        @Returns: L{twisted.internet.defer.Deferred}
        """
        return defer.succeed(None)

    def do_setup(self):
        """
        Subclasses can implement me to set up the component before it is
        started.  It should set up the component, possibly opening files
        and resources.
        Non-programming errors should not be raised, but returned as a
        failing deferred.

        self.config will be set when this is called.

        @Returns: L{twisted.internet.defer.Deferred}
        """
        return defer.succeed(None)

    def do_start(self, *args, **kwargs):
        """
        BaseComponent vmethod for starting up. If you override this
        method, you are responsible for arranging that the component
        becomes happy.

        @Returns: L{twisted.internet.defer.Deferred}
        """
        # default behavior
        self.setMood(moods.happy)
        return defer.succeed(None)
       
    def do_stop(self):
        """
        BaseComponent vmethod for stopping.
        The component should do any cleanup it needs, but must not set the
        component's mood to sleeping.

        @Returns: L{twisted.internet.defer.Deferred}
        """
        return defer.succeed(None)
 
    ### BaseComponent implementation related to compoment protocol
    ### called by manager through medium
    def setup(self, config, *args, **kwargs):
        """
        Sets up the component with the given config.  Called by the manager
        through the medium.

        @Returns: L{twisted.internet.defer.Deferred}
        @raise    flumotion.common.errors.ComponentSetupError:
                  when an error happened during setup of the component
        """
        def setup_plugs():
            # by this time we have a medium, so we can load bundles
            reg = registry.getRegistry()

            def load_bundles():
                modules = {}
                for plugs in config['plugs'].values():
                    for plug in plugs:
                        modules[plug['type']] = True
                for plugtype in modules.keys():
                    # we got this far, it should work
                    entry = reg.getPlug(plugtype).getEntry()
                    modules[plugtype] = entry.getModuleName()
                if not modules:
                    return defer.succeed(True) # shortcut
                elif not self.medium:
                    self.warning('Not connected to a medium, cannot '
                                 'load bundles -- assuming all modules '
                                 'are available')
                    return defer.succeed(True)
                else:
                    loader = self.medium.bundleLoader
                    return loader.getBundles(moduleName=modules.values())
                
            def make_plugs():
                for socket, plugs in config['plugs'].items():
                    self.plugs[socket] = []
                    for plug in plugs:
                        entry = reg.getPlug(plug['type']).getEntry()
                        module = reflect.namedAny(entry.getModuleName())
                        proc = getattr(module, entry.getFunction())
                        instance = proc(plug)
                        self.plugs[socket].append(instance)

            try:
                d = load_bundles()
                d.addCallback(lambda x: make_plugs())
                return d
            except Exception, e:
                self.debug("Exception while loading bundles: %s" % 
                    log.getExceptionMessage(e))
                return defer.fail(e)

        def checkErrorCallback(result):
            # if the mood is now sad, it means an error was encountered
            # during check, and we should return a failure here.
            current = self.state.get('mood')
            if current == moods.sad.value:
                self.warning('Running checks made the component sad.')
                raise errors.ComponentSetupError()

        self.debug("setup() called with config %r", config)
        self.setMood(moods.waking)
        self._setConfig(config)
        # now we have a name, set it on the medium too
        if self.medium:
            self.medium.logName = self.getName()
        d = setup_plugs()
        d.addCallback(lambda r: self.do_check())
        d.addCallback(checkErrorCallback)
        d.addCallback(lambda r: self.do_setup())
        return d

    def start(self, *args, **kwargs):
        """
        Tell the component to start.  This is called when all its dependencies
        are already started.

        To hook onto this method, implement your own do_start method.
        See BaseComponent.do_start() for what your do_start method is
        responsible for doing.

        Again, don't override this method. Thanks.
        """
        self.debug('BaseComponent.start')

        def start_plugs():
            for socket, plugs in self.plugs.items():
                for plug in plugs:
                    self.debug('Starting plug %r on socket %s', plug, socket)
                    plug.start(self)

        try:
            start_plugs()
            ret = self.do_start(*args, **kwargs)
            assert isinstance(ret, defer.Deferred), \
                   "do_start %r must return a deferred" % self.do_start
            self.debug('start: returning value %s' % ret)
            return ret
        except Exception, e:
            self.debug("Exception during component do_start: %s" % 
                log.getExceptionMessage(e))
            return defer.fail(e)
        
    def stop(self):
        """
        Tell the component to stop.
        The connection to the manager will be closed.
        The job process will also finish.
        """
        self.debug('BaseComponent.stop')

        def stop_plugs(ret):
            for socket, plugs in self.plugs.items():
                for plug in plugs:
                    self.debug('Stopping plug %r on socket %s', plug, socket)
                    plug.stop(self)
            return ret

        self.setMood(moods.waking)
        for message in self.state.get('messages'):
            self.state.remove('messages', message)

        if self._cpuCallLater:
            self._cpuCallLater.cancel()
            self._cpuCallLater = None

        d = self.do_stop()
        d.addCallback(stop_plugs)
        return d

    ### GObject methods
    def emit(self, name, *args):
        if 'uninitialized' in str(self):
            self.warning('Uninitialized object!')
            #self.__gobject_init__()
        else:
            gobject.GObject.emit(self, name, *args)
        
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

        self.debug('MOOD changed to %r' % mood)
        self.state.set('mood', mood.value)

    def getMood(self):
        """
        Gets the mood on the component.

        @rtype: int
        """
        return self.state.get('mood')

        
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

    # private methods
    def _setConfig(self, config):
        if self.name:
            assert config['name'] == self.name, \
                   "Can't change name while running"
        self.config = config
        self.name = config['name']

    def _updateCPUUsage(self):
        # update CPU time stats
        nowTime = time.time()
        nowClock = time.clock()
        deltaTime = nowTime - self.lastTime
        deltaClock = nowClock - self.lastClock
        CPU = deltaClock/deltaTime
        self.log('latest CPU use: %r' % CPU)
        self.state.set('cpu', CPU)
        deltaTime = nowTime - self.baseTime
        deltaClock = nowClock
        CPU = deltaClock/deltaTime
        self.lastTime = nowTime
        self.lastClock = nowClock

        self._cpuCallLater = reactor.callLater(5, self._updateCPUUsage)

pygobject.type_register(BaseComponent)
