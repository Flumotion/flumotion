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
# Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.

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
from twisted.internet import reactor, error
from twisted.manhole import telnet
from twisted.spread import pb

import pbutil
import log
import twistedutils

def msg(*args):
    log.msg('controller', *args)

class Dispatcher:
    __implements__ = portal.IRealm
    def __init__(self, controller):
        self.controller = controller

    def requestAvatar(self, avatarID, mind, interface):
        assert interface == pb.IPerspective
        
        #msg('requestAvatar (%s, %s, %s)' % (avatarID, mind, interface))

        # This could use some cleaning up
        component_type, avatarID = avatarID.split('_', 1)
        
        if self.controller.hasComponent(avatarID):
            # XXX: Raise exception/deny access
            return
        
        p = self.controller.getPerspective(component_type, avatarID)

        #msg("returning Avatar(%s): %s" % (avatarID, p))
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
        self.state = gst.STATE_NULL
        self.options = Options()
        self.listen_port = -1
        self.started = False
        
    def __repr__(self):
        return '<%s %s in state %s>' % (self.__class__.__name__,
                                        self.getName(),
                                        gst.element_state_get_name(self.state))
    
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

        self.controller.componentRegistered(self)
            
    def attached(self, mind):
        #msg('%s attached, calling register()' % self.getName())
        self.mind = mind
        
        cb = mind.callRemote('register')
        cb.addCallback(self.after_register_cb, cb)
        
    def detached(self, mind):
        name = self.getName()
        msg('%s detached' % name)
        if self.controller.hasComponent(name):
            self.controller.removeComponent(self)

    def perspective_stateChanged(self, old, state):
        #msg('%s.stateChanged %s' % (self.getName(),
        #                            gst.element_state_get_name(state)))
        
        self.state = state
        if self.state == gst.STATE_PLAYING:
            msg('%s is now playing' % self.getName())
            self.started = True
            self.controller.startPendingComponents(self)
            
    def perspective_error(self, element, error):
        msg('%s.error element=%s string=%s' % (self.getName(), element, error))
        
        self.controller.removeComponent(self)

class ProducerPerspective(ComponentPerspective):
    """Perspective for producer components"""
    kind = 'producer'
    def listen(self, host, port=None):
        """starts the remote methods listen"""
        if port == None:
            def after_get_free_port_cb(port):
                self.listen_port = port
                msg('Calling remote method listen (%s, %d)' % (host, port))
                self.mind.callRemote('listen', host, port)

            msg('Calling remote method get_free_port()')
            cb = self.mind.callRemote('get_free_port')
            cb.addCallback(after_get_free_port_cb)
        else:
            self.listen_port = port
            msg('Calling remote method listen (%s, %d)' % (host, port))
            self.mind.callRemote('listen', host, port)
            
class ConverterPerspective(ComponentPerspective):
    """Perspective for converter components"""
    kind = 'converter'
    def start(self, sources, host, port=None):
        """starts the remote methods start"""
        
        if port == None:
            def after_get_free_port_cb(port):
                self.listen_port = port
                msg('Calling remote method start (%s, %s, %d)' % (sources, host, port))
                self.mind.callRemote('start', sources,  host, port)

            msg('Calling remote method get_free_port()')
            cb = self.mind.callRemote('get_free_port')
            cb.addCallback(after_get_free_port_cb)
        else:
            self.listen_port = port
            msg('Calling remote method start (%s, %s, %d)' % (sources, host, port))
            self.mind.callRemote('start', sources,  host, port)
            
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
        msg('Calling remote method connect(%s)' % sources)
        self.mind.callRemote('connect', sources)

