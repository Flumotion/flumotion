# -*- Mode: Python -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# flumotion/worker/job.py: functionality for the flumotion-worker job processes
#
# Flumotion - a streaming media server
# Copyright (C) 2004 Fluendo, S.L. (www.fluendo.com). All rights reserved.

# This file may be distributed and/or modified under the terms of
# the GNU General Public License version 2 as published by
# the Free Software Foundation.
# This file is distributed without any warranty; without even the implied
# warranty of merchantability or fitness for a particular purpose.
# See "LICENSE.GPL" in the source distribution for more information.

# Licensees having purchased or holding a valid Flumotion Advanced
# Streaming Server license may use this file in accordance with the
# Flumotion Advanced Streaming Server Commercial License Agreement.
# See "LICENSE.Flumotion" in the source distribution for more information.

# Headers in this file shall remain intact.

"""
Worker-side objects to handle job processes.
"""

import os
import sys
import resource
import signal
import gobject

from twisted.cred.credentials import UsernamePassword
from twisted.internet import reactor
from twisted.python import reflect, failure
from twisted.spread import pb

from flumotion.common import config, errors, interfaces, log, registry, keycards
from flumotion.component import component
from flumotion.twisted import credentials

def getComponent(dict, defs):
    #FIXME: add setup of files to be transmitted over the wire.
    source = defs.getSource()
    log.debug('component', 'Loading source %s' % source)
    try:
        module = reflect.namedAny(source)
    except ValueError:
        raise config.ConfigError("%s source file could not be found" % source)
    except ImportError, e:
        raise config.ConfigError("%s source file could not be imported (%s)" % (source, e))
    except Exception, e:
        raise config.ConfigError("Exception %s during import of source %s (%s)" % (e.__class__.__name__, source, e))
        
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

    def __init__(self, options):
        self.remote = None
        self.options = options
        self.name = None
        
    ### pb.Referenceable remote methods called on by the WorkerBrain
    ### FIXME: arguments not needed anymore, Medium knows about options
    def remote_initial(self, host, port, transport):
        self.manager_host = host
        self.manager_port = port
        self.manager_transport = transport
        
    def remote_start(self, name, type, configDict, feedPorts):
        """
        I am called on by the worker's JobAvatar to start a component.
        
        @param name:       name of component to start
        @type  name:       string
        @param type:       type of component to start
        @type  type:       string
        @param configDict: the configuration dictionary
        @type  configDict: dict
        @param feedPorts:  feedName -> port
        @type  feedPorts:  dict
        """
        self.name = name
        defs = registry.registry.getComponent(type)
        self._runComponent(name, type, configDict, defs, feedPorts)

    def remote_stop(self):
        self.debug('%s: remote_stop() called' % self.name)
        reactor.stop()
        #os._exit(0)

    ### IMedium methods
    def setRemoteReference(self, remoteReference):
        self.remote = remoteReference
    
    # FIXME: add to IMedium
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
    
    def _runComponent(self, name, type, config, defs, feedPorts):
        """
        @param name:      name of component to start
        @type  name:      string
        @param type:      type of component to start
        @type  type:      string
        @param config:    the configuration dictionary
        @type  config:    dict
        @param defs:      the registry entry for a component
        @type  defs:      L{flumotion.common.registry.RegistryEntryComponent}
        @param feedPorts: feedName -> port
        @type  feedPorts: dict
        """
        
        self.info('Starting component %s of type %s' % (name, type))
        #self.info('setting up signals')
        #signal.signal(signal.SIGINT, signal.SIG_IGN)
        self.threads_init()

        log.debug(name, 'Starting on pid %d of type %s' %
                  (os.getpid(), type))

        self.set_nice(name, config.get('nice', 0))
        self.enable_core_dumps(name)
        
        log.debug(name, '_runComponent(): config dictionary is: %r' % config)
        log.debug(name, '_runComponent(): feedPorts is: %r' % feedPorts)
        log.debug(name, '_runComponent(): defs is: %r' % defs)

        comp = None
        try:
            comp = getComponent(config, defs)
        except Exception, error:
            self.warning("raising ComponentStart(%s)" % error)
            raise errors.ComponentStart(error)

        # we have components without feed ports, and without this function
        if feedPorts:
            comp.set_feed_ports(feedPorts)

        # make component log in to manager
        manager_client_factory = component.ComponentClientFactory(comp)
        keycard = keycards.KeycardUACPP(self.options.username,
            self.options.password, 'localhost')
        keycard.avatarId = name
        manager_client_factory.login(keycard)

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

        self.component_factory = manager_client_factory
        
class JobClientFactory(pb.PBClientFactory, log.Loggable):
    """
    I am a client factory that logs in to the WorkerBrain.
    I live in the flumotion-worker job process.
    """
    def __init__(self, name, options):
        """
        @param options: the command-line options the worker was started with
        """
        pb.PBClientFactory.__init__(self)
        
        # we pass the options to the medium
        self.medium = JobMedium(options)
        self.login(name)
            
    ### pb.PBClientFactory methods
    def login(self, username):
        d = pb.PBClientFactory.login(self, 
                                     credentials.Username(username),
                                     self.medium)
        d.addCallbacks(self._connectedCallback,
                       self._connectedErrback)
        return d
    
    def _connectedCallback(self, remoteReference):
        self.info('perspective %r connected' % remoteReference)
        self.medium.setRemoteReference(remoteReference)

    def _connectedErrback(self, error):
        print 'ERROR:' + str(error)

def run(name, options):
    """
    Called by the worker to start a job fork.
    """
    worker_filename = '/tmp/flumotion.%d' % os.getpid()

    pid = os.fork()
    if pid:
        return pid

    signal.signal(signal.SIGINT, signal.SIG_IGN)
    
    reactor.removeAll()

    # the only usable object created for now in the child is the
    # JobClientFactory, so we throw the options at it
    job_factory = JobClientFactory(name, options)
    reactor.connectUNIX(worker_filename, job_factory)
    log.debug('job', 'Starting reactor')
    reactor.run()

    def _exitCb(*unused):
        while reactor.iterate():
            pass
                
        reactor.stop()
            
    #reactor.callLater(0, _exitCb)
    #reactor.run()
    log.debug('job', 'Left reactor.run')
    log.info('job', 'Job stopped, returning with exit value 0')
            
    os._exit(0)
    
