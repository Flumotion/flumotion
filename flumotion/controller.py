# -*- Mode: Python -*-
# Flumotion - a video streaming server
# Copyright (C) 2004 Fluendo
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
# Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
#

import sys
    
import gobject
import gst

if __name__ == '__main__':
    import gstreactor
    gstreactor.install()

from twisted.application import service, internet
from twisted.cred import portal, checkers, credentials
from twisted.internet import reactor
from twisted.python import log
from twisted.spread import pb

import pbutil

class Dispatcher:
    __implements__ = portal.IRealm
    def __init__(self, controller):
        self.controller = controller

    def requestAvatar(self, avatarID, mind, interface):
        assert interface == pb.IPerspective
        
        log.msg('requestAvatar (%s, %s, %s)' % (avatarID, mind, interface))

        # if self.controller.hasComponent(avatarID) ...
        
        p = self.controller.getPerspective(avatarID)

        log.msg("returning Avatar(%s): %s" % (avatarID, p))
        if not p:
            raise ValueError, "no perspective for '%s'" % avatarID
        
        p.attached(mind) # perhaps .callLater(0) ?
        
        return (pb.IPerspective, p,
                lambda p=p,mind=mind: p.detached(mind))

class AcquisitionPerspective(pbutil.NewCredPerspective):
    def __init__(self, controller, username):
        self.controller = controller
        self.username = username
        self.caps = None
        
    def __repr__(self):
        return '<AcquisitionPerspective for %s>' % self.username
    
    def getPeer(self):
        return self.mind.broker.transport.getPeer()

    def getCaps(self):
        return self.caps
    
    def attached(self, mind):
        log.msg('%s attached, preparing' % self.username)
        mind.callRemote('prepare')
        self.mind = mind
        
    def detached(self, mind):
        log.msg('%r detached' % mind)
        self.controller.removeComponent(self)

    def perspective_stateChanged(self, old, state):
        log.msg('%s.stateChanged %s -> %s' %
                (self.username,
                 gst.element_state_get_name(old),
                 gst.element_state_get_name(state)))

    def perspective_notifyCaps(self, caps):
        log.msg('%s.notifyCaps %s' % (self.username, caps))
        self.caps = caps
        self.controller.componentReady(self)
        
    def perspective_error(self, element, error):
        log.msg('%s.error element=%s string=%s' % (self.username, element, error))

class TranscoderPerspective(pbutil.NewCredPerspective):
    def __init__(self, controller, username):
        self.controller = controller
        self.username = username
        
    def __repr__(self):
        return '<TranscoderPerspective for %s>' % self.username

    def getPeer(self):
        return self.mind.broker.transport.getPeer()

    def attached(self, mind):
        log.msg('%s attached, preparing' % self.username)
        defer = mind.callRemote('prepare')
        defer.addCallback(self.prepareDone)
        self.mind = mind
        
    def detached(self, mind):
        log.msg('%r detached' % mind)
        self.controller.removeComponent(self)
        
    def prepareDone(self, *args):
        self.controller.componentReady(self)

    def perspective_stateChanged(self, old, state):
        log.msg('%s.stateChanged %s -> %s' %
                (self.username,
                 gst.element_state_get_name(old),
                 gst.element_state_get_name(state)))

    def perspective_error(self, element, error):
        log.msg('%s.error element=%s string=%s' % (self.username, element, error))
        
class Controller(pb.Root):
    def __init__(self):
        self.components = {}

    def getPerspective(self, username):
        if username.startswith('acq_'):
            component = AcquisitionPerspective(self, username)
        elif username.startswith('trans_'):
            component = TranscoderPerspective(self, username)

        self.addComponent(username, component)

        return component

    def addComponent(self, name, component):
        self.components[name] = component
        
    def removeComponent(self, component):
        del self.components[component.username]
    
    def componentReady(self, component):
        link = ['acq_johan', 'trans_johan']
        component.ready = True
        
        log.msg('%r is ready' % component)
        for component in self.components.values():
            if component.ready == False:
                break
        else:
            item = link[0]
            if not self.components.has_key(item):
                log.msg('%s is not yet connected' % item) 
                return
            
            prev = self.components[link[0]]
            for item in link[1:]:
                if not self.components.has_key(item):
                    log.msg('%s is not yet connected' % item) 
                    return
                curr = self.components[item]
                
                log.msg('going to connect %s with %s' % (prev, curr))
                self.link(prev, curr)
                prev = curr

    def link(self, acq, trans):
        obj = trans.mind.callRemote('listen', 5500, acq.getCaps())
        proto, hostname, port = trans.getPeer()
        def listenDone(obj):
            acq.mind.callRemote('connect', hostname, 5500)
        obj.addCallback(listenDone)
            
class ControllerMaster(pb.PBServerFactory):
    def __init__(self):
        controller = Controller()
        disp = Dispatcher(controller)
        checker = pbutil.ReallyAllowAnonymousAccess()
        
        port = portal.Portal(disp, [checker])
        pb.PBServerFactory.__init__(self, port)

    def __repr__(self):
        return '<ControllerMaster>'
    
    def clientConnectionMade(self, broker):
        log.msg('Broker connected: %r' % broker)
        
log.startLogging(sys.stdout)
reactor.listenTCP(8890, ControllerMaster())
reactor.run()
