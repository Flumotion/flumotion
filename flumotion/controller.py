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
    """dummy class for storing controller side options of a component"""

class ComponentPerspective(pbutil.NewCredPerspective):
    """Perspective all components will have on the controller side"""
    def __init__(self, controller, username):
        self.controller = controller
        self.username = username
        self.ready = False
        self.state = gst.STATE_NULL
        self.options = Options()
        self.listen_port = -1

    def __repr__(self):
        return '<%s %s>' % (self.__class__.__name__, self.username)
    
    def getTransportPeer(self):
        return self.mind.broker.transport.getPeer()

    def getSources(self):
        return self.options.sources
    
    def getRemoteControllerIP(self):
        return self.options.ip

    def getName(self):
        return self.username

    def getListenHost(self):
        return self.getTransportPeer()[1]

    # This method should ask the component if the port is free
    def getListenPort(self):
        assert self.listen_port != -1
        return self.listen_port

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
        log.msg('%s.stateChanged %s' %
                (self.username,
                 gst.element_state_get_name(state)))
        self.state = state
        
    def perspective_error(self, element, error):
        log.msg('%s.error element=%s string=%s' % (self.username, element, error))
        
        self.ready = False
        cb = self.mind.callRemote('register')
        cb.addCallback(self.after_register_cb, cb)
              
class ProducerPerspective(ComponentPerspective):
    """Perspective for producer components"""
    kind = 'producer'
    def listen(self, host):
        """starts the remote methods listen"""
        def after_get_free_port_cb(port):
            self.listen_port = port
            self.mind.callRemote('listen', host, port)
            
        log.msg('Calling remote method get_free_port()')
        cb = self.mind.callRemote('get_free_port')
        cb.addCallback(after_get_free_port_cb)
 
    def getSources(self):
        "Should never be called, a Producer does not have any sources"
        raise AssertionError
       
class ConverterPerspective(ComponentPerspective):
    """Perspective for converter components"""
    kind = 'converter'
    def start(self, sources, listen_host):
        """starts the remote methods start"""
        def after_get_free_port_cb(listen_port):
            self.listen_port = listen_port
            log.msg('Calling remote method start (%s, %s, %d)' % (sources,
                                                                  listen_host, listen_port))
            self.mind.callRemote('start', sources,  listen_host, listen_port)

        log.msg('Calling remote method get_free_port()')
        cb = self.mind.callRemote('get_free_port')
        cb.addCallback(after_get_free_port_cb)

class StreamerPerspective(ComponentPerspective):
    """Perspective for streamer components"""
    kind = 'streamer'
    def getListenHost(self):
        "Should never be called, a Streamer does not accept incoming components"
        raise AssertionError
    
    def getListenPort(self):
        "Should never be called, a Streamer does not accept incoming components"
        raise AssertionError

    def connect(self, sources):
        """starts the remote methods connect"""
        self.mind.callRemote('connect', sources)

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
        self.addComponent(component)
        return component

    def hasComponent(self, name):
        """adds a new component
        @type name:  string
        @param name: name of the component
        @rtype:      boolean
        @returns:    True if a component with that name is registered, otherwise False"""
        
        return self.components.has_key(name)
    
    def addComponent(self, component):
        """adds a component
        @type component: component
        @param component: the component"""

        component_name = component.getName()
        self.components[component_name] = component
        
    def removeComponent(self, component):
        """removes a component
        @type component: component
        @param component: the component"""

        component_name = component.getName()
        del self.components[component_name]

    def waitForComponent(self, name, component):
        """adds a component to another components waitlist. Eg wait until
        the other component has started up before starting it
        
        @type name:      string
        @param name:     name of the other component
        @type component: component
        @param component: the component"""
        
        if not self.waitlists.has_key(name):
            self.waitlists[name] = []

        self.waitlists[name].append(component)

    def startPendingComponentsFor(self, component):
        """Starts all components that requires L{Component} to be started
        @type component: component
        @param component: the component"""
        
        name = component.getName()
        if self.waitlists.has_key(name):
            for component in self.waitlists[name]:
                self.componentStart(component)
            self.waitlists[name] = []
    
    def getSourceComponents(self, component):
        """Retrives the source components for component

        @type component:  component
        @param component: the component
        @rtype:           list of string
        @returns:         name of source components"""

        assert not isinstance(component, ProducerPerspective)
        
        peernames = component.getSources()
        retval = []
        for peername in peernames:
            assert self.components.has_key(peername)
            source = self.components[peername]
            retval.append((source.getName(),
                           source.getListenHost(),
                           source.getListenPort()))
        return retval

    def producerStart(self, producer):
        assert isinstance(producer, ProducerPerspective)
        
        host = producer.getListenHost()
        log.msg('Calling remote method listen (%s)' % host)
        producer.listen(host)

    def converterStart(self, converter):
        #assert isinstance(converter, ConverterPerspective)
        
        sources = self.getSourceComponents(converter)
        listen_host = converter.getListenHost()
            
        converter.start(sources, listen_host)
        
    def streamerStart(self, streamer):
        #assert isinstance(streamer, StreamerPerspective)
        
        sources = self.getSourceComponents(streamer)
        log.msg('Calling remote method connect')
        streamer.connect(sources)
        
    def componentStart(self, component):
        log.msg('Starting component %r of type %s' % (component, component.kind))
        
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
        
        # A producer can just be started ...
        if isinstance(component, ProducerPerspective):
            self.componentStart(component)
            return

        source_names = component.getSources()
        assert source_names != []

        sources_ready = True
        for source_name in source_names:
            if self.hasComponent(source_name):
                continue
            
            log.msg("%r will be waiting for source %s" % (component, source_name))
            self.waitForComponent(source_name, component)
            sources_ready = False

        if sources_ready:
            log.msg('All sources for %r (%s) are ready, so starting' % (component, source_names))
            self.componentStart(component)
            
class ControllerServerFactory(pb.PBServerFactory):
    """A Server Factory with a Dispatcher and a Portal"""
    def __init__(self):
        controller = Controller()
        disp = Dispatcher(controller)
        checker = pbutil.ReallyAllowAnonymousAccess()
        
        port = portal.Portal(disp, [checker])
        pb.PBServerFactory.__init__(self, port)

    def __repr__(self):
        return '<ControllerServerFactory>'
    
if __name__ == '__main__':
    log.startLogging(sys.stdout)
    reactor.listenTCP(8890, ControllerServerFactory())
    reactor.run()
