# -*- Mode: Python -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# flumotion/worker/job.py: jobs done by the worker
#
# Flumotion - a streaming media server
# Copyright (C) 2004 Fluendo (www.fluendo.com)

# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
# See "LICENSE.GPL" in the source distribution for more information.

# This program is also licensed under the Flumotion license.
# See "LICENSE.Flumotion" in the source distribution for more information.

import os
import resource
import signal
import gobject

from twisted.cred.credentials import UsernamePassword
from twisted.internet import reactor
from twisted.python import reflect
from twisted.spread import pb

from flumotion.common.registry import registry
from flumotion.component import component
from flumotion.worker import launcher
from flumotion.twisted import cred
from flumotion.utils import log

def getComponent(dict, defs):
    # Setup files to be transmitted over the wire. Must be a
    # better way of doing this.
    source = defs.getSource()
    log.info('job', 'Loading %s' % source)
    try:
        module = reflect.namedAny(source)
    except ValueError:
        raise ConfigError("%s source file could not be found" % source)
        
    if not hasattr(module, 'createComponent'):
        log.warning('job', 'no createComponent() for %s' % source)
        return
        
    dir = os.path.split(module.__file__)[0]
    files = {}
    for file in defs.getFiles():
        filename = os.path.basename(file.getFilename())
        real = os.path.join(dir, filename)
        files[real] = file
        
    # Create the component which the specified configuration
    # directives. Note that this can't really be moved from here
    # since it gets called by the launcher from another process
    # and we don't want to create it in the main process, since
    # we're going to listen to ports and other stuff which should
    # be separated from the main process.

    component = module.createComponent(dict)
    component.setFiles(files)
    return component

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
        defs = registry.getComponent(type)
        self.run_component(name, type, config, defs)

    def remote_stop(self):
        reactor.stop()
        raise SystemExit
    
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
    
    def run_component(self, name, type, config, defs):
        if not config.get('start-factory', True):
            return
        
        #self.info('setting up signals')
        #signal.signal(signal.SIGINT, signal.SIG_IGN)
        self.threads_init()

        log.debug(name, 'Starting on pid %d of type %s' %
                  (os.getpid(), type))

        self.set_nice(name, config.get('nice', 0))
        self.enable_core_dumps(name)
        
        log.debug(name, 'Configuration dictionary is: %r' % config)

        comp = getComponent(config, defs)
        factory = component.ComponentFactory(comp)
        factory.login(name)
        reactor.connectTCP(self.manager_host,
                           self.manager_port, factory)
    
class JobFactory(pb.PBClientFactory, log.Loggable):
    def __init__(self, name):
        pb.PBClientFactory.__init__(self)
        
        self.view = JobView()
        self.login(name)
            
    def login(self, username):
        d = pb.PBClientFactory.login(self, 
                                     cred.Username(username),
                                     self.view)
        d.addCallbacks(self.cb_connected,
                       self.cb_failure)
        return d
    
    def cb_connected(self, perspective):
        self.info('perspective %r connected' % perspective)
        self.view.cb_gotPerspective(perspective)

    def cb_failure(self, error):
        print 'ERROR:' + str(error)
