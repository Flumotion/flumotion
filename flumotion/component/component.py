# -*- Mode: Python; test-case-name: flumotion.test.test_component -*-
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
worker-side objects for components
"""

import os
import sys
import socket

import gobject

from twisted.internet import reactor, error
from twisted.cred import error as crederror
from twisted.spread import pb

from flumotion.common import interfaces, errors, log, planet
from flumotion.common.planet import moods
from flumotion.configure import configure
from flumotion.twisted import credentials
from flumotion.twisted import pb as fpb
from flumotion.common.pygobject import gsignal

# FIXME: make the superklass reconnecting ?
superklass = fpb.FPBClientFactory
# the client factory logging in to the manager
class ComponentClientFactory(superklass):
    """
    I am a client factory for a component logging in to the manager.
    """
    logCategory = 'component'
    __super_login = superklass.login
    def __init__(self, component):
        """
        @param component: L{flumotion.component.component.BaseComponent}
        """
        # doing this as a class method triggers a doc error
        super_init = superklass.__init__
        super_init(self)
        
        self.component = component
        # get the component's medium class, defaulting to the base one
        klass = getattr(component, 'component_medium_class', BaseComponentMedium)
        # instantiate the medium, giving it the component it's a medium for
        self.medium = klass(component)
        component.setMedium(self.medium)

        # get the interfaces implemented by the component medium class
        self.interfaces = getattr(klass, '__implements__', ())

        self.logName = component.name
        
    # override log.Loggable method so we don't traceback
    def error(self, message):
        self.warning('Shutting down because of %s' % message)
        print >> sys.stderr, 'ERROR: %s' % message
        # FIXME: do we need to make sure that this cannot shut down the
        # manager if it's the manager's bouncer ?
        reactor.stop()
        self.component.setMood(moods.sad)

    def login(self, keycard):
        d = self.__super_login(keycard, self.medium,
                               interfaces.IComponentMedium)
        d.addCallback(self._loginCallback)
        d.addErrback(self._unauthorizedLoginErrback)
        d.addErrback(self._connectionRefusedErrback)
        d.addErrback(self._loginErrback)
        return d
        
    # this method receives a RemoteReference
    # it can't tell if it's from an IPerspective implementor, Viewpoint or
    # Referenceable
    def _loginCallback(self, remoteReference):
        """
        @param remoteReference: an object on which we can callRemote to the
                                manager's avatar
        @type remoteReference: L{twisted.spread.pb.RemoteReference}
        """
        self.medium.setRemoteReference(remoteReference)

    def _unauthorizedLoginErrback(self, failure):
        failure.trap(crederror.UnauthorizedLogin)
        self.error('Unauthorized login.')
                                                                                
    def _connectionRefusedErrback(self, failure):
        failure.trap(error.ConnectionRefusedError)
        self.error('Connection to %s:%d refused.' % (self.manager_host,
                                                     self.manager_port))

    def _loginErrback(self, failure):
        self.error('Login failed, reason: %r' % failure)
    
# needs to be before BaseComponent because BaseComponent references it
class BaseComponentMedium(pb.Referenceable, log.Loggable):
    """
    I am a medium interfacing with a manager-side avatar.
    I implement a Referenceable for the manager's avatar to call on me.
    I have a remote reference to the manager's avatar to call upon.
    """

    __implements__ = interfaces.IComponentMedium,
    logCategory = 'basecompmedium'

    def __init__(self, component):
        """
        @param component: L{flumotion.component.component.BaseComponent}
        """
        self.comp = component
        self.comp.connect('log', self._component_log_cb)
        
        self.remote = None # the perspective we have on the other side (?)

        self.logName = component.name
        
    ### IMedium methods
    def setRemoteReference(self, remoteReference):
        self.remote = remoteReference
        
    def hasRemoteReference(self):
        return self.remote != None

    # call function on remote perspective in manager
    def callRemoteErrback(self, failure):
        self.warning('callRemote failed because of %r' % failure)
        failure.trap(pb.PBConnectionLost)
        
    def callRemote(self, name, *args, **kwargs):
        """
        @returns: a deferred
        """
        if not self.hasRemoteReference():
            self.debug('skipping %s, no perspective' % name)
            return

        #def errback(reason):
        #    self.warning('stopping pipeline because of %s' % reason)
        #    self.comp.pipeline_stop()

        try:
            d = self.remote.callRemote(name, *args, **kwargs)
        except pb.DeadReferenceError:
            return
        
        d.addErrback(self.callRemoteErrback)
        return d

    ### our methods
    def getIP(self):
        """
        Return our own IP as seen from the manager.
        """
        assert self.remote
        peer = self.remote.broker.transport.getPeer()
        try:
            host = peer.host
        except AttributeError:
            host = peer[1]

        return socket.gethostbyname(host)

    def _component_log_cb(self, component, args):
        self.callRemote('log', *args)
        
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
        self.debug('remote_getState of f: returning %r' % self.comp.state)

        return self.comp.state
        
    def remote_start(self, *args, **kwargs):
        """
        Tell the component to start.  This is called when all its dependencies
        are already started.

        Extended by subclasses.  Subclasses call this as the last method if
        the start is successful.  Sets the mood to happy.
        """
        self.comp.updateMood()
        self.comp.startHeartbeat()
        
    def remote_stop(self):
        """
        Tell the component to stop.
        The connection to the manager will be closed.
        The job process will also finish.
        """
        self.comp.stopHeartbeat()
        self.comp.stop()
        self.remote.broker.transport.loseConnection()
        reactor.stop()

    def remote_reloadComponent(self):
        """Reload modules in the component."""
        import sys
        from twisted.python.rebuild import rebuild
        from twisted.python.reflect import filenameToModuleName
        name = filenameToModuleName(__file__)

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

class BaseComponent(log.Loggable, gobject.GObject):
    """
    I am the base class for all Flumotion components.

    @ivar name: the name of the component
    @type name: string

    @cvar component_medium_class: the medium class to use for this component
    @type component_medium_class: child class of L{BaseComponentMedium}
    """

    __remote_interfaces__ = interfaces.IComponentMedium,
    logCategory = 'basecomp'

    gsignal('log', object)

    component_medium_class = BaseComponentMedium
    _heartbeatInterval = configure.heartbeatInterval
    
    def __init__(self, name):
        # FIXME: name is unique where ? only in flow, so not in worker
        # need to use full path maybe ?
        """
        @param name: unique name of the component
        @type name: string
        """
        self.__gobject_init__()

        self.state = planet.WorkerJobState()
        
        #self.state.set('name', name)
        self.state.set('mood', moods.sleeping.value)
        self.state.set('pid', os.getpid())

        # FIXME: remove stuff in state
        self.name = name

        self._HeartbeatDC = None
        self.medium = None # the medium connecting us to the manager's avatar
 
    def updateMood(self):
        """
        Update the mood because a mood condition has changed.
        Will not change the mood if it's sad - sad needs to be explicitly
        fixed.

        See the mood transition diagram.
        """
        mood = self.state.get('mood')
        if mood == moods.sad.value:
            return

        # FIXME: probably could use a state where it's still starting ?
        self.setMood(moods.happy)
    
    def startHeartbeat(self):
        """
        Start sending heartbeats.
        """
        self._heartbeat()

    def stopHeartbeat(self):
        """
        Stop sending heartbeats.
        """
        if self._HeartbeatDC:
            self._HeartbeatDC.cancel()
        self._HeartbeatDC = None
         
    def _heartbeat(self):
        """
        Send heartbeat to manager and reschedule.
        """
        #self.log('Sending heartbeat')
        if self.medium:
            self.medium.callRemote('heartbeat', self.state.get('mood'))
        self._HeartbeatDC = reactor.callLater(self._heartbeatInterval,
            self._heartbeat)

    ### GObject methods
    def emit(self, name, *args):
        if 'uninitialized' in str(self):
            self.warning('Uninitialized object!')
            #self.__gobject_init__()
        else:
            gobject.GObject.emit(self, name, *args)
        
    ### BaseComponent methods
    def getName(self):
        return self.name

    def setWorkerName(self, workerName):
        self.state.set('workerName', workerName)

    def getWorkerName(self):
        return self.state.get('workerName')

    def setMedium(self, medium):
        assert isinstance(medium, BaseComponentMedium)
        self.medium = medium
        # send a heartbeat right now
        if self._HeartbeatDC:
            self._HeartbeatDC.reset(0)

    def setMood(self, mood):
        """
        Set the given mood on the component if it's different from the current
        one.
        """
        if self.state.get('mood') == mood.value:
            return

        self.debug('MOOD changed to %r' % mood)
        self.state.set('mood', mood.value)
        # send a heartbeat right now
        if self._HeartbeatDC:
            self._HeartbeatDC.reset(0)
        
    def adminCallRemote(self, methodName, *args, **kwargs):
        """
        Call a remote method on all admin client views on this component.

        This gets serialized through the manager and multiplexed to all
        admin clients, and from there on to all views connected to each
        admin client model.
        """
        self.medium.callRemote("adminCallRemote", methodName, *args, **kwargs)

gobject.type_register(BaseComponent)
