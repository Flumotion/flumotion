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

import socket
import sys
    
import pygtk
pygtk.require('2.0')

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

class ComponentPerspecetive(pbutil.NewCredPerspective):
    def __init__(self, controller, username):
        self.controller = controller
        self.username = username
        self.ready = False
        self.state = gst.STATE_NULL
        self.remote_host = None

    def getPeer(self):
        return self.mind.broker.transport.getPeer()

    # XXX: Rename
    def getControllerHostname(self):
        return self.remote_host
    
    def after_register_cb(self, host, cb):
        if host == None:
            cb = self.mind.callRemote('register')
            cb.addCallback(self.after_register_cb, cb)
            return
        self.remote_host = host
        
        self.controller.componentReady(self)
        
    def attached(self, mind):
        log.msg('%s attached, registering' % self.username)
        self.mind = mind
        
        cb = mind.callRemote('register')
        cb.addCallback(self.after_register_cb, cb)
        
    def detached(self, mind):
        log.msg('%r detached' % mind)
        self.controller.removeComponent(self)

    def perspective_stateChanged(self, old, state):
        log.msg('%s.stateChanged %s -> %s' %
                (self.username,
                 gst.element_state_get_name(old),
                 gst.element_state_get_name(state)))
        self.state = state
        
    def perspective_error(self, element, error):
        log.msg('%s.error element=%s string=%s' % (self.username, element, error))
        
        self.ready = False
        cb = self.mind.callRemote('register')
        cb.addCallback(self.after_register_cb)

class Controller(pb.Root):
    def __init__(self):
        self.components = {}
        
    def getPerspective(self, username):
        component = ComponentPerspective(self, username)
        self.addComponent(username, component)
        return component

    def addComponent(self, name, component):
        self.components[name] = component
        
    def removeComponent(self, component):
        del self.components[component.username]
    
    def componentReady(self, component):
        link = ['prod_johan', 'conv_johan']
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

    def link(self, prod, conv):
        assert prod.ready
        assert conv.ready
        
        prod_port = 5500
        conv_port = 5501
        proto, prod_hostname, port = prod.getPeer()
        conv_hostname = conv.getPeer()[1]

        if (prod_hostname == '127.0.0.1' and conv_hostname != '127.0.0.1'):
            prod_hostname = conv.getControllerHostname()
            
        def listenDone(obj=None):
            assert prod.state == gst.STATE_PLAYING, \
                   gst.element_state_get_name(prod.state)

            log.msg('calling %s.listen(%d, %s, %d)' % (conv.username,
                                                       prod_port,
                                                       prod_hostname,
                                                       conv_port))
            conv.mind.callRemote('start', prod_port, prod_hostname, conv_port)

        if prod.state != gst.STATE_PLAYING:
            log.msg('calling %s.listen(%s, %d)' % (prod.username,
                                                   prod_hostname,
                                                   prod_port))
            obj = prod.mind.callRemote('listen', prod_hostname, prod_port)
            obj.addCallback(listenDone)
        else:
            log.msg('calling %s.listen(%d, %s, %d)' % (conv.username,
                                                       prod_port,
                                                       prod_hostname,
                                                       conv_port))
            conv.mind.callRemote('start', prod_port, prod_hostname, conv_port)
            
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
