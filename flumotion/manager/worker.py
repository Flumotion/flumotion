# -*- Mode: Python -*-
# vi:si:et:sw=4:sts=4:ts=4

# Flumotion - a video streaming server
# Copyright (C) 2004 Fluendo
#
# manager/worker.py: manager-side objects to handle workers
# 
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
# 
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Street #330, Boston, MA 02111-1307, USA.

"""
Manager-side objects to handle worker clients.
"""

from twisted.spread import pb

from flumotion.common import interfaces
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

    def __init__(self, heaven, avatarID):
        self.heaven = heaven
        self.avatarID = avatarID

    def getName(self):
        return self.avatarID
    
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
        self.info('starting %s' % name)
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
        self.avatars = {}
        self.conf = None
        
    def getAvatar(self, avatarID):
        avatar = WorkerAvatar(self, avatarID)
        self.avatars[avatarID] = avatar
        return avatar

    def removeAvatar(self, avatarID):
        del self.avatars[avatarID]

    def loadConfiguration(self, filename):
        # XXX: Merge?
        self.conf = FlumotionConfigXML(filename)

    def getEntries(self, worker):
        retval = []
        if not self.conf:
            return retval
        
        for entry in self.conf.entries.values():
            entry_worker = entry.getWorker()
            if entry_worker and entry_worker != worker.getName():
                continue
            retval.append(entry)
        return retval
    
    def workerAttached(self, worker):
        entries = self.getEntries(worker)
        for entry in entries:
            name = entry.getName()
            log.debug('config', 'Starting component: %s' % name)
            dict = entry.getConfigDict()
            
            if dict.has_key('config'):
                del dict['config'] # HACK

            worker.start(name, entry.getType(), dict)
            
    def start(self, name, type, config, worker=None):
        if not self.avatars:
            raise AttributeError

        if worker:
            avatar = self.avatars[worker]
        else:
            # XXX: Do we really want to keep this big hack?
            # eg, if we don't select a worker, just pick the first one.
            avatar = self.avatars.values()[0]

        return avatar.start(name, type, config)
