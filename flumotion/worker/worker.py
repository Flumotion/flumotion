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

import optparse
import os
import signal
import sys

from twisted.internet import protocol, reactor
from twisted.spread import pb

# We want to avoid importing gst, otherwise --help fails
# so be very careful when adding imports
from flumotion.common import errors, interfaces
from flumotion.twisted import pbutil
from flumotion.utils import log

#factory = pbutil.ReconnectingPBClientFactory
factory = pbutil.FMClientFactory
class WorkerFactory(factory):
    #__super_login = factory.startLogin
    __super_login = factory.login
    def __init__(self, parent):
        self.view = parent.worker_view
        # doing this as a class method triggers a doc error
        factory.__init__(self)
        
    def login(self, username, password):
        return self.__super_login(pbutil.Username(username, password),
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
        worker_filename = '/tmp/flumotion.%d' % os.getpid()
        args = [self.program,
                '--job', name,
                '--worker', worker_filename]
        log.debug('worker', 'Launching process %s' % name)
        p = reactor.spawnProcess(protocol.ProcessProtocol(),
                                 self.program, args,
                                 env=os.environ,
                                 childFDs={ 0: 0, 1: 1, 2: 2})
        self.kids[name] = Kid(p, name, type, config)

        return p

    def getKid(self, name):
        return self.kids[name]
    
    def getKids(self):
        return self.kids.values()
    
# Similar to Vishnu, but for worker related classes
class WorkerFabric:
    def __init__(self, host, port):
        signal.signal(signal.SIGCHLD, signal.SIG_IGN)
        signal.signal(signal.SIGINT, signal.SIG_IGN)

        self.manager_host = host
        self.manager_port = port
        
        self.kindergarten = Kindergarten()
        from flumotion.worker import report
        self.report_factory, self.report_heaven = report.setup(self)

        self.worker_view = WorkerView(self)
        self.worker_factory = WorkerFactory(self)

    def login(self, username, password):
        d = self.worker_factory.login(username, password)
        d.addErrback(self.cb_accessDenied)

    def cb_accessDenied(self, failure):
        failure.trap(errors.AccessDeniedError)
        print 'ACCESS DENIED, GOOD LUCK'
    
def main(args):
    parser = optparse.OptionParser()
    group = optparse.OptionGroup(parser, "Worker options")
    group.add_option('-m', '--manager-host',
                     action="store", type="string", dest="host",
                     default="localhost",
                     help="Manager to connect to [default localhost]")
    group.add_option('-p', '--manager-port',
                     action="store", type="int", dest="port",
                     default=8890,
                     help="Manager port to connect to [default 8890]")
    group.add_option('-u', '--username',
                     action="store", type="string", dest="username",
                     default="",
                     help="Username to use")
    group.add_option('-d', '--password',
                     action="store", type="string", dest="password",
                     default="",
                     help="Password to use, - for interactive")
    parser.add_option_group(group)
    group = optparse.OptionGroup(parser, "Job options")
    group.add_option('-j', '--job',
                     action="store", type="string", dest="job",
                     help="Run job")
    group.add_option('-w', '--worker',
                     action="store", type="string", dest="worker",
                     help="Worker unix socket to connect to")
    parser.add_option_group(group)
    
    log.debug('manager', 'Parsing arguments (%r)' % ', '.join(args))
    options, args = parser.parse_args(args)

    # If job is specificed, run a job
    if options.job:
        from flumotion.worker import job
        job_factory = job.JobFactory(options.job)
        reactor.connectUNIX(options.worker, job_factory)
    else:
        log.debug('Connectiong to %s:%d' % (options.host, options.port))
    
        fabric = WorkerFabric(options.host, options.port)
        fabric.login(options.username, options.password or '')
        reactor.connectTCP(options.host, options.port, fabric.worker_factory)
        
    log.debug('worker', 'Starting reactor')
    reactor.run()
    log.debug('worker', 'Reactor stopped')

    log.debug('worker', 'Shutting down jobs')

    if not options.job:
        # XXX: Is this really necessary
        fabric.report_heaven.shutdown()

        pids = [kid.getPid() for kid in fabric.kindergarten.getKids()]
        
        log.debug('worker', 'Waiting for jobs to finish')
        while pids:
            pid = os.wait()[0]
            pids.remove(pid)

        log.debug('worker', 'All jobs finished, closing down')
