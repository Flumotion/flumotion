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
import time
import sys

from twisted.spread import pb
from twisted.internet import reactor

from transcoder import TranscoderFactory
from acquisition import AcquisitionFactory

class AcquisitionManager:
    def __init__(self, control):
        self.control = control
        self.objs = {}
        
    def create(self, port=8800, interface='', pipeline=''):
        factory = pb.PBServerFactory(AcquisitionFactory(pipeline))
        f = reactor.listenTCP(port, factory, 5, interface)

        if interface == '':
            interface = socket.gethostname()
        return interface, port

    def onConnect(self, object, control):
        d = object.callRemote('setController', control)
        def getRetval(object_id):
            self.objs[object_id] = object
            return object
        d.addCallback(getRetval)
        return object
        
    def connect(self, hostname, port):
        factory = pb.PBClientFactory()
        reactor.connectTCP(hostname, port, factory)

        object = factory.getRootObject()
        object.addCallback(self.onConnect, self.control)
        return object
    
class TranscoderManager:
    def __init__(self, control):
        self.control = control
        self.objs = {}
        self.hostnames = {}

    def getHostnameFor(self, obj):
        obj_id = obj.processUniqueID()
        if not self.hostnames.has_key(obj_id):
            raise KeyError, "No hostname found for object: %r" % obj

        return self.hostnames[obj_id]
    
    def create(self, port=8800, interface=''):
        factory = pb.PBServerFactory(TranscoderFactory())
        f = reactor.listenTCP(port, factory, 5, interface)
        if interface == '':
            interface = socket.gethostname()
            
        return interface, port

    def connect(self, hostname, port):
        factory = pb.PBClientFactory()
        reactor.connectTCP(hostname, port, factory)
        
        object = factory.getRootObject()
        def onConnect(obj, control):
            self.hostnames[obj.processUniqueID()] = hostname
            d = obj.callRemote('setController', control)
            return obj
        object.addCallback(onConnect, self.control)
        return object
    
class ControllerFactory(pb.Referenceable):
    def __init__(self):
        self.linked_objs = {}
        self.hostnames = {}
        self.ports = {}
        self.acq_mgr = AcquisitionManager(self)
        self.trans_mgr = TranscoderManager(self)
        
    def createAcquisition(self, port=8800, interface='', pipeline=''):
        return self.acq_mgr.create(port, interface, pipeline)
        
    def createTranscoder(self, port=8800, interface=''):
        return self.trans_mgr.create(port, interface)

    def connectAcquisition(self, hostname, port):
        return self.acq_mgr.connect(hostname, port)

    def connectTranscoder(self, hostname, port):
        return self.trans_mgr.connect(hostname, port)

    def transGetInfo(self, port, obj):
        self.ports[obj.processUniqueID()] = port
        return obj

    def getLinkedObject(self, object):
        object_id = object.processUniqueID()
        if not self.linked_objs.has_key(object_id):
            raise KeyError, "%r is not linked to an object yet" % object

        other = self.linked_objs[object_id]
        return other

    def addLinkedObjects(self, object, other):
        if not hasattr(other, 'result'):
            return

        other = other.result
        
        self.linked_objs[object.processUniqueID()] = other
        self.linked_objs[other.processUniqueID()] = object
        
    def link(self, acq, trans, port):
        def onAcqConnect(object, other):
            self.addLinkedObjects(object, other)
            object.callRemote('start')
            return object

        acq.addCallback(onAcqConnect, trans)
        
        def onTransConnect(object, other):
            print 'Transcoder connected'
            self.addLinkedObjects(object, other)
            object.callRemote('start', port)
            retval = object.callRemote('getInfo')
            retval.addCallback(self.transGetInfo, object)
            return object

        trans.addCallback(onTransConnect, acq)

    def remote_acqFinished(self, acq):
        print 'Controller.remote_acquisitionFinished', acq

    def remote_acqNotifyCaps(self, acq_id, caps):
        print 'Controller.acqNotifyCaps', caps
        acq = self.acq_mgr.objs[acq_id]
        transcoder = self.getLinkedObject(acq)
        retval = transcoder.callRemote('setCaps', caps)
        
        def whenCapsIsSet(obj, acq):
            print 'Transcoders caps is set, calling up to acq'
            obj_id = transcoder.processUniqueID()
            hostname = self.trans_mgr.getHostnameFor(transcoder)
            port = self.ports[obj_id]
            acq.callRemote('assignRealSink', hostname, port)
            return acq
        
        retval.addCallback(whenCapsIsSet, acq)

    def remote_transStarted(self, trans):
        print 'Controller.remote_transStarted', trans
        
if __name__ == '__main__':
    controller = ControllerFactory()
    start_acq = False
    start_trans = False

    if start_acq:
        pipeline = 'videotestsrc'
        hostname, port = controller.createAcquisition(8802, pipeline=pipeline)

    if start_trans:
        hostname, port = controller.createTranscoder(8803)
        
    hostname, port = sys.argv[1].split(':')
    acq = controller.connectAcquisition(hostname, int(port))
    
    hostname, port = sys.argv[2].split(':')
    trans = controller.connectTranscoder(hostname, int(port))

    controller.link(acq, trans, 5500)
    
    reactor.run()
