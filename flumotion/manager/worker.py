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

from flumotion.common import errors, interfaces
from flumotion.common.config import FlumotionConfigXML
from flumotion.utils import log

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

        return
    
        name = 'testing'
        type = 'videotest'
        config = dict(width=320, height=240, framerate=5.0, name=name)
        
        self.start(name, type, config)
        
    def detached(self, mind):
        self.info('detached %r' % mind)

    def start(self, name, type, config):
        self.info('starting %s on %s' % (name, self.avatarId))
        return self.mind.callRemote('start', name, type, config)
        
class WorkerHeaven(pb.Root):
    """
    I interface between the Manager and worker clients.
    For each worker client I create an L{WorkerAvatar} to handle requests.
    I live in the manager.
    """
    
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
        if not self.conf.hasWorker(avatarId):
            raise AssertionError
            
        avatar = WorkerAvatar(self, avatarId)
        self.avatars[avatarId] = avatar
        return avatar

    def removeAvatar(self, avatarId):
        del self.avatars[avatarId]

    ### my methods

    def loadConfiguration(self, filename):
        # XXX: Merge?
        self.conf = FlumotionConfigXML(filename)

        workers = self.conf.getWorkers()
        if workers:
            self.setupWorkers(workers)

    def setupWorkers(self, workers):
        if workers.getPolicy() == 'password':
            self.vishnu.checker.allowAnonymous(False)

            for worker in workers.workers:
                self.vishnu.checker.addUser(worker.getUsername(),
                                            worker.getPassword())
            
    def getEntries(self, worker):
        if not self.conf:
            return []

        retval = []
        for entry in self.conf.entries.values():
            entry_worker = entry.getWorker()
            if entry_worker and entry_worker != worker.getName():
                continue
            retval.append(entry)
        return retval
       
        workers = [worker for worker in self.conf
                              if not worker or worker != worker.getName()]
        return workers
    
    def workerAttached(self, worker):
        entries = self.getEntries(worker)
        worker_name = worker.getName()
        for entry in entries:
            name = entry.getName()
            log.debug('config', 'Starting component: %s on %s' % (name, worker_name))
            dict = entry.getConfigDict()
            
            if dict.has_key('config'):
                del dict['config'] # HACK

            self.start(name, entry.getType(), dict, worker_name)
            
    # FIXME: move worker to second argument
    # FIXME: rename method to workerStart
    def start(self, name, type, config, worker):
        """
        @param name:
        @type name: string
        @param type:
        @type type: string
        @param config: a configuration dictionary
        @type config: dict
        @param worker: name of the worker to start the component on
        @type worker: string
        """
        
        if not self.avatars:
            raise AttributeError

        if worker:
            avatar = self.avatars[worker]
        else:
            # XXX: Do we really want to keep this big hack?
            # eg, if we don't select a worker, just pick the first one.
            avatar = self.avatars.values()[0]

        return avatar.start(name, type, config)
