# -*- Mode: Python -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# flumotion/manager/worker.py: manager-side objects to handle workers
# 
# Flumotion - a streaming media server
# Copyright (C) 2004 Fluendo (www.fluendo.com)

# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
# See "LICENSE.GPL" in the source distribution for more information.

# This program is also licensed under the Flumotion license.
# See "LICENSE.Flumotion" in the source distribution for more information.

"""
Manager-side objects to handle worker clients.
"""

from twisted.spread import pb

from flumotion.common import errors, interfaces, log
from flumotion.common.config import FlumotionConfigXML

class WorkerAvatar(pb.Avatar, log.Loggable):
    """
    I am an avatar created for a worker.
    A reference to me is given when logging in and requesting an "worker" avatar.
    I live in the manager.
    """
    
    __implements__ = interfaces.INewCredPerspective

    logCategory = 'worker-avatar'

    def __init__(self, heaven, avatarId):
        self.heaven = heaven
        self.avatarId = avatarId

    def getName(self):
        return self.avatarId
    
    def attached(self, mind):
        self.info('attached %r' % mind)
        self.mind = mind

        self.heaven.workerAttached(self)
    
    def detached(self, mind):
        self.info('detached %r' % mind)

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
        self.info('starting %s on %s with config %r' % (name, self.avatarId, config))
        return self.mind.callRemote('start', name, type, config)
        
class WorkerHeaven(pb.Root, log.Loggable):
    """
    I interface between the Manager and worker clients.
    For each worker client I create an L{WorkerAvatar} to handle requests.
    I live in the manager.
    """
    
    logCategory = "workerheaven"
    __implements__ = interfaces.IHeaven
    
    def __init__(self, vishnu):
        """
        @type vishnu: L{flumotion.manager.manager.Vishnu}
        @param vishnu: the Vishnu object
        """
        self.avatars = {} # avatarId -> WorkerAvatar
        self.conf = None
        self.vishnu = vishnu
        
    ### IHeaven methods

    def createAvatar(self, avatarId):
        avatar = WorkerAvatar(self, avatarId)
        self.avatars[avatarId] = avatar
        return avatar

    def removeAvatar(self, avatarId):
        del self.avatars[avatarId]

    ### my methods

    def loadConfiguration(self, filename):
        # XXX: Merge?
        self.conf = FlumotionConfigXML(filename)
        return

    def getEntries(self, worker):
        # get all components from the config for this worker
        workerName = worker.getName()
        if not self.conf:
            return []

        retval = []

        # scan config for all atmosphere and grid component Entries
        entries = {}
        if self.conf.atmosphere.components:
            entries.update(self.conf.atmosphere.components)
        for gridEntry in self.conf.grids:
            entries.update(gridEntry.components)

        for entry in entries.values():
            if entry.worker and entry.worker != workerName:
                continue
            retval.append(entry)
        return retval
       
    def workerAttached(self, workerAvatar):
        # called when the mind is attached, ie the worker logged in
        self.debug('workerAttached(): worker %r logged in' % workerAvatar)

        # get all components that are supposed to start on this worker
        entries = self.getEntries(workerAvatar)
        workerName = workerAvatar.getName()
        for entry in entries:
            componentName = entry.getName()
            self.debug('workerAttached(): starting component: %s on %s' % (
                componentName, workerName))
            # FIXME: we need to put default feeds in this dict
            dict = entry.getConfigDict()
            
            if dict.has_key('config'):
                del dict['config'] # HACK

            self.workerStartComponent(workerName, componentName,
                entry.getType(), dict)
            
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
            raise AttributeError

        if workerName:
            avatar = self.avatars[workerName]
        else:
            # XXX: Do we really want to keep this big hack?
            # eg, if we don't select a worker, just pick the first one.
            avatar = self.avatars.values()[0]

        return avatar.start(componentName, type, config)
