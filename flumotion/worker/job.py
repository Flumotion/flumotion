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

import os
import resource
import signal
import gobject

from twisted.cred.credentials import UsernamePassword
from twisted.internet import reactor
from twisted.spread import pb

from flumotion.common.config import ConfigEntry
from flumotion.common.registry import registry
from flumotion.component import component
from flumotion.worker import launcher
from flumotion.twisted import pbutil
from flumotion.utils import log

class JobView(pb.Referenceable, log.Loggable):
    logCategory = 'job'
    def __init__(self):
        self.remote = None
        
    def hasPerspective(self):
        return self.remote != None

    def cb_gotPerspective(self, perspective):
        self.remote = perspective

    def remote_initial(self, host, port):
        self.manager_host = host
        self.manager_port = port
        self.launcher = launcher.Launcher(host, port)
        
    def remote_start(self, name, type, config):
        print 'START NOW', type
        
        defs = registry.getComponent(type)
        entry = ConfigEntry(name, type, config, defs)
        self.run_component(entry)

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
    
    def run_component(self, config):
        self.info('setting up signals')
        #signal.signal(signal.SIGINT, signal.SIG_IGN)
        self.threads_init()

        name = config.getName()
        type = config.getType()
        
        log.debug(name, 'Starting on pid %d of type %s' %
                  (os.getpid(), type))

        self.set_nice(name, config.nice)
        self.enable_core_dumps(name)
        
        dict = config.getConfigDict()
        log.debug(name, 'Configuration dictionary is: %r' % dict)
        
        comp = config.getComponent()
        factory = component.ComponentFactory(comp)
        factory.login(name)
        reactor.connectTCP(self.manager_host,
                           self.manager_port, factory)

        reactor.run(False)
    
class JobFactory(pb.PBClientFactory, log.Loggable):
    def __init__(self, name):
        pb.PBClientFactory.__init__(self)
        
        self.view = JobView()
        self.login(name)
            
    def login(self, username):
        d = pb.PBClientFactory.login(self, 
                                     pbutil.Username(username),
                                     self.view)
        d.addCallbacks(self.cb_connected,
                       self.cb_failure)
        return d
    
    def cb_connected(self, perspective):
        self.info('perspective %r connected' % perspective)
        self.view.cb_gotPerspective(perspective)

    def cb_failure(self, error):
        print 'ERROR:' + str(error)
