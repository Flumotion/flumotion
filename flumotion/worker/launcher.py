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
import resource
import signal
import gobject

from twisted.internet import reactor

from flumotion.component import component
from flumotion.utils import log

from twisted.internet import protocol

class WorkerProtocol(protocol.ProcessProtocol):
    def __init__(self):
        pass
    
    def connectionMade(self):
        return
    
        self.transport.writeToChild(3, self.passphrase)
        self.transport.closeChildFD(3)
        self.transport.writeToChild(0, self.crypttext)
        self.transport.closeChildFD(0)
        
    def childDataReceived(self, childFD, data):
        return

def run(name, fd):
    proto = WorkerProtocol()
    cmd = ["flumotion-worker",
           '--run', name,
           '--parent-fd', str(fd)]
    
    p = reactor.spawnProcess(proto, cmd[0], cmd,
                             childFDs={str(fd): "rw"})
    
class Launcher(log.Loggable):
    logCategory = 'launcher'
    def __init__(self, host, port):
        self.children = []
        self.manager_host = host
        self.manager_port = port
        self.uid = None
        
        signal.signal(signal.SIGCHLD, signal.SIG_IGN)
    
    def restore_uid(self, name):
        if self.uid is None:
            return
        
        try:
            os.setuid(self.uid)
            log.debug(name, 'uid set to %d' % (self.uid))
        except OSError, e:
            log.warning(name, 'failed to set uid: %s' % str(e))

    def set_nice(self, name, nice):
        if not nice:
            return
        
        try:
            os.nice(nice)
        except OSError, e:
            log.warning(name, 'Failed to set nice level: %s' % str(e))
        else:
            log.debug(name, 'Nice level set to %d' % nice)

    def enable_core_dumps(self, name):
        soft, hard = resource.getrlimit(resource.RLIMIT_CORE)
        if hard != resource.RLIM_INFINITY:
            log.warning(name, 'Could not set ulimited core dump sizes, setting to %d instead' % hard)
        else:
            log.debug(name, 'Enabling core dumps of ulimited size')
            
        resource.setrlimit(resource.RLIMIT_CORE, (hard, hard))
        
    def threads_init(self):
        try:
            gobject.threads_init()
        except AttributeError:
            self.warning('Old PyGTK detected')
        except RuntimeError:
            self.warning('Old PyGTK with threading disabled detected')
    
    def launch_component(self, config):
        self.info('entering launch component')
        if not config.startFactory():
            self.debug('Not starting a factory.')
            return

        self.info('forking')

        r, w = os.pipe()
        pid = os.fork()
        if pid:
            self.children.append(pid)
            return

        self.run_component(config)
        
    def run_component(self, config):
        self.info('setting up signals')
        #signal.signal(signal.SIGINT, signal.SIG_IGN)
        self.threads_init()

        name = config.getName()
        type = config.getType()
        
        log.debug(name, 'Starting on pid %d of type %s' %
                  (os.getpid(), type))

        self.restore_uid(name)
        self.set_nice(name, config.nice)
        self.enable_core_dumps(name)
        
        dict = config.getConfigDict()
        log.debug(name, 'Configuration dictionary is: %r' % dict)
        
        comp = config.getComponent()
        factory = component.ComponentFactory(comp)
        factory.login(name)
        reactor.connectTCP(self.manager_host, self.manager_port, factory)

        reactor.run(False)
        
    def run(self, factory):
        reactor.connectTCP(self.manager_host,
                           self.manager_port, factory)
        reactor.run()

        for pid in self.children:
            os.kill(pid, signal.SIGINT)
            
        print 'EXIT RUN'

    

