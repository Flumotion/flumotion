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
import signal
import sys

from twisted.internet import protocol, reactor
from twisted.spread import pb

from flumotion.common import interfaces
from flumotion.twisted import pbutil
from flumotion.utils import log
from flumotion.worker import job, report

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
    def getPid(self):
        return self.protocol.pid
    
class Kindergarten:
    def __init__(self):
        dirname = os.path.split(os.path.abspath(sys.argv[0]))[0]
        self.program = os.path.join(dirname, 'flumotion-worker')
        self.kids = {}
        
    def play(self, name, type, config):
        args = [self.program, name, '/tmp/flumotion.%d' % os.getpid()]
        log.debug('worker', 'Launching process %s' % name)
        p = reactor.spawnProcess(protocol.ProcessProtocol(),
                                 self.program, args,
                                 env=os.environ,
                                 childFDs={ 0: 0, 1: 1, 2: 2})
        self.kids[name] = Kid(p, name, type, config)

        return p
    
    def getKids(self):
        return self.kids.values()
    
# Similar to Vishnu, but for worker related classes
class WorkerFabric:
    def __init__(self, host, port):
        self.manager_host = host
        self.manager_port = port
        
        self.kindergarten = Kindergarten()
        self.report_factory, self.report_heaven = report.setup(self)

        self.worker_view = WorkerView(self)
        self.worker_factory = WorkerFactory(self)
        self.worker_factory.login('Worker')

def run_job(args):
    name = args[1]
    filename = args[2]
        
    job_factory = job.JobFactory(name)
    reactor.connectUNIX(filename, job_factory)

    log.debug('job', 'Starting reactor')
    reactor.run()
    log.debug('job', 'Reactor stopped')
    
def run_worker(args):
    host = 'localhost'
    port = 8890
    
    fabric = WorkerFabric(host, port)
    
    reactor.connectTCP(host, port, fabric.worker_factory)
    log.debug('worker', 'Starting reactor')
    reactor.run()
    log.debug('worker', 'Reactor stopped')

    log.debug('worker', 'Shutting down jobs')

    # Is this really necessary
    fabric.report_heaven.shutdown()

    pids = [kid.getPid() for kid in fabric.kindergarten.getKids()]
    
    log.debug('worker', 'Waiting for jobs to finish')
    while pids:
        pid = os.wait()[0]
        pids.remove(pid)

    log.debug('worker', 'All jobs finished, closing down')

def main(args):
    # run-job
    if args[1:]:
        log.debug('launching job with args %r' % args)
        run_job(args)
    else:
        signal.signal(signal.SIGCHLD, signal.SIG_IGN)
        signal.signal(signal.SIGINT, signal.SIG_IGN)
        log.debug('launching worker with args %r' % args)
        run_worker(args)
