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

import atexit
import os
import socket

from twisted.spread import pb
from twisted.internet import reactor

from transcoder import TranscoderFactory
from acquisition import AcquisitionFactory

class AcquisitionManager:
    def __init__(self, control):
        self.control = control
        
    def create(self, port=8800, interface=''):
        pid = os.fork()
        if not pid:
            factory = pb.PBServerFactory(AcquisitionFactory())
            f = reactor.listenTCP(port, factory, 5, interface)
            reactor.run()
            raise SystemExit

        atexit.register(os.kill, pid, 9)
        if interface == '':
            interface = socket.gethostname()
            
        return (interface, port)
    
    def connect(self, hostname, port, filename):
        factory = pb.PBClientFactory()
        reactor.connectTCP(hostname, port, factory)

        def whenConnected(object):
            object.callRemote('setController', self.control)
            object.callRemote('startFileSink', filename)
            return object
        
        object = factory.getRootObject()
        object.addCallback(whenConnected)

class TranscoderManager:
    def __init__(self, control):
        self.control = control

    def create(self, port=8800, interface=''):
        pid = os.fork()
        if not pid:
            factory = pb.PBServerFactory(TranscoderFactory())
            f = reactor.listenTCP(port, factory, 5, interface)
            reactor.run()
            raise SystemExit

        atexit.register(os.kill, pid, 9)
        if interface == '':
            interface = socket.gethostname()
            
        return interface, port

    def connect(self, hostname, port, filename):
        factory = pb.PBClientFactory()
        reactor.connectTCP(hostname, port, factory)

        def whenConnected(object):
            object.callRemote('setController', self.control)
            object.callRemote('startFileSrc', filename)
            return object
        
        self.transcoder = factory.getRootObject()
        self.transcoder.addCallback(whenConnected)

class ControllerFactory(pb.Referenceable):
    def __init__(self):
        self.acq_mgr = AcquisitionManager(self)
        self.trans_mgr = TranscoderManager(self)
        
    def createAcquisition(self, port=8800, interface=''):
        return self.acq_mgr.create(port, interface)
        
    def createTranscoder(self, port=8800, interface=''):
        return self.trans_mgr.create(port, interface)

    def connectAcquisition(self, hostname, port, filename):
        self.acq_mgr.connect(hostname, port, filename)

    def connectTranscoder(self, hostname, port, filename):
        self.trans_mgr.connect(hostname, port, filename)
        
    def remote_acqStarted(self, acq):
        print 'Controller.remote_acqStarted', acq
        
    def remote_acqFinished(self, acq):
        print 'Controller.remote_acquisitionFinished', acq

    def remote_acqNotifyCaps(self, acq, caps):
        print 'Controller.remote_acqNotifyCaps', caps
        
        # XXX: Un-tie
        transcoder = self.trans_mgr.transcoder
        transcoder.addCallback(lambda obj: obj.callRemote('setCaps', caps))

    def remote_transStarted(self, trans):
        print 'Controller.remote_transStarted', trans
        
if __name__ == '__main__':
    controller = ControllerFactory()

    filename = '/tmp/foo'
    if os.path.exists(filename):
        os.unlink(filename)
    os.mkfifo(filename, 0600)

    hostname, port = controller.createAcquisition(8803)
    controller.connectAcquisition(hostname, port, filename)
    
    hostname, port = controller.createTranscoder(8804)
    controller.connectTranscoder(hostname, port, filename)
    
    reactor.run()
