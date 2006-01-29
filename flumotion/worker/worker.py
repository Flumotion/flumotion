# -*- Mode: Python; test-case-name:flumotion.test.test_worker_worker -*-
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
worker-side objects to handle worker clients
"""

import errno
import os
import signal
import sys

import gst
import gst.interfaces

from twisted.cred import portal
from twisted.internet import defer, protocol, reactor
from twisted.spread import pb
import twisted.cred.error
import twisted.internet.error

from flumotion.common import errors, interfaces, log, bundleclient
from flumotion.common import common, medium, messages
from flumotion.twisted import checkers
from flumotion.twisted import pb as fpb
from flumotion.twisted.defer import defer_generator_method
from flumotion.configure import configure

factoryClass = fpb.ReconnectingFPBClientFactory
class WorkerClientFactory(factoryClass):
    """
    I am a client factory for the worker to log in to the manager.
    """
    logCategory = 'worker'
    def __init__(self, brain):
        """
        @type brain: L{flumotion.worker.worker.WorkerBrain}
        """
        self.manager_host = brain.manager_host
        self.manager_port = brain.manager_port
        self.medium = brain.medium
        # doing this as a class method triggers a doc error
        factoryClass.__init__(self)
        # maximum 10 second delay for workers to attempt to log in again
        self.maxDelay = 10
        
    def startLogin(self, keycard):
        factoryClass.startLogin(self, keycard, self.medium,
            interfaces.IWorkerMedium)
        
    # vmethod implementation
    def gotDeferredLogin(self, d):
        def remoteDisconnected(remoteReference):
            if reactor.killed:
                self.log('Connection to manager lost due to SIGINT shutdown')
            else:
                self.warning('Lost connection to manager, '
                             'will attempt to reconnect')

        def loginCallback(reference):
            self.info("Logged in to manager")
            self.debug("remote reference %r" % reference)
           
            self.medium.setRemoteReference(reference)
            reference.notifyOnDisconnect(remoteDisconnected)

        def alreadyConnectedErrback(failure):
            failure.trap(errors.AlreadyConnectedError)
            self.error('A worker with the name "%s" is already connected.' %
                failure.value)

        def accessDeniedErrback(failure):
            failure.trap(twisted.cred.error.UnauthorizedLogin)
            self.error('Access denied.')
            
        def connectionRefusedErrback(failure):
            failure.trap(twisted.internet.error.ConnectionRefusedError)
            self.error('Connection to %s:%d refused.' % (self.manager_host,
                                                         self.manager_port))
                                                          
        def loginFailedErrback(failure):
            self.error('Login failed, reason: %s' % str(failure))

        d.addCallback(loginCallback)
        d.addErrback(accessDeniedErrback)
        d.addErrback(connectionRefusedErrback)
        d.addErrback(alreadyConnectedErrback)
        d.addErrback(loginFailedErrback)
            
    # override log.Loggable method so we don't traceback
    def error(self, message):
        self.warning('Shutting down worker because of error:')
        self.warning(message)
        print >> sys.stderr, 'ERROR: %s' % message
        reactor.stop()

class WorkerMedium(medium.BaseMedium):
    """
    I am a medium interfacing with the manager-side WorkerAvatar.
    """
    
    logCategory = 'workermedium'

    __implements__ = interfaces.IWorkerMedium,
    
    def __init__(self, brain, ports):
        self.brain = brain
        self.ports = ports
        
    ### pb.Referenceable method for the manager's WorkerAvatar
    def remote_getPorts(self):
        """
        Gets the range of feed ports that this worker was configured to
        use.

        @returns: a list of ports, as integers
        """
        return self.ports

    def remote_create(self, avatarId, type, moduleName, methodName, config):
        """
        Start a component of the given type with the given config dict.
        Will spawn a new job process to run the component in.

        @param avatarId:   avatar identification string
        @type  avatarId:   string
        @param type:       type of the component to create
        @type  type:       string
        @param moduleName: name of the module to create the component from
        @type  moduleName: string
        @param methodName: the factory method to use to create the component
        @type  methodName: string
        @param config:     a configuration dictionary for the component
        @type  config:     dict

        @returns: a deferred fired when the process has started and created
                  the component
        """

        # from flumotion.common import debug
        # def write(indent, str, *args):
        #     print ('[%d]%s%s' % (os.getpid(), indent, str)) % args
        # debug.trace_start(ignore_files_re='twisted/python/rebuild', write=write)

        self.info('Starting component "%s" of type "%s"' % (avatarId, type))
        self.debug('remote_create(): id %s, type %s, config %r' % (
            avatarId, type, config))

        # set up bundles as we need to have a pb connection to download
        # the modules -- can't do that in the kid yet.
        # FIXME: thomas: find a way to rebuild less so this doesn't take
        # excessive amounts of CPU time
        self.debug('setting up bundles for %s' % moduleName)
        d = self.bundleLoader.getBundles(moduleName=moduleName)
        yield d
        # check errors, will proxy to the manager
        bundles = d.value()

        # this could throw ComponentAlreadyStartingError
        d = self.brain.deferredCreate(avatarId)
        if not d:
            msg = ('Component "%s" has already received a create request'
                   % avatarId)
            raise errors.ComponentCreateError(msg)

        # spawn the job process
        self.brain.kindergarten.play(avatarId, type, moduleName, methodName,
            config, bundles)

        yield d

        try:
            result = d.value()
        except errors.ComponentCreateError, e:
            self.debug('deferred create for %s failed, forwarding error' %
                avatarId)
            raise
        self.debug('deferred create for %s succeeded (%r)'
                   % (avatarId, result))
        yield result
    remote_create = defer_generator_method(remote_create)

    def remote_checkElements(self, elementNames):
        """
        Checks if one or more GStreamer elements are present and can be
        instantiated.

        @param elementNames:   names of the Gstreamer elements
        @type  elementNames:   list of strings

        @rtype:   list of strings
        @returns: a list of instantiatable element names
        """
        self.debug('remote_checkElements: element names to check %r' % (
            elementNames,))

        list = []
        # GST 0.8
        for name in elementNames:
            # in 0.9.x, element_factory_make started
            # raising gst.PluginNotFoundError
            try:
                e = gst.element_factory_make(name)
                if e:
                    list.append(name)
            except gst.PluginNotFoundError:
                pass
        self.debug('remote_checkElements: returning elements names %r' % list)
        return list

    def remote_runFunction(self, module, function, *args, **kwargs):
        """
        Runs the given function in the given module with the given arguments.
        
        @param module:   module the function lives in
        @type  module:   string
        @param function: function to run
        @type  function: string

        @returns: the return value of the given function in the module.
        """
        self.debug('remote runFunction(%r, %r)' % (module, function))
        d = self.bundleLoader.loadModule(module)
        yield d

        try:
            mod = d.value()
        except errors.NoBundleError:
            msg = 'Failed to find bundle for module %s' % module
            self.warning(msg)
            raise errors.RemoteRunError(msg)
        except Exception, e:
            msg = 'Failed to load bundle for module %s' % module
            self.debug("exception %r" % e)
            self.warning(msg)
            raise errors.RemoteRunError(msg)

        try:
            proc = getattr(mod, function)
        except AttributeError:
            msg = 'No procedure named %s in module %s' % (function, module)
            self.warning(msg)
            raise errors.RemoteRunError(msg)

        try:
            self.debug('calling %r(%r, %r)' % (proc, args, kwargs))
            d = proc(*args, **kwargs)
        except Exception, e:
            # FIXME: make e.g. GStreamerError nicely serializable, without
            # printing ugly tracebacks
            msg = ('calling %s.%s(*args=%r, **kwargs=%r) failed: %s' % (
                module, function, args, kwargs,
                log.getExceptionMessage(e)))
            self.debug(msg)
            raise e
 
        yield d

        try:
            # only if d was actually a deferred will we get here
            # this is a bit nasty :/
            result = d.value()
            if not isinstance(result, messages.Result):
                msg = 'function %r returned a non-Result %r' % (
                    proc, result)
                raise errors.RemoteRunError(msg)

            self.debug('yielding result %r with failed %r' % (result,
                result.failed))
            yield result
        except Exception, e:
            # FIXME: make e.g. GStreamerError nicely serializable, without
            # printing ugly tracebacks
            msg = ('%s.%s(*args=%r, **kwargs=%r) failed: %s' % (
                module, function, args, kwargs,
                log.getExceptionMessage(e)))
            self.debug(msg)
            raise e
    remote_runFunction = defer_generator_method(remote_runFunction)

class Kid:
    """
    I am an abstraction of a job process started by the worker.
    """
    def __init__(self, pid, avatarId, type, moduleName, methodName, config,
                 bundles):
        self.pid = pid 
        self.avatarId = avatarId
        self.type = type
        self.moduleName = moduleName
        self.methodName = methodName
        self.config = config
        self.bundles = bundles

    # pid = protocol.transport.pid
    def getPid(self):
        return self.pid

class JobProcessProtocol(protocol.ProcessProtocol):
    def __init__(self, kindergarten):
        self.kindergarten = kindergarten
        self.pid = None

    def setPid(self, pid):
        self.pid = pid

    def processEnded(self, status):
        # vmethod implementation
        # status is an instance of failure.Failure
        # status.value is a twisted.internet.error.ProcessTerminated
        # status.value.status is the os.WAIT-like status value
        kg = self.kindergarten
        kg.removeKidByPid(self.pid)
        if status.value.exitCode is not None:
            kg.info("Reaped child job with pid %d, exit value %d" % (
                                self.pid, status.value.exitCode))
        signum = status.value.signal
        if signum is not None:
            if signum == signal.SIGSEGV:
                kg.warning("Job child with pid %d segfaulted" % self.pid)
                if not os.WCOREDUMP(status.value.status):
                    kg.warning(
                        "No core dump generated.  "\
                        "Were core dumps enabled at the start ?")
            else:
                kg.info(
                    "Reaped job child with pid %d signaled by signal %d" % (
                        self.pid, signum))
            if os.WCOREDUMP(status.value.status):
                kg.info("Core dumped")
                corepath = os.path.join(os.getcwd(), 'core.%d' % self.pid)
                if os.path.exists(corepath):
                    kg.info("Core file is probably %s" % corepath)

        self.setPid(None)
        
class Kindergarten(log.Loggable):
    """
    I spawn job processes.
    I live in the worker brain.
    """

    logCategory = 'workerbrain' # thomas: I don't like Kindergarten

    def __init__(self, options):
        """
        @param options: the optparse option instance of command-line options
        @type  options: dict
        """
        dirname = os.path.split(os.path.abspath(sys.argv[0]))[0]
        self.program = os.path.join(dirname, 'flumotion-worker')
        self.kids = {} # avatarId -> Kid
        self.options = options
        
    def play(self, avatarId, type, moduleName, methodName, config, bundles):
        """
        Create a kid and make it "play" by starting a job.
        Starts a component with the given name, of the given type, and
        the given config dictionary.

        This will spawn a new flumotion-job process.

        @param avatarId:   avatarId the component should use to log in
        @type  avatarId:   string
        @param type:       type of component to start
        @type  type:       string
        @param moduleName: name of the module to create the component from
        @type  moduleName: string
        @param methodName: the factory method to use to create the component
        @type  methodName: string
        @param config:     a configuration dictionary for the component
        @type  config:     dict
        @param bundles:    ordered list of (bundleName, bundlePath) for this
                           component
        @type bundles:     list of (str, str)
        """
        p = JobProcessProtocol(self)
        executable = os.path.join(os.path.dirname(sys.argv[0]), 'flumotion-job')
        if not os.path.exists(executable):
            self.error("Trying to spawn job process, but '%s' does not "
                       "exist" % executable)
        # Evil FIXME: make argv[0] of the kid insult the user
        argv = [executable, avatarId, getSocketPath()]
        childFDs={0:0, 1:1, 2:2}
        env={}
        env.update(os.environ)
        # FIXME: publicize log._FLU_DEBUG ?
        env['FLU_DEBUG'] = log._FLU_DEBUG
        process = reactor.spawnProcess(p, executable, env=env, args=argv,
            childFDs=childFDs)

        p.setPid(process.pid)

        self.kids[avatarId] = \
            Kid(process.pid, avatarId, type, moduleName, methodName, config,
                bundles)

    def getKid(self, avatarId):
        return self.kids[avatarId]
    
    def getKids(self):
        return self.kids.values()

    def removeKidByPid(self, pid):
        """
        Remove the kid from the kindergarten based on the pid.
        Called by the signal handler in the brain.

        @returns: whether or not a kid with that pid was removed
        @rtype: boolean
        """
        for path, kid in self.kids.items():
            if kid.getPid() == pid:
                self.debug('Removing kid with name %s and pid %d' % (
                    path, pid))
                del self.kids[path]
                return True

        self.warning('Asked to remove kid with pid %d but not found' % pid)
        return False

def getSocketPath():
    # FIXME: better way of getting at a tmp dir ?
    # this is insecure as well, fixme before 0.1.10
    return os.path.join('/tmp', "flumotion.worker.%d" % os.getpid())

# Similar to Vishnu, but for worker related classes
class WorkerBrain(log.Loggable):
    """
    I manage jobs and everything related.
    I live in the main worker process.
    """

    logCategory = 'workerbrain'

    def __init__(self, options):
        """
        @param options: the optparsed dictionary of command-line options
        @type  options: an object with attributes
        """
        self._port = None
        self._oldSIGTERMHandler = None # stored by installSIGTERMHandler
        self.options = options

        # we used to ignore SIGINT from here on down, but actually
        # the reactor catches these properly in both 1.3 and 2.0,
        # and in 2.0 setting it to ignore first will make the reactor
        # not catch it (because it compares to the default int handler)
        # signal.signal(signal.SIGINT, signal.SIG_IGN)

        self.manager_host = options.host
        self.manager_port = options.port
        self.manager_transport = options.transport

        self.workerName = options.name
        self.keycard = None
        
        self.kindergarten = Kindergarten(options)
        self.job_server_factory, self.job_heaven = self.setup()

        self.medium = WorkerMedium(self, self.options.feederports)
        self.worker_client_factory = WorkerClientFactory(self)

        self._createDeferreds = {}

    def login(self, keycard):
        # called by worker/main.py
        self.keycard = keycard
        self.worker_client_factory.startLogin(keycard)
                             
    def setup(self):
        # called from Init
        root = JobHeaven(self)
        dispatcher = JobDispatcher(root)
        # FIXME: we should hand a username and password to log in with to
        # the job process instead of allowing anonymous
        checker = checkers.FlexibleCredentialsChecker()
        checker.allowPasswordless(True)
        p = portal.Portal(dispatcher, [checker])
        job_server_factory = pb.PBServerFactory(p)
        self._port = reactor.listenUNIX(getSocketPath(), job_server_factory)

        return job_server_factory, root

    def teardown(self):
        """
        Clean up after setup()

        @Returns: a L{twisted.internet.defer.Deferred} that fires when
                  the teardown is completed
        """
        self.debug("cleaning up port %r" % self._port)
        return self._port.stopListening()

    # override log.Loggable method so we don't traceback
    def error(self, message):
        self.warning('Shutting down worker because of error:')
        self.warning(message)
        print >> sys.stderr, 'ERROR: %s' % message
        reactor.stop()

    # FIXME: this isn't necessary, we can just connect to the shutdown
    # event on the reactor, reducing a lot of complexity here...
    def installSIGTERMHandler(self):
        """
        Install our own signal handler for SIGTERM.
        This will call the currently installed one first, then shut down
        jobs.
        """
        self.debug("Installing SIGTERM handler")
        handler = signal.signal(signal.SIGTERM, self._SIGTERMHandler)
        if handler not in (signal.SIG_IGN, signal.SIG_DFL, None):
            self._oldSIGTERMHandler = handler

    def _SIGTERMHandler(self, signum, frame):
        self.info("Worker daemon received TERM signal, shutting down")
        self.debug("handling SIGTERM")
        self.debug("_SIGTERMHandler: shutting down jobheaven")
        d = self.job_heaven.shutdown()

        if self._oldSIGTERMHandler:
            if d:
                self.debug("chaining Twisted handler")
                d.addCallback(lambda result: self._oldSIGTERMHandler(signum, frame))
            else:
                self.debug("calling Twisted handler")
                self._oldSIGTERMHandler(signum, frame)

        self.debug("_SIGTERMHandler: done")

    def deferredCreate(self, avatarId):
        """
        Create and register a deferred for creating the given component.
        This deferred will be fired when the JobAvatar has instructed the
        job to create the component.
        """
        self.debug('making create deferred for %s' % avatarId)
        if avatarId in self._createDeferreds.keys():
            raise errors.ComponentAlreadyStartingError(avatarId)

        d = defer.Deferred()
        self._createDeferreds[avatarId] = d
        return d

    def deferredCreateTrigger(self, avatarId):
        """
        Trigger a previously registered deferred for creating up the given
        component.
        """
        self.debug('triggering create deferred for %s' % avatarId)
        if not avatarId in self._createDeferreds.keys():
            self.warning('No deferred create registered for %s' % avatarId)
            return

        d = self._createDeferreds[avatarId]
        del self._createDeferreds[avatarId]
        # return the avatarId the component will use to the original caller
        d.callback(avatarId)
 
    def deferredCreateFailed(self, avatarId, exception):
        """
        Notify the caller that a create has failed, and remove the create
        from the list of pending creates.
        """
        self.debug('deferred create failed for %s' % avatarId)
        assert avatarId in self._createDeferreds.keys()

        d = self._createDeferreds[avatarId]
        del self._createDeferreds[avatarId]
        d.errback(exception)
 
class JobDispatcher:
    """
    I am a Realm inside the worker for forked jobs to log in to.
    """
    __implements__ = portal.IRealm
    
    def __init__(self, root):
        """
        @type root: L{flumotion.worker.worker.JobHeaven}
        """
        self.root = root
        
    ### portal.IRealm methods
    # flumotion-worker job processes log in to us.
    # The mind is a RemoteReference which allows the brain to call back into
    # the job.
    # the avatar id is of the form /(parent)/(name) 
    def requestAvatar(self, avatarId, mind, *interfaces):
        if pb.IPerspective in interfaces:
            avatar = self.root.createAvatar(avatarId)
            reactor.callLater(0, avatar.attached, mind)
            return pb.IPerspective, avatar, avatar.logout
        else:
            raise NotImplementedError("no interface")

class JobAvatar(pb.Avatar, log.Loggable):
    """
    I am an avatar for the job living in the worker.
    """
    logCategory = 'job-avatar'

    def __init__(self, heaven, avatarId):
        """
        @type  heaven:   L{flumotion.worker.worker.JobHeaven}
        @type  avatarId: string
        """
        self.heaven = heaven
        self.avatarId = avatarId
        self.mind = None
        self.debug("created new JobAvatar")
            
    def hasRemoteReference(self):
        """
        Check if the avatar has a remote reference to the peer.

        @rtype: boolean
        """
        return self.mind != None

    def attached(self, mind):
        """
        @param mind: reference to the job's JobMedium on which we can call
        @type mind: L{twisted.spread.pb.RemoteReference}
        
        I am scheduled from the dispatcher's requestAvatar method.
        """
        self.mind = mind
        self.log('Client attached mind %s' % mind)
        host = self.heaven.brain.manager_host
        port = self.heaven.brain.manager_port
        transport = self.heaven.brain.manager_transport

        kid = self.heaven.brain.kindergarten.getKid(self.avatarId)

        d = self.mind.callRemote('bootstrap', self.heaven.getWorkerName(),
            host, port, transport, self.heaven.getKeycard(), kid.bundles)

        yield d
        d.value() # allow exceptions

        # we got kid.config through WorkerMedium.remote_start from the manager
        feedNames = kid.config.get('feed', [])
        self.log('feedNames: %r' % feedNames)

        self.debug('asking job to create component with config %r' % kid.config)
        d = self.mind.callRemote('create', kid.avatarId, kid.type,
            kid.moduleName, kid.methodName, kid.config)

        yield d
        try:
            d.value() # check for errors
            self.debug('job started component with avatarId %s' % kid.avatarId)
            self.heaven.brain.deferredCreateTrigger(kid.avatarId)
        except errors.ComponentCreateError, e:
            self.warning('could not create component %s of type %s: %r'
                         % (kid.avatarId, kid.type, e))
            self.heaven.brain.deferredCreateFailed(kid.avatarId, e)
        except Exception, e:
            self.warning('unhandled remote error: type %s, message %s'
                         % (e.__class__.__name__, e))
    attached = defer_generator_method(attached)

    def logout(self):
        self.log('logout called, %s disconnected' % self.avatarId)
        self.mind = None
        
    def stop(self):
        """
        returns: a deferred marking completed stop.
        """
        self.debug('stopping %s' % self.avatarId)
        if not self.mind:
            return defer.succeed(None)
        
        return self.mind.callRemote('stop')
        
    def remote_ready(self):
        pass

### this is a different kind of heaven, not IHeaven, for now...
class JobHeaven(pb.Root, log.Loggable):
    """
    I am similar to but not quite the same as a manager-side Heaven.
    I manage avatars inside the worker for job processes spawned by the worker.
    """
    logCategory = "job-heaven"
    def __init__(self, brain):
        self.avatars = {}
        self.brain = brain
        
    def createAvatar(self, avatarId):
        avatar = JobAvatar(self, avatarId)
        self.avatars[avatarId] = avatar
        return avatar

    def shutdown(self):
        self.debug('Shutting down JobHeaven')
        self.debug('Stopping all jobs')
        dl = defer.DeferredList([x.stop() for x in self.avatars.values()])
        dl.addCallback(lambda result: self.debug('Stopped all jobs'))
        return dl

    def getKeycard(self):
        """
        Gets the keycard that the worker used to log in to the manager.

        @rtype: L{flumotion.common.keycards.Keycard}
        """
        return self.brain.keycard

    def getWorkerName(self):
        """
        Gets the name of the worker that spawns the process.

        @rtype: str
        """
        return self.brain.workerName