class Controller(pb.Root):
    def __init__(self):
        self.components = {}
        self.deps = {}
        self.last_free_port = 5500
        
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

    def isLocalComponent(self, component):
        # TODO: This could be a lot smarter
        if component.getListenHost() == '127.0.0.1':
            return True
        else:
            return False

    def getFreePort(self):
        start = self.last_free_port
        fd = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        while 1:
            try:
                fd.bind(('', start))
            except socket.error:
                start += 1
                continue
            break
        
        self.last_free_port = start + 1
        
        return start
        
    def getComponent(self, name):
        """retrieves a new component
        @type name:  string
        @param name: name of the component
        @rtype:      component
        @returns:    the component"""

        if not self.hasComponent(name):
            raise KeyError, name
        
        return self.components[name]
    
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
        if self.hasComponent(component_name):
            raise KeyError, component_name
            
        self.components[component_name] = component

    def removeComponent(self, component):
        """removes a component
        @type component: component
        @param component: the component"""

        component_name = component.getName()
        if not self.hasComponent(component_name):
            raise KeyError, component_name

        del self.components[component_name]

    def isComponentStarted(self, component_name):
        if not self.hasComponent(component_name):
            return False

        component = self.components[component_name]

        return component.started == True
    
    def getSourceComponents(self, component):
        """Retrives the source components for component

        @type component:  component
        @param component: the component
        @rtype:           tuple of with 3 items
        @returns:         name, hostname and port"""

        assert not isinstance(component, ProducerPerspective)

        peernames = component.getSources()
        retval = []
        for peername in peernames:
            assert self.components.has_key(peername), peername
            source = self.components[peername]
            retval.append((source.getName(),
                           source.getListenHost(),
                           source.getListenPort()))
        return retval

    def producerStart(self, producer):
        assert isinstance(producer, ProducerPerspective)
        
        host = producer.getListenHost()
        if self.isLocalComponent(producer):
            producer.listen(host, self.getFreePort())
        else:
            producer.listen(host)

    def converterStart(self, converter):
        assert isinstance(converter, ConverterPerspective)
        
        sources = self.getSourceComponents(converter)
        host = converter.getListenHost()
            
        if self.isLocalComponent(converter):
            converter.start(sources, host, self.getFreePort())
        else:
            converter.start(sources, host)
            
    def streamerStart(self, streamer):
        assert isinstance(streamer, StreamerPerspective)
        
        sources = self.getSourceComponents(streamer)
        streamer.connect(sources)
        
    def componentStart(self, component):
        msg('Starting component %s of type %s' % (component.getName(), component.kind))
        assert isinstance(component, ComponentPerspective)
        assert component != ComponentPerspective

        if isinstance(component, ProducerPerspective):
            self.producerStart(component)
        elif isinstance(component, ConverterPerspective):
            self.converterStart(component)
        elif isinstance(component, StreamerPerspective):
            self.streamerStart(component)

    def componentRegistered(self, component):
        msg('%s is registered' % component.getName())

        sources = component.getSources()
        if not sources:
            self.componentStart(component)
            return

        can_start = True
        name = component.getName()
        for source in sources:
            if self.isComponentStarted(source):
                #msg('%s is already started' % source)
                continue

            can_start = False
            msg('%s will wait for %s' % (name, source))
                    
            if not self.deps.has_key(source):
                self.deps[source] = []
                
            self.deps[source].append(name)

        if can_start:
            self.componentStart(component)
            
    def startPendingComponents(self, component):
        component_name = component.getName()
        if self.deps.has_key(component_name):
            msg('starting pending components for %s' % component_name)
            comps = self.deps[component_name]
            for name in comps[:]:
                child = self.components[name]
                for source in child.getSources():
                    if not self.isComponentStarted(source):
                        return
                    
                self.componentStart(child)
            return

        for component_name in self.components:
            if not self.isComponentStarted(component_name):
                return

        msg('Server started up correctly')
            
class ControllerServerFactory(pb.PBServerFactory):
    """A Server Factory with a Dispatcher and a Portal"""
    def __init__(self):
        self.controller = Controller()
        self.dispatcher = Dispatcher(self.controller)
        checker = pbutil.ReallyAllowAnonymousAccess()
        
        self.portal = portal.Portal(self.dispatcher, [checker])
        pb.PBServerFactory.__init__(self, self.portal)

    def __repr__(self):
        return '<ControllerServerFactory>'

if __name__ == '__main__':
    controller = ControllerServerFactory()

    ts = telnet.ShellFactory()
    ts.namespace.update(controller.controller.__dict__)
    ts.namespace['dispatcher'] = controller.dispatcher
    ts.namespace['portal'] = controller.portal

    ts.protocol = twistedutils.Shell
    try:
        reactor.listenTCP(8890, controller)
        reactor.listenTCP(4040, ts)
    except error.CannotListenError, e:
        print 'ERROR:', e
        raise SystemExit

    
    reactor.run(False)
