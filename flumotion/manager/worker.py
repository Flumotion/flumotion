# -*- Mode: Python -*-
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

    def detached(self, mind):
        self.info('worker "%s" logged out' % self.getName())
        base.ManagerAvatar.detached(self, mind)
        # FIXME: rename heaven methods to avatarDetached, move to base ?
        self.heaven.workerDetached(self)
    
    def start(self, name, type, config):
        """
        Start a component of the given type with the given config.
                                                                                
        @param name:   name of the component to start
        @type name:    string
        @param type:   type of the component to start
        @type type:    string
        @param config: a configuration dictionary for the component
        @type config:  dict
        """
        self.debug('starting %s on %s with config %r' % (name, self.avatarId,
            config))
        return self.mindCallRemote('start', name, type, config, self.avatarId)

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

    def loadConfiguration(self, filename, string=None):
        # XXX: Merge?
        self.conf = config.FlumotionConfigXML(filename, string)

        # trigger an update of config for all attached workers
        for worker in self.getAvatars():
            self.workerAttached(worker)
            
    def getEntries(self, worker):
        # get all components from the config for this worker
        workerName = worker.getName()
        if not self.conf:
            return []

        retval = []

        entries = self.conf.getComponentEntries()

        for entry in entries.values():
            if entry.worker and entry.worker != workerName:
                continue
            retval.append(entry)
        return retval
       
    def workerAttached(self, workerAvatar):
        # called when the mind is attached, ie the worker logged in
        workerName = workerAvatar.getName()
        if not workerName in self.state.get('names'):
            self.state.append('names', workerName)
        
        # get all components that are supposed to start on this worker
        for entry in self.getEntries(workerAvatar):
            componentName = entry.getName()
            self.debug('workerAttached(): starting component: %s on %s' % (
                componentName, workerName))
            
            self.workerStartComponent(workerName,
                                      componentName,
                                      entry.getType(),
                                      entry.getConfigDict())

    def workerDetached(self, workerAvatar):
        workerName = workerAvatar.getName()
        names = self.state.get('names')
        if workerName in self.state.get('names'):
            self.state.remove('names', workerName)
            
    def workerStartComponent(self, workerName, componentName, type, config):
        """
        @param workerName:    name of the worker to start component on
        @type  workerName:    string
        @param componentName: name of the component to start
        @type  componentName: string
        @param type:          type of the component to start
        @type  type:          string
        @param config:        a configuration dictionary
        @type  config:        dict
        """

        if not self.avatars:
            raise AttributeError()

        if workerName:
            avatar = self.avatars[workerName]
        else:
            # XXX: Do we really want to keep this big hack?
            # eg, if we don't select a worker, just pick the first one.
            avatar = self.avatars.values()[0]

        self.info('Starting component "%s" on worker "%s"' % (
            componentName, workerName))
        return avatar.start(componentName, type, config)
