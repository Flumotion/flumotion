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
import sys

from twisted.internet import protocol, reactor
from twisted.spread import pb

from flumotion.common import interfaces
from flumotion.twisted import pbutil
from flumotion.utils import log
from flumotion.worker import launcher, report

class WorkerFactory(pbutil.ReconnectingPBClientFactory):
    __super_login = pbutil.ReconnectingPBClientFactory.startLogin
    def __init__(self, parent):
        self.view = parent.worker_view
        # doing this as a class method triggers a doc error
        pbutil.ReconnectingPBClientFactory.__init__(self)
        
    def login(self, username):
        self.__super_login(pbutil.Username(username),
                           self.view,
                           interfaces.IWorkerComponent)
        
    def gotPerspective(self, perspective):
        self.view.cb_gotPerspective(perspective)

class WorkerView(pb.Referenceable, log.Loggable):
    logCategory = 'worker-view'
    def __init__(self, fabric):
        self.fabric = fabric
        
    def cb_gotPerspective(self, perspective):
        self.info('got perspective: %s' % perspective)

    def cb_processFinished(self, *args):
        self.info('processFinished %r' % args)

    def cb_processFailed(self, *args):
        self.info('processFailed %r' % args)

    def remote_start(self, name, type, config):
        self.info('start called')
        self.fabric.kindergarten.play(name, type, config)
        
class Kid:
    def __init__(self, protocol, name, type, config):
        self.protocol = protocol 
        self.name = name
        self.type = type
        self.config = config

    # pid = protocol.transport.pid
    
class Kindergarten:
    def __init__(self):
        dirname = os.path.split(os.path.abspath(sys.argv[0]))[0]
        self.program = os.path.join(dirname, 'flumotion-worker')
        self.extra = {}
        
    def play(self, name, type, config):
        args = [self.program, name, '/tmp/flumotion.%d' % os.getpid()]

        p = reactor.spawnProcess(protocol.ProcessProtocol(),
                                 self.program, args,
                                 env=os.environ,
                                 childFDs={ 0: 0, 1: 1, 2: 2})
        self.extra[name] = Kid(p, name, type, config)

        return p
    
    def getExtra(self, name):
        return self.extra[name]

# Similar to Vishnu, but for worker related classes
class WorkerFabric:
    def __init__(self, host, port):
        self.manager_host = host
        self.manager_port = port
        
        self.kindergarten = Kindergarten()
        self.report_factory = report.setup(self)

        self.worker_view = WorkerView(self)
        self.worker_factory = WorkerFactory(self)
        self.worker_factory.login('Worker')
        
def main(args):
    # run-job
    if args[1:]:
        from flumotion.worker import job
        print 'Starting worker job', repr(args)
        name = args[1]
        filename = args[2]
        
        job_factory = job.JobFactory(name)
        reactor.connectUNIX(filename, job_factory)
        reactor.run()
    else:
        host = 'localhost'
        port = 8890

        fabric = WorkerFabric(host, port)
        
        reactor.connectTCP(host, port, fabric.worker_factory)
        reactor.run()
