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

from twisted.spread import pb

from flumotion.common import interfaces
from flumotion.utils import log

class WorkerAvatar(pb.Avatar, log.Loggable):
    
    __implements__ = interfaces.INewCredPerspective

    logCategory = 'worker-avatar'

    def __init__(self, avatarID):
        self.avatarID = avatarID

    def attached(self, mind):
        self.info('attached %r' % mind)
        self.mind = mind

        name = 'testing'
        type = 'videotest'
        config = dict(width=320, height=240, framerate=5.0, name=name)

        self.info('starting %s' % name)
        self.mind.callRemote('start', name, type, config)
                             
    def detached(self, mind):
        self.info('detached %r' % mind)
    
class WorkerHeaven(pb.Root):
    
    __implements__ = interfaces.IHeaven
    
    def __init__(self, vishnu):
        """
        @type vishnu: L{flumotion.manager.manager.Vishnu}
        @param vishnu: the Vishnu object
        """
        self.avatars = {}
        
    def getAvatar(self, avatarID):
        avatar = WorkerAvatar(avatarID)
        self.avatars[avatarID] = avatar
        return avatar

    def removeAvatar(self, avatarID):
        del self.avatars[avatarID]

