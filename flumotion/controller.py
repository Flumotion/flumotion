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

        # This could use some cleaning up
        component_type, avatarID = avatarID.split('_', 1)
        
        if self.controller.hasComponent(avatarID):
            # XXX: Raise exception/deny access
            pass
        
        p = self.controller.getPerspective(component_type, avatarID)

        log.msg("returning Avatar(%s): %s" % (avatarID, p))
        if not p:
            raise ValueError, "no perspective for '%s'" % avatarID

        reactor.callLater(0, p.attached, mind)
        
        return (pb.IPerspective, p,
                lambda p=p,mind=mind: p.detached(mind))

class Options:
    pass

class ComponentPerspective(pbutil.NewCredPerspective):
    def __init__(self, controller, username):
        self.controller = controller
        self.username = username
        self.ready = False
        self.state = gst.STATE_NULL
        self.options = Options()

    def __repr__(self):
        return '<%s %s>' % (self.__class__.__name__, self.username)
    
    def getTransportPeer(self):
        return self.mind.broker.transport.getPeer()

    def getSource(self):
        return self.options.source
    
    def getRemoteControllerIP(self):
        return self.options.ip

    def getName(self):
        return self.username

    def getListenHost(self):
        return self.getTransportPeer()[1]

    # This method should ask the component if the port is free
    def getListenPort(self):
        raise NotImplementedError
    
    def after_register_cb(self, options, cb):
        if options == None:
            cb = self.mind.callRemote('register')
            cb.addCallback(self.after_register_cb, cb)
            return

        for key, value in options.items():
            setattr(self.options, key, value)
        
        self.ready = True
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


              
class ProducerPerspective(ComponentPerspective):
    kind = 'producer'
    def getListenPort(self):
        return 5500

    def listen(self, host, port):
        self.mind.callRemote('listen', host, port)
        
class ConverterPerspective(ComponentPerspective):
    kind = 'converter'
    def getListenPort(self):
        return 5501
    
    def start(self, source_host, source_port, listen_host, listen_port):
        self.mind.callRemote('start', source_host, source_port, listen_host, listen_port)

class StreamerPerspective(ComponentPerspective):
    kind = 'streamer'

    def connect(self, host, port):
        self.mind.callRemote('connect', host, port)

class Controller(pb.Root):
    def __init__(self):
        self.components = {}
        self.waitlists = {}
        
    def getPerspective(self, component_type, username):
        if component_type == 'producer':
            klass = ProducerPerspective
        elif component_type == 'converter':
            klass = ConverterPerspective
        elif component_type == 'streamer':
            klass = StreamerPerspective
        else:
            raise AssertionError
        
        component = klass(self, username)
        self.addComponent(username, component)
        return component

    def hasComponent(self, name):
        return self.components.has_key(name)
    
    def addComponent(self, name, component):
        self.components[name] = component
        
    def removeComponent(self, component):
        del self.components[component.username]

    def waitForComponent(self, name, component):
        if not self.waitlists.has_key(name):
            self.waitlists[name] = []

        self.waitlists[name].append(component)

    def startPendingComponentsFor(self, component):
        name = component.getName()
        if self.waitlists.has_key(name):
            for component in self.waitlists[name]:
                self.componentStart(component)
            self.waitlists[name] = []
    
    def getSourceComponent(self, component):
        peername = component.getSource()
        assert self.components.has_key(peername)
        return self.components[peername]

    def producerStart(self, producer):
        host = producer.getListenHost()
        port = producer.getListenPort()
        log.msg('Calling remote method listen (%s, %d)' % (host, port))
        producer.listen(host, port)

    def converterStart(self, converter):
        source = self.getSourceComponent(converter)
        source_host = source.getListenHost()
        source_port = source.getListenPort()
        listen_host = converter.getListenHost()
        listen_port = converter.getListenPort()
        log.msg('Calling remote method start (%s, %d, %s, %d)' % (source_host, source_port,
                                                                  listen_host, listen_port))
        converter.start(source_host, source_port, listen_host, listen_port)

    def streamerStart(self, streamer):
        source = self.getSourceComponent(converter)
        host = source.getListenHost()
        port = source.getListenPort()
        log.msg('Calling remote method connect')
        streamer.connect(host, port)
        
    def componentStart(self, component):
        log.msg('Starting component %r (%s)' % (component, component.kind))
        
        if isinstance(component, ProducerPerspective):
            self.producerStart(component)
        elif isinstance(component, ConverterPerspective):
            self.converterStart(component)
        elif isinstance(component, StreamerPerspective):
            self.streamerStart(component)

        # Now when the component is up and running, 
        self.startPendingComponentsFor(component)

    def componentReady(self, component):
        log.msg('%r is ready' % component)
        
        # The producer can just be started ...
        if isinstance(component, ProducerPerspective):
            self.componentStart(component)
            return

        source_name = component.getSource()
        assert not source_name is None
        
        # ... while the others need the source running
        if self.hasComponent(source_name):
            log.msg('Source for %r (%s) is ready, so starting' % (component, source_name))
            self.componentStart(component)
        else:
            log.msg('%r requires %s to be running, but its not so waiting' % (component, source_name))
            self.waitForComponent(source_name, component)
        
    def link(self, prod, conv):
        assert prod.ready
        assert conv.ready
    
        prod_port = 5500
        conv_port = 5501
        proto, prod_hostname, port = prod.getTransportPeer()
        conv_hostname = conv.getTransportPeer()[1]

        if (prod_hostname == '127.0.0.1' and conv_hostname != '127.0.0.1'):
            prod_hostname = conv.getRemoteControllerIP()
            
        def listenDone(obj=None):
            assert prod.state == gst.STATE_PLAYING, \
                   gst.element_state_get_name(prod.state)

            log.msg('calling %s.start(%d, %s, %d)' % (conv.username,
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
            log.msg('calling %s.start(%d, %s, %d)' % (conv.username,
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
