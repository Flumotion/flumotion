# -*- Mode: Python; test-case-name: flumotion.test.test_manager_worker -*-
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

class PortSet(log.Loggable):
    """
    A list of ports that keeps track of which are available for use by a
    given worker.
    """
    def __init__(self, workername, ports):
        self.logName = workername
        self.ports = ports
        self.used = [False] * len(ports)

    def reservePorts(self, numPorts):
        ret = []
        while numPorts > 0:
            if not False in self.used:
                raise errors.ComponentStart('could not allocate port '
                                            'on worker %s' % self.logName)
            i = self.used.index(False)
            ret.append(self.ports[i])
            self.used[i] = True
            numPorts -= 1
        return ret

    def releasePorts(self, ports):
        for p in ports:
            try:
                i = self.ports.index(p)
                if self.used[i]:
                    self.used[i] = False
                else:
                    self.warning('releasing unallocated port: %d' % p)
            except ValueError:
                self.warning('releasing unknown port: %d' % p)

    def numFree(self):
        return len(filter(lambda x: not x, self.used))
    
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
        self.info('worker "%s" logged out' % self.getName())
        base.ManagerAvatar.detached(self, mind)
        self.heaven.workerDetached(self)
        self.vishnu.workerDetached(self)
    
    def reservePorts(self, numPorts):
        return self.portset.reservePorts(numPorts)

    def releasePorts(self, ports):
        self.portset.releasePorts(ports)

    def start(self, avatarId, type, config):
        """
        Start a component of the given type with the given config.

        @param avatarId: avatarId the component should use to log in
        @type  avatarId: string
        @param type:     type of the component to start
        @type  type:     string
        @param config:   a configuration dictionary for the component
        @type  config:   dict

        @returns: a deferred that will give the avatarId the component
                  will use to log in to the manager
        """
        self.debug('starting %s (%s) on worker %s with config %r' % (
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

        return self.mindCallRemote('start', avatarId, type, moduleName,
            methodName, config)

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
        # called when the mind of a worker is attached, ie the worker logged in
        workerName = workerAvatar.getName()
        # FIXME: what if it was already there ?
        if not workerName in self.state.get('names'):
            self.state.append('names', workerName)

        # self.vishnu.workerAttached(workerAvatar)

    def workerDetached(self, workerAvatar):
        workerName = workerAvatar.getName()
        names = self.state.get('names')
        if workerName in self.state.get('names'):
            self.state.remove('names', workerName)
