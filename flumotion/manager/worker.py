# -*- Mode: Python; test-case-name: flumotion.test.test_manager_worker -*-
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
manager-side objects to handle worker clients
"""

from twisted.internet import defer

from flumotion.manager import base
from flumotion.common import errors, log, registry
from flumotion.common import worker, common
from flumotion.common.vfs import registerVFSJelly

__version__ = "$Rev$"


class WorkerAvatar(base.ManagerAvatar):
    """
    I am an avatar created for a worker.
    A reference to me is given when logging in and requesting a worker avatar.
    I live in the manager.

    @ivar feedServerPort: TCP port the feed server is listening on
    @type feedServerPort: int
    """
    logCategory = 'worker-avatar'

    _portSet = None
    feedServerPort = None

    def __init__(self, heaven, avatarId, remoteIdentity, mind,
                 feedServerPort, ports, randomPorts):
        base.ManagerAvatar.__init__(self, heaven, avatarId,
                                    remoteIdentity, mind)
        self.feedServerPort = feedServerPort

        self._portSet = worker.PortSet(self.avatarId, ports, randomPorts)

        self.heaven.workerAttached(self)
        self.vishnu.workerAttached(self)

        registerVFSJelly()

    def getName(self):
        return self.avatarId

    def makeAvatarInitArgs(klass, heaven, avatarId, remoteIdentity,
                           mind):

        def havePorts(res):
            log.debug('worker-avatar', 'got port information')
            (_s1, feedServerPort), (_s2, (ports, random)) = res
            return (heaven, avatarId, remoteIdentity, mind,
                    feedServerPort, ports, random)
        log.debug('worker-avatar', 'calling mind for port information')
        d = defer.DeferredList([mind.callRemote('getFeedServerPort'),
                                mind.callRemote('getPorts')],
                               fireOnOneErrback=True)
        d.addCallback(havePorts)
        return d
    makeAvatarInitArgs = classmethod(makeAvatarInitArgs)

    def onShutdown(self):
        self.heaven.workerDetached(self)
        self.vishnu.workerDetached(self)
        base.ManagerAvatar.onShutdown(self)

    def reservePorts(self, numPorts):
        """
        Reserve the given number of ports on the worker.

        @param numPorts: how many ports to reserve
        @type  numPorts: int
        """
        return self._portSet.reservePorts(numPorts)

    def releasePorts(self, ports):
        """
        Release the given list of ports on the worker.

        @param ports: list of ports to release
        @type  ports: list of int
        """
        self._portSet.releasePorts(ports)

    def createComponent(self, avatarId, type, nice, conf):
        """
        Create a component of the given type with the given nice level.

        @param avatarId: avatarId the component should use to log in
        @type  avatarId: str
        @param type:     type of the component to create
        @type  type:     str
        @param nice:     the nice level to create the component at
        @type  nice:     int
        @param conf:     the component's config dict
        @type  conf:     dict

        @returns: a deferred that will give the avatarId the component
                  will use to log in to the manager
        """
        self.debug('creating %s (%s) on worker %s with nice level %d',
                   avatarId, type, self.avatarId, nice)
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
            methodName, nice, conf)

    def getComponents(self):
        """
        Get a list of components that the worker is running.

        @returns: a deferred that will give the avatarIds running on the
                  worker
        """
        self.debug('getting component list from worker %s' %
            self.avatarId)
        return self.mindCallRemote('getComponents')

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
            self.warning('worker %s was already registered in the heaven',
                         workerName)
            raise errors.AlreadyConnectedError()

    def workerDetached(self, workerAvatar):
        """
        Notify the heaven that the given worker has logged out.

        @type  workerAvatar: L{WorkerAvatar}
        """
        workerName = workerAvatar.getName()
        try:
            self.state.remove('names', workerName)
            for state in list(self.state.get('workers')):
                if state.get('name') == workerName:
                    self.state.remove('workers', state)
        except ValueError:
            self.warning('worker %s was never registered in the heaven',
                         workerName)
