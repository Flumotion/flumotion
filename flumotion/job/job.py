# -*- Mode: Python -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# Flumotion - a streaming media server
# Copyright (C) 2004,2005,2006 Fluendo, S.L. (www.fluendo.com).
# All rights reserved.

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
the job-side half of the worker-job connection
"""

import os
import resource

# I've read somewhere that importing the traceback module messes up the
# exception state, so it's better to import it globally instead of in the
# exception handler
# import traceback

from twisted.cred import credentials
from twisted.internet import reactor
from twisted.python import failure
from twisted.spread import pb

from flumotion.common import config, errors, interfaces, log, registry, keycards
from flumotion.common import medium, package
from flumotion.common.reflectcall import createComponent
from flumotion.component import component

from flumotion.twisted import fdserver
from flumotion.twisted import pb as fpb

from flumotion.twisted.defer import defer_generator_method
from flumotion.twisted.compat import implements

class JobMedium(medium.BaseMedium):
    """
    I am a medium between the job and the worker's job avatar.
    I live in the job process.

    @cvar component: the component this is a medium for; created as part of
                     L{remote_create}
    @type component: L{flumotion.component.component.BaseComponent}
    """
    logCategory = 'jobmedium'

    implements(interfaces.IJobMedium)

    def __init__(self):
        self.avatarId = None
        self.logName = None
        self.component = None

        self._workerName = None
        self._managerHost = None
        self._managerPort = None
        self._managerTransport = None
        self._managerKeycard = None
        self._componentClientFactory = None # from component to manager

    ### pb.Referenceable remote methods called on by the WorkerBrain
    def remote_bootstrap(self, workerName, host, port, transport, authenticator,
            packagePaths):
        """
        I receive the information on how to connect to the manager. I also set
        up package paths to be able to run the component.
        
        Called by the worker's JobAvatar.
        
        @param workerName:    the name of the worker running this job
        @type  workerName:    str
        @param host:          the host that is running the manager
        @type  host:          str
        @param port:          port on which the manager is listening
        @type  port:          int
        @param transport:     'tcp' or 'ssl'
        @type  transport:     str
        @param authenticator: remote reference to the worker-side authenticator
        @type  authenticator: L{twisted.spread.pb.RemoteReference} to a
                              L{flumotion.twisted.pb.Authenticator}
        @param packagePaths:  ordered list of
                              (package name, package path) tuples
        @type  packagePaths:  list of (str, str)
        """
        assert isinstance(workerName, str)
        assert isinstance(host, str)
        assert isinstance(port, int)
        assert transport in ('ssl', 'tcp')
        assert isinstance(authenticator, pb.RemoteReference)
        assert isinstance(packagePaths, list)

        self.debug('remote_bootstrap')
        self._workerName = workerName
        self._managerHost = host
        self._managerPort = port
        self._managerTransport = transport
        self._authenticator = fpb.RemoteAuthenticator(authenticator)
        
        packager = package.getPackager()
        for name, path in packagePaths:
            self.debug('registering package path for %s' % name)
            self.log('... from path %s' % path)
            packager.registerPackagePath(path, name)

    def remote_create(self, avatarId, type, moduleName, methodName, config):
        """
        I am called on by the worker's JobAvatar to create a component.
        
        @param avatarId:   avatarId for component to log in to manager
        @type  avatarId:   str
        @param type:       type of component to start
        @type  type:       str
        @param moduleName: name of the module to create the component from
        @type  moduleName: str
        @param methodName: the factory method to use to create the component
        @type  methodName: str
        @param config:     the configuration dictionary
        @type  config:     dict
        """
        self.debug('remote_create, avatarId %s' % avatarId)
        self.avatarId = avatarId
        self.logName = avatarId

        self.component = self._createComponent(avatarId, type, moduleName,
            methodName, config)

    def remote_stop(self):
        self.debug('remote_stop() called')
        # stop reactor from a callLater so this remote method finishes
        # nicely
        reactor.callLater(0, self.shutdown)

    def shutdownHandler(self):
        if self.component:
            medium = self.component.medium
            if medium.hasRemoteReference():
                d = medium.callRemote("cleanShutdown")
                return d
        return None

    ### our methods
    def shutdown(self):
        """
        Shut down the job process completely, cleaning up the component
        so the reactor can be left from.
        """
        reactorAlreadyStopped = False
        if self.component:
            self.debug('stopping component')
            self.component.stop()
            if self.component.medium and self.component.medium.reactor_stopped:
                reactorAlreadyStopped = True
            self.debug('stopped component')

        if not reactorAlreadyStopped:
            self.debug('stopping reactor')
            reactor.stop()
            self.debug('reactor stopped, exiting process')

    def _setNice(self, nice):
        if not nice:
            return
        
        try:
            os.nice(nice)
        except OSError, e:
            self.warning('Failed to set nice level: %s' % str(e))
        else:
            self.debug('Nice level set to %d' % nice)

    def _enableCoreDumps(self):
        soft, hard = resource.getrlimit(resource.RLIMIT_CORE)
        if hard != resource.RLIM_INFINITY:
            self.warning('Could not set unlimited core dump sizes, '
                         'setting to %d instead' % hard)
        else:
            self.debug('Enabling core dumps of unlimited size')
            
        resource.setrlimit(resource.RLIMIT_CORE, (hard, hard))
        
    # FIXME: we only use "nice" from config anymore
    def _createComponent(self, avatarId, type, moduleName, methodName, config):
        """
        Create a component of the given type.
        Log in to the manager with the given avatarId.

        @param avatarId:   avatarId component will use to log in to manager
        @type  avatarId:   str
        @param type:       type of component to start
        @type  type:       str
        @param moduleName: name of the module that contains the entry point
        @type  moduleName: str
        @param methodName: name of the factory method to create the component
        @type  methodName: str
        @param config:     the configuration dictionary
        @type  config:     dict
        """
        
        self.debug('_createComponent(): config dictionary is: %r' % config)

        self.info('Creating component "%s" of type "%s"' % (avatarId, type))
        #self.info('setting up signals')
        #signal.signal(signal.SIGINT, signal.SIG_IGN)

        self._setNice(config.get('nice', 0))
        self._enableCoreDumps()
        
        # FIXME: we put avatarId in the config for now
        # but it'd be nicer to do this outside of config, so do this
        config['avatarId'] = avatarId
        try:
            comp = createComponent(moduleName, methodName)
        except Exception, e:
            msg = "Exception %s during createComponent: %s" % (
                e.__class__.__name__, " ".join(e.args))
            # traceback.print_exc()
            # a ComponentCreateError is already formatted
            if isinstance(e, errors.ComponentCreateError):
                msg = e.args[0]
            self.warning(
                "raising ComponentCreateError(%s) and stopping job" % msg)
            # This is a Nasty Hack. We raise ComponentCreateError, which can be
            # caught on the other side and marshalled as a reasonably 
            # comprehensible error message. However, if we shutdown immediately,
            # the PB connection won't be available, so the worker will just get
            # an error about that! So, instead, we shut down in a tenth of a
            # second, usually allowing the worker to get scheduled and read the
            # exception over PB. Ick!
            reactor.callLater(0.1, self.shutdown)
            raise errors.ComponentCreateError(msg)

        comp.setWorkerName(self._workerName)

        # make component log in to manager
        self.debug('creating ComponentClientFactory')
        managerClientFactory = component.ComponentClientFactory(comp)
        self._componentClientFactory = managerClientFactory
        self.debug('created ComponentClientFactory %r' % managerClientFactory)
        self._authenticator.avatarId = avatarId
        managerClientFactory.startLogin(self._authenticator)

        host = self._managerHost
        port = self._managerPort
        transport = self._managerTransport
        self.debug('logging in with authenticator %r' % self._authenticator)
        if transport == "ssl":
            from twisted.internet import ssl
            self.info('Connecting to manager %s:%d with SSL' % (host, port))
            reactor.connectSSL(host, port, managerClientFactory,
                ssl.ClientContextFactory())
        elif transport == "tcp":
            self.info('Connecting to manager %s:%d with TCP' % (host, port))
            reactor.connectTCP(host, port, managerClientFactory)
        else:
            self.error('Unknown transport protocol %s' % self._managerTransport)

        return comp
        
class JobClientBroker(pb.Broker, log.Loggable):
    """
    A pb.Broker subclass that handles FDs being passed (with associated data)
    over the same connection as the normal PB data stream.
    When an FD is seen, the FD should be added to a given eater or feeder
    element.
    """
    def __init__(self, connectionClass, **kwargs):
        """
        @param connectionClass: a subclass of L{twisted.internet.tcp.Connection}
        """
        pb.Broker.__init__(self, **kwargs)

        self._connectionClass = connectionClass

    def fileDescriptorsReceived(self, fds, message):
        # file descriptors get delivered to the component
        self.debug('received fds %r, message %r' % (fds, message))
        if message.startswith('sendFeed '):
            feedName = message[len('sendFeed '):]
            self.factory.medium.component.feedToFD(feedName, fds[0])
        elif message.startswith('receiveFeed '):
            feedId = message[len('receiveFeed '):]
            self.factory.medium.component.eatFromFD(feedId, fds[0])
        else:
            self.warning('Unknown message received: %r' % message)

class JobClientFactory(pb.PBClientFactory, log.Loggable):
    """
    I am a client factory that logs in to the WorkerBrain.
    I live in the flumotion-worker job process.

    @cvar medium: the medium for the JobHeaven to access us through
    @type medium: L{JobMedium}
    """
    logCategory = "job"
    perspectiveInterface = interfaces.IJobMedium    

    def __init__(self, id):
        """
        @param id:      the avatar id used for logging into the workerbrain
        @type  id:      str
        """
        pb.PBClientFactory.__init__(self)
        
        self.medium = JobMedium()
        self.logName = id
        self.login(id)

        # use an FD-passing broker instead
        self.protocol = JobClientBroker
            
    ### pb.PBClientFactory methods
    def buildProtocol(self, addr):
        p = self.protocol(fdserver.FDServer)
        p.factory = self
        return p

    # FIXME: might be nice if jobs got a password to use to log in to brain
    def login(self, username):
        self.info('Logging in to worker')
        d = pb.PBClientFactory.login(self, 
            credentials.UsernamePassword(username, ''),
            self.medium)
        yield d
        try:
            remoteReference = d.value()
            self.info('Logged in to worker')
            self.debug('perspective %r connected' % remoteReference)
            self.medium.setRemoteReference(remoteReference)
        except Exception, e:
            from flumotion.common import debug; debug.print_stack()
            print ('ERROR connecting job to worker [%d]: %s'
                   % (os.getpid(), log.getExceptionMessage(e)))
            # raise error
    login = defer_generator_method(login)
    
    # the only way stopFactory can be called is if the WorkerBrain closes
    # the pb server.  Ideally though we would have gotten a notice before.
    # This ensures we shut down the component/job in ALL cases where the worker
    # goes away.
    def stopFactory(self):
        self.debug('shutting down medium')
        self.medium.shutdown()
        self.debug('shut down medium')
