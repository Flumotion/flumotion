# -*- Mode: Python -*-
# vi:si:et:sw=4:sts=4:ts=4

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
# Foundation, Inc., 59 Temple Street #330, Boston, MA 02111-1307, USA.

from twisted.internet import reactor
from twisted.spread import pb

from flumotion.twisted import pbutil
from flumotion.utils import log

class ComponentView(pb.Copyable):
    def __init__(self, component):
        self.name = component.getName()
        # forced to int so it's jellyable
        self.state = int(component.state)
        self.sources = component.getSources()
        self.feeds = component.getFeeds()
        self.options = component.options.dict

class RemoteComponentView(pb.RemoteCopy):
    def __cmp__(self, other):
        if not isinstance(other, RemoteComponentView):
            return False
        return cmp(self.name, other.name)
    
    def __repr__(self):
        return '<RemoteComponentView %s>' % self.name
pb.setUnjellyableForClass(ComponentView, RemoteComponentView)

class AdminPerspective(pbutil.NewCredPerspective):
    def __init__(self, controller):
        self.controller = controller
        self.mind = None
        
    debug = lambda s, *a: log.debug('admin', *a)
    warning = lambda s, *a: log.warning('admin', *a)

    def hasPerspective(self):
        return self.mind != None
    
    def callRemote(self, name, *args, **kwargs):
        if not self.hasPerspective():
            #self.warning("Can't call remote method %s, no perspective" % name)
            return
        
        #self.debug('Calling remote method %s%r' % (name, args))
        try:
            return self.mind.callRemote(name, *args, **kwargs)
        except pb.DeadReferenceError:
            self.mind = None
            return
        
    def getClients(self):
        clients = map(ComponentView, self.controller.components.values())
        print "clients:"
        print clients
        return clients

    def sendLog(self, category, type, message):
        self.callRemote('log', category, type, message)
        
    def componentAdded(self, component):
        self.callRemote('componentAdded', ComponentView(component))
        
    def componentRemoved(self, component):
        self.callRemote('componentRemoved', ComponentView(component))

    def attached(self, mind):
        self.mind = mind
        ip = self.mind.broker.transport.getPeer()[1]
        self.debug('Client from %s attached' % ip)

        self.callRemote('initial', self.getClients())

    def detached(self, mind):
        ip = self.mind.broker.transport.getPeer()[1]
        self.debug('Client from %s detached' % ip)
        
        self.callRemote('shutdown')

    def perspective_shutdown(self):
        print 'SHUTTING DOWN'
        reactor.stop()
        raise SystemExit
    
    def perspective_setState(self, component_name, element, property, value):
        component = self.controller.getComponent(component_name)
        try:
            component.setState(element, property, value)
        except TypeError, e:
            print 'ERROR: %s' % str(e)

    def perspective_getState(self, component_name, element, property):
        component = self.controller.getComponent(component_name)
        return component.getState(element, property)

class Admin(pb.Root):
    def __init__(self, controller):
        self.controller = controller
        self.clients = []
        log.addLogHandler(self.logHandler)
        self.logcache = []

    debug = lambda s, *a: log.debug('admin', *a)
        
    def logHandler(self, category, type, message):
        self.logcache.append((category, type, message))
        for client in self.clients:
            client.sendLog(category, type, message)

    def sendCache(self, client):
        if not client.hasPerspective():
            reactor.callLater(0.25, self.sendCache, client)
            return
        
        self.debug('sending logcache to client (%d messages)' % len(self.logcache))
        for category, type, message in self.logcache:
            client.sendLog(category, type, message)
        
    def getPerspective(self):
        self.debug('creating new perspective')
        admin = AdminPerspective(self.controller)
        reactor.callLater(0.25, self.sendCache, admin)
        
        self.clients.append(admin)
        return admin
    
    def componentAdded(self, component):
        for client in self.clients:
            client.componentAdded(component)

    def componentRemoved(self, component):
        for client in self.clients:
            client.componentRemoved(component)

        
