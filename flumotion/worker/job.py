# -*- Mode: Python -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# Flumotion - a streaming media server
# Copyright (C) 2004,2005 Fluendo, S.L. (www.fluendo.com). All rights reserved.

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
worker-side objects to handle job processes
"""

import os
import sys
import resource
import signal
import gobject

# I've read somewhere that importing the traceback module messes up the
# exception state, so it's better to import it globally instead of in the
# exception handler
import traceback

from twisted.cred import credentials
from twisted.internet import reactor
from twisted.python import reflect, failure
from twisted.spread import pb

from flumotion.common import config, errors, interfaces, log, registry, keycards
from flumotion.common import medium
from flumotion.component import component

def getComponent(dict, defs):
    """
    @param dict: the configuration dictionary
    @type  dict: dict
    @param defs: the registry entry for a component
    @type  defs: L{flumotion.common.registry.RegistryEntryComponent}
    """
    log.debug('component', 'getting module for defs %r' % defs)
    try:
        moduleName = defs.getSource()
    except TypeError, e:
        raise config.ConfigError(
            "could not get module name for defs %r (%s)" % (defs, e))
    except Exception, e:
        raise config.ConfigError(
            "Exception %s while getting module name for defs %r (%s)" % (
                e.__class__.__name__, defs, " ".join(e.args)))
        
    log.debug('component', 'Loading moduleName %s' % moduleName)
    try:
        module = reflect.namedAny(moduleName)
    except ValueError:
        raise config.ConfigError("module %s could not be found" % moduleName)
    except ImportError, e:
        raise config.ConfigError("module %s could not be imported (%s)" % (
            moduleName, e))
    except SyntaxError, e:
        raise config.ConfigError("module %s has a syntax error in %s:%d" % (
            moduleName, e.filename, e.lineno))
    except Exception, e:
        raise config.ConfigError(
            "Exception %r during import of module %s (%r)" % (
                e.__class__.__name__, moduleName, e.args))
        
    if not hasattr(module, 'createComponent'):
        log.warning('job', 'no createComponent() in module %s' % moduleName)
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

    log.debug('job', 'calling createComponent for module %s' % moduleName)
    #component = module.createComponent(dict)
    try:
        component = module.createComponent(dict)
    except Exception, e:
        # find where the exception occurred
        stack = traceback.extract_tb(sys.exc_traceback)
        (filename, line, func, text) = stack[-1]
        filename = log.scrubFilename(filename)
        msg = "%s:%s: %s(): %s during %s.createComponent(): %s" % (
            filename, line, func, e.__class__.__name__, moduleName,
            " ".join([repr(i) for i in e.args]))
        log.warning('job', msg)
        log.warning('job', 'raising config.ConfigError')
        raise config.ConfigError(msg)
    log.debug('job', 'returning component %r' % component)
    return component

class JobMedium(medium.BaseMedium):
    """
    I am a medium between the job and the worker's job avatar.
    I live in the job process.
    """
    logCategory = 'jobmedium'

    __implements__ = interfaces.IJobMedium,

    def __init__(self, options):
        self.options = options
        self.avatarId = None
        self.logName = None

    ### pb.Referenceable remote methods called on by the WorkerBrain
    ### FIXME: arguments not needed anymore, Medium knows about options
    def remote_initial(self, host, port, transport):
        self.manager_host = host
        self.manager_port = port
        self.manager_transport = transport
        
    def remote_start(self, avatarId, type, config, feedPorts):
        """
        I am called on by the worker's JobAvatar to start a component.
        
        @param avatarId:   avatarId for component to log in to manager
        @type  avatarId:   string
        @param type:       type of component to start
        @type  type:       string
        @param config:     the configuration dictionary
        @type  config:     dict
        @param feedPorts:  feedName -> port
        @type  feedPorts:  dict
        """
        self.avatarId = avatarId
        self.logName = avatarId

        defs = registry.registry.getComponent(type)
        self._runComponent(avatarId, type, config, defs, feedPorts)

    def remote_stop(self):
        self.debug('remote_stop() called')
        reactor.stop()
        #os._exit(0)

    ### our methods
    def _set_nice(self, nice):
        if not nice:
            return
        
        try:
            os.nice(nice)
        except OSError, e:
            self.warning('Failed to set nice level: %s' % str(e))
        else:
            self.debug('Nice level set to %d' % nice)

    def _enable_core_dumps(self):
        soft, hard = resource.getrlimit(resource.RLIMIT_CORE)
        if hard != resource.RLIM_INFINITY:
            self.warning('Could not set ulimited core dump sizes, setting to %d instead' % hard)
        else:
            self.debug('Enabling core dumps of ulimited size')
            
        resource.setrlimit(resource.RLIMIT_CORE, (hard, hard))
        
    def threads_init(self):
        try:
            gobject.threads_init()
        except AttributeError:
            self.warning('Old PyGTK detected')
        except RuntimeError:
            self.warning('Old PyGTK with threading disabled detected')
    
    def _runComponent(self, avatarId, type, config, defs, feedPorts):
        """
        @param avatarId:  avatarId component will use to log in to manager
        @type  avatarId:  string
        @param type:      type of component to start
        @type  type:      string
        @param config:    the configuration dictionary
        @type  config:    dict
        @param defs:      the registry entry for a component
        @type  defs:      L{flumotion.common.registry.RegistryEntryComponent}
        @param feedPorts: feedName -> port
        @type  feedPorts: dict
        """
        
        self.info('Starting component "%s" of type "%s"' % (avatarId, type))
        #self.info('setting up signals')
        #signal.signal(signal.SIGINT, signal.SIG_IGN)
        self.threads_init()

        self.debug('Starting on pid %d of type %s' % (os.getpid(), type))

        self._set_nice(config.get('nice', 0))
        self._enable_core_dumps()
        
        self.debug('_runComponent(): config dictionary is: %r' % config)
        self.debug('_runComponent(): feedPorts is: %r' % feedPorts)
        self.debug('_runComponent(): defs is: %r' % defs)

        comp = None

        # FIXME: we put avatarId in the config for now
        # but it'd be nicer to do this outside of config, so do this
        config['avatarId'] = avatarId
        try:
            comp = getComponent(config, defs)
        except Exception, e:
            msg = "Exception %s during getComponent: %s" % (
                e.__class__.__name__, " ".join(e.args))
            traceback.print_exc()
            self.warning("raising ComponentStart(%s)" % msg)
            raise errors.ComponentStart(msg)

        # we have components without feed ports, and without this function
        if feedPorts:
            comp.set_feed_ports(feedPorts)

        comp.setWorkerName(self.options.name)
        comp.setConfig(config)

        # make component log in to manager
        manager_client_factory = component.ComponentClientFactory(comp)
        keycard = keycards.KeycardUACPP(self.options.username,
            self.options.password, 'localhost')
        keycard.avatarId = avatarId
        manager_client_factory.startLogin(keycard)

        host = self.manager_host
        port = self.manager_port
        transport = self.manager_transport
        if transport == "ssl":
            from twisted.internet import ssl
            self.info('Connecting to manager %s:%d with SSL' % (host, port))
            reactor.connectSSL(host, port, manager_client_factory,
                ssl.ClientContextFactory())
        elif self.manager_transport == "tcp":
            self.info('Connecting to manager %s:%d with TCP' % (host, port))
            reactor.connectTCP(host, port, manager_client_factory)
        else:
            self.error('Unknown transport protocol %s' % self.manager_transport)

        self.component_factory = manager_client_factory
        
class JobClientFactory(pb.PBClientFactory, log.Loggable):
    """
    I am a client factory that logs in to the WorkerBrain.
    I live in the flumotion-worker job process.
    """
    logCategory = "job"

    def __init__(self, id, options):
        """
        @param options: the command-line options the worker was started with
        @type  id:      string
        """
        pb.PBClientFactory.__init__(self)
        
        # we pass the options to the medium
        self.medium = JobMedium(options)
        self.logName = id
        self.login(id)
            
    ### pb.PBClientFactory methods
    # FIXME: might be nice if jobs got a password to use to log in to brain
    def login(self, username):
        d = pb.PBClientFactory.login(self, 
            credentials.UsernamePassword(username, ''),
            self.medium)
        self.info('Logging in to worker')
        d.addCallbacks(self._connectedCallback,
                       self._connectedErrback)
        return d
    
    def _connectedCallback(self, remoteReference):
        self.info('Logged in to worker')
        self.debug('perspective %r connected' % remoteReference)
        self.medium.setRemoteReference(remoteReference)

    def _connectedErrback(self, error):
        print 'ERROR:' + str(error)

def getSocketPath():
    # FIXME: better way of getting at a tmp dir ?
    return os.path.join('/tmp', "flumotion.worker.%d" % os.getpid())

def run(avatarId, options):
    """
    Called by the worker to start a job fork.
    """
    workerSocket = getSocketPath()

    pid = os.fork()
    if pid:
        # parent
        return pid

    signal.signal(signal.SIGINT, signal.SIG_IGN)
    
    reactor.removeAll()

    # the only usable object created for now in the child is the
    # JobClientFactory, so we throw the options at it
    job_factory = JobClientFactory(avatarId, options)
    reactor.connectUNIX(workerSocket, job_factory)
    log.info('job', 'Started job on pid %d' % os.getpid())
    log.debug('job', 'Starting reactor')
    reactor.run()

    log.debug('job', 'Left reactor.run')
    log.info('job', 'Job stopped, returning with exit value 0')
            
    os._exit(0)
    
