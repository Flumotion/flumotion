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
from flumotion.common import errors, interfaces, log
from flumotion.common import config, worker

class WorkerAvatar(base.ManagerAvatar):
    """
    I am an avatar created for a worker.
    A reference to me is given when logging in and requesting a worker avatar.
    I live in the manager.
    """
    logCategory = 'worker-avatar'

    def getName(self):
        return self.avatarId

    def attached(self, mind):
        self.info('worker "%s" logged in' % self.getName())
        base.ManagerAvatar.attached(self, mind)
        self.heaven.workerAttached(self)
        self.vishnu.workerAttached(self)

    def detached(self, mind):
        self.info('worker "%s" logged out' % self.getName())
        base.ManagerAvatar.detached(self, mind)
        self.heaven.workerDetached(self)
        self.vishnu.workerDetached(self)
    
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
        self.debug('starting %s on worker %s with config %r' % (
            avatarId, self.avatarId, config))
        return self.mindCallRemote('start', avatarId, type, config)

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
        # called when the mind is attached, ie the worker logged in
        workerName = workerAvatar.getName()
        if not workerName in self.state.get('names'):
            self.state.append('names', workerName)

    def workerDetached(self, workerAvatar):
        workerName = workerAvatar.getName()
        names = self.state.get('names')
        if workerName in self.state.get('names'):
            self.state.remove('names', workerName)
