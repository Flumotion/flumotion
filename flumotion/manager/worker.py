# -*- Mode: Python -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# flumotion/manager/worker.py: manager-side objects to handle workers
# 
# Flumotion - a streaming media server
# Copyright (C) 2004 Fluendo, S.L. (www.fluendo.com). All rights reserved.

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
Manager-side objects to handle worker clients.
"""

import socket

from twisted.spread import pb

from flumotion.manager import common
from flumotion.common import errors, interfaces, log
from flumotion.common.config import FlumotionConfigXML

class WorkerAvatar(common.ManagerAvatar):
    """
    I am an avatar created for a worker.
    A reference to me is given when logging in and requesting a worker avatar.
    I live in the manager.
    """
    
    __implements__ = interfaces.INewCredPerspective

    logCategory = 'worker-avatar'

    def getName(self):
        return self.avatarId

    def attached(self, mind):
        common.ManagerAvatar.attached(self, mind)

        self.heaven.workerAttached(self)
    
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
        return self.mindCallRemote('start', name, type, config)

class WorkerHeaven(common.ManagerHeaven):
    """
    I interface between the Manager and worker clients.
    For each worker client I create an L{WorkerAvatar} to handle requests.
    I live in the manager.
    """
    
    logCategory = "workerheaven"
    avatarClass = WorkerAvatar
    
    def __init__(self, vishnu):
        common.ManagerHeaven.__init__(self, vishnu)
        self.conf = None
        
    ### my methods

    def loadConfiguration(self, filename, string=None):
        # XXX: Merge?
        self.conf = FlumotionConfigXML(filename, string)

        for worker in self.getAvatars():
            self.workerAttached(worker)
            
    def getEntries(self, worker):
        # get all components from the config for this worker
        workerName = worker.getName()
        if not self.conf:
            return []

        retval = []

        # scan config for all atmosphere and flow component Entries
        entries = {}
        if self.conf.atmosphere and self.conf.atmosphere.components:
            entries.update(self.conf.atmosphere.components)
            
        for flowEntry in self.conf.flows:
            entries.update(flowEntry.components)

        for entry in entries.values():
            if entry.worker and entry.worker != workerName:
                continue
            retval.append(entry)
        return retval
       
    def workerAttached(self, workerAvatar):
        # called when the mind is attached, ie the worker logged in
        self.info('worker "%s" logged in' % workerAvatar.getName())
        
        # get all components that are supposed to start on this worker
        workerName = workerAvatar.getName()
        for entry in self.getEntries(workerAvatar):
            componentName = entry.getName()
            self.debug('workerAttached(): starting component: %s on %s' % (
                componentName, workerName))
            
            self.workerStartComponent(workerName,
                                      componentName,
                                      entry.getType(),
                                      entry.getConfigDict())
            
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
