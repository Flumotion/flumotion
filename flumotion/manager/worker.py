# -*- Mode: Python; test-case-name: flumotion.test.test_manager_worker -*-
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
manager-side objects to handle worker clients
"""

import socket

from twisted.spread import pb
from twisted.internet import defer

# FIXME: rename to base
from flumotion.manager import base
from flumotion.common import errors, interfaces, log, registry
from flumotion.common import config, worker, common
from flumotion.twisted.defer import defer_generator_method

PortSet = worker.PortSet

class WorkerAvatar(base.ManagerAvatar):
    """
    I am an avatar created for a worker.
    A reference to me is given when logging in and requesting a worker avatar.
    I live in the manager.
    """
    logCategory = 'worker-avatar'

    portset = None

    def getName(self):
        return self.avatarId

    def attached(self, mind):
        # doc in base class
        self.info('worker "%s" logged in' % self.getName())
        base.ManagerAvatar.attached(self, mind)

        d = self.mindCallRemote('getPorts')
        yield d
        ports = d.value()
        self.portset = PortSet(self.avatarId, ports)

        self.heaven.workerAttached(self)
        self.vishnu.workerAttached(self)
    attached = defer_generator_method(attached)

    def detached(self, mind):
        # doc in base class
        self.info('worker "%s" logged out' % self.getName())
        base.ManagerAvatar.detached(self, mind)
        self.heaven.workerDetached(self)
        self.vishnu.workerDetached(self)
    
    def reservePorts(self, numPorts):
        """
        Reserve the given number of ports on the worker.

        @param numPorts: how many ports to reserve
        @type  numPorts: int
        """
        return self.portset.reservePorts(numPorts)

    def releasePorts(self, ports):
        """
        Release the given list of ports on the worker.
    
        @param ports: list of ports to release
        @type  ports: list of int
        """
        self.portset.releasePorts(ports)

    def createComponent(self, avatarId, type, config):
        """
        Create a component of the given type with the given config.

        @param avatarId: avatarId the component should use to log in
        @type  avatarId: str
        @param type:     type of the component to create
        @type  type:     str
        @param config:   a configuration dictionary for the component
        @type  config:   dict

        @returns: a deferred that will give the avatarId the component
                  will use to log in to the manager
        """
        self.debug('creating %s (%s) on worker %s with config %r' % (
            avatarId, type, self.avatarId, config))
        defs = registry.getRegistry().getComponent(type)
        try:
            entry = defs.getEntryByType('component')
            # FIXME: use entry.getModuleName() (doesn't work atm?)
            moduleName = defs.getSource()
            methodName = entry.getFunction()
        except KeyError:
            self.warning('no "component" entry in registry of type %s, %s',
                         type, 'falling back to createComponent')
            moduleName = defs.getSource()
            methodName = "createComponent"

        self.debug('call remote create')
        return self.mindCallRemote('create', avatarId, type, moduleName,
            methodName, config)

    ### IPerspective methods, called by the worker's component
    def perspective_componentAddMessage(self, avatarId, message):
        """
        Called by the worker to tell the manager to add a given message to
        the given component.
        
        Useful in cases where the component can't report messages itself,
        for example because it crashed.

        @param avatarId: avatarId of the component the message is about
        @type  message:  L{flumotion.common.messages.Message}
        """
        self.debug('received message from component %s' % avatarId)
        self.vishnu.componentAddMessage(avatarId, message)

class WorkerHeaven(base.ManagerHeaven):
    """
    I interface between the Manager and worker clients.
    For each worker client I create an L{WorkerAvatar} to handle requests.
    I live in the manager.
    """
    
    logCategory = "workerheaven"
    avatarClass = WorkerAvatar
    
    def __init__(self, vishnu):
        base.ManagerHeaven.__init__(self, vishnu)
        self.conf = None
        self.state = worker.ManagerWorkerHeavenState()
        
    ### my methods
    def workerAttached(self, workerAvatar):
        """
        Notify the heaven that the given worker has logged in.

        @type  workerAvatar: L{WorkerAvatar}
        """
        workerName = workerAvatar.getName()
        if not workerName in self.state.get('names'):
            # wheee
            host = workerAvatar.mind.broker.transport.getPeer().host
            state = worker.ManagerWorkerState(name=workerName, host=host)
            self.state.append('names', workerName)
            self.state.append('workers', state)
        else:
            # FIXME: what if it was already there ?
            self.warning('worker %s was already registered in the heaven' %
                workerName)

    def workerDetached(self, workerAvatar):
        """
        Notify the heaven that the given worker has logged out.

        @type  workerAvatar: L{WorkerAvatar}
        """
        workerName = workerAvatar.getName()
        names = self.state.get('names')
        try:
            self.state.remove('names', workerName)
            for state in list(self.state.get('workers')):
                if state.get('name') == workerName:
                    self.state.remove('workers', state)
        except ValueError:
            self.warning('worker %s was never registered in the heaven' %
                workerName)
