# -*- Mode: Python -*-
# vi:si:et:sw=4:sts=4:ts=4

# Flumotion - a video streaming server
# Copyright (C) 2004 Fluendo
#
# worker/worker.py: client-side objects to handle launching of components
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

import os

from twisted.cred import portal
from twisted.internet import reactor
from twisted.spread import pb

from flumotion.twisted import pbutil
from flumotion.utils import log

class Dispatcher:
    __implements__ = portal.IRealm
    def __init__(self, root):
        self.root = root
        
    def requestAvatar(self, avatarID, mind, *interfaces):
        if pb.IPerspective in interfaces:
            avatar = self.root.getAvatar(avatarID)
            reactor.callLater(0, avatar.attached, mind)
            return pb.IPerspective, avatar, avatar.shutdown
        else:
            raise NotImplementedError("no interface")

class ReportAvatar(pb.Avatar, log.Loggable):
    logCategory = 'report-avatar'
    def __init__(self, heaven, name):
        """
        @type heaven: L{flumotion.worker.report.ReportHeaven}
        @type name: string
        """
        
        self.heaven = heaven
        self.name = name
        self.mind = None
        self.debug("created new ReportAvatar")

    def hasRemoteReference(self):
        """
        Check if the avatar has a remote reference to the peer.

        @rtype: boolean
        """
        return self.mind != None

    def attached(self, mind):
        self.mind = mind
        self.log('Client attached mind %s' % mind)
        host = self.heaven.fabric.manager_host
        port = self.heaven.fabric.manager_port
        cb = self.mind.callRemote('initial', host, port)
        cb.addCallback(self.cb_afterInitial)

    def cb_afterInitial(self, unused):
        kid = self.heaven.fabric.kindergarten.getKid(self.name)
        self.mind.callRemote('start', kid.name, kid.type, kid.config)
                                          
    def shutdown(self):
        self.log('%s disconnected' % self.name)
        self.mind = None

    def stop(self):
        if not self.mind:
            return
        
        return self.mind.callRemote('stop')
        
    def remote_ready(self):
        pass

class ReportHeaven(pb.Root, log.Loggable):
    logCategory = "report-root"
    def __init__(self, fabric):
        self.avatars = {}
        self.fabric = fabric
        
    def getAvatar(self, avatarID):
        avatar = ReportAvatar(self, avatarID)
        self.avatars[avatarID] = avatar
        return avatar

    def shutdown(self):
        cb = None
        for avatar in self.avatars.values():
            new = avatar.stop()
            if cb:
                cb.chainDeferred(new)
                cb = new
        return cb
                                 
def setup(fabric):
    root = ReportHeaven(fabric)
    dispatcher = Dispatcher(root)
    checker = pbutil.ReallyAllowAnonymousAccess()
    p = portal.Portal(dispatcher, [checker])
    report_factory = pb.PBServerFactory(p)
    reactor.listenUNIX('/tmp/flumotion.%d' % os.getpid(),
                       report_factory)

    return report_factory, root
