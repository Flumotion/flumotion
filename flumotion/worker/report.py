# -*- Mode: Python -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# flumotion/worker/report.py: report status of worker
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

import os

from twisted.cred import portal
from twisted.internet import reactor
from twisted.spread import pb

from flumotion.twisted import cred
from flumotion.utils import log

class Dispatcher:
    __implements__ = portal.IRealm
    def __init__(self, root):
        self.root = root
        
    def requestAvatar(self, avatarId, mind, *interfaces):
        if pb.IPerspective in interfaces:
            avatar = self.root.createAvatar(avatarId)
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

### this is a different kind of heaven, not IHeaven, for now...
class ReportHeaven(pb.Root, log.Loggable):
    logCategory = "report-root"
    def __init__(self, fabric):
        self.avatars = {}
        self.fabric = fabric
        
    def createAvatar(self, avatarId):
        avatar = ReportAvatar(self, avatarId)
        self.avatars[avatarId] = avatar
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
    checker = cred.FlexibleCredentials()
    checker.allowAnonymous(True)
    p = portal.Portal(dispatcher, [checker])
    report_factory = pb.PBServerFactory(p)
    reactor.listenUNIX('/tmp/flumotion.%d' % os.getpid(),
                       report_factory)

    return report_factory, root
