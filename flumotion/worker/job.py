# -*- Mode: Python -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# flumotion/worker/job.py: functionality for the flumotion-worker job processes
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

"""
Worker-side objects to handle job processes.
"""

import os
import resource
import signal
import gobject

from twisted.cred.credentials import UsernamePassword
from twisted.internet import reactor
from twisted.python import reflect
from twisted.spread import pb

from flumotion.common.registry import registry
from flumotion.common import interfaces
from flumotion.component import component
from flumotion.twisted import cred
from flumotion.utils import log

def getComponent(dict, defs):
    #FIXME: add setup of files to be transmitted over the wire.
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
        
    # Create the component with the specified configuration
    # directives. Note that this can't really be moved from here
    # since it gets called by the job from another process
    # and we don't want to create it in the main process, since
    # we're going to listen to ports and other stuff which should
    # be separated from the main process.

    component = module.createComponent(dict)
    return component

class JobMedium(pb.Referenceable, log.Loggable):
    """
    I am a medium between the job and the worker's job avatar.
    I live in the job process.
    """
    logCategory = 'jobmedium'

    __implements__ = interfaces.IJobMedium,

    def __init__(self):
        self.remote = None
        
    ### pb.Referenceable remote methods called on by the WorkerBrain
    def remote_initial(self, host, port, transport):
        self.manager_host = host
        self.manager_port = port
        self.manager_transport = transport
        
    def remote_start(self, name, type, config, feedPorts):
        """
        @param feedPorts: feedName -> port
        @type feedPorts: dict
        """
        defs = registry.getComponent(type)
        self.run_component(name, type, config, defs, feedPorts)

    def remote_stop(self):
        reactor.stop()
        raise SystemExit

    ### IMedium methods
    def setRemoteReference(self, remoteReference):
        self.remote = remoteReference
    
    #FIXME: add to IMedium
    def hasPerspective(self):
        return self.remote != None

    ### our methods
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
    
    def run_component(self, name, type, config, defs, feed_ports):
        """
        @param feed_ports: feed_name -> port
        @type feed_ports: dict, or None
        """
        # XXX: Remove this hack
        if not config.get('start-factory', True):
            return
        
        #self.info('setting up signals')
        #signal.signal(signal.SIGINT, signal.SIG_IGN)
        self.threads_init()

        log.debug(name, 'Starting on pid %d of type %s' %
                  (os.getpid(), type))

        self.set_nice(name, config.get('nice', 0))
        self.enable_core_dumps(name)
        
        log.debug(name, 'run_component(): config dictionary is: %r' % config)
        log.debug(name, 'run_component(): feed_ports is: %r' % feed_ports)

        comp = getComponent(config, defs)

        # we have components without feed ports, and without this function
        if feed_ports:
            comp.set_feed_ports(feed_ports)

        manager_client_factory = component.ComponentClientFactory(comp)
        # XXX: get username/password from parent
        manager_client_factory.login(name)

        host = self.manager_host
        port = self.manager_port
        transport = self.manager_transport
        if transport == "ssl":
            from twisted.internet import ssl
            log.info('job',
                'Connecting to manager %s:%d with SSL' % (host, port))
            reactor.connectSSL(host, port, manager_client_factory,
                ssl.ClientContextFactory())
        elif self.manager_transport == "tcp":
            log.info('job',
                'Connecting to manager %s:%d with TCP' % (host, port))
            reactor.connectTCP(host, port, manager_client_factory)
        else:
            self.error('Unknown transport protocol %s' % self.manager_transport)
    
class JobClientFactory(pb.PBClientFactory, log.Loggable):
    """
    I am a client factory that logs in to the WorkerBrain.
    I live in the flumotion-worker job process.
    """
    def __init__(self, name):
        pb.PBClientFactory.__init__(self)
        
        self.medium = JobMedium()
        self.login(name)
            
    ### pb.PBClientFactory methods
    def login(self, username):
        d = pb.PBClientFactory.login(self, 
                                     cred.Username(username),
                                     self.medium)
        d.addCallbacks(self._connectedCallback,
                       self._connectedErrback)
        return d
    
    def _connectedCallback(self, remoteReference):
        self.info('perspective %r connected' % remoteReference)
        self.medium.setRemoteReference(remoteReference)

    def _connectedErrback(self, error):
        print 'ERROR:' + str(error)
