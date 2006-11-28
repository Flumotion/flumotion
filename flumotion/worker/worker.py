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

import os
import signal
import sys
import exceptions

import gst
import gst.interfaces

from twisted.cred import portal
from twisted.internet import defer, reactor
from twisted.spread import pb
import twisted.cred.error
import twisted.internet.error

from flumotion.common import errors, interfaces, log, bundleclient
from flumotion.common import common, medium, messages, worker
from flumotion.twisted import checkers, fdserver, compat
from flumotion.twisted import pb as fpb
from flumotion.twisted.defer import defer_generator_method
from flumotion.twisted.compat import implements
from flumotion.configure import configure
from flumotion.worker import feed

factoryClass = fpb.ReconnectingFPBClientFactory
class WorkerClientFactory(factoryClass):
    """
    I am a client factory for the worker to log in to the manager.
    """
    logCategory = 'worker'
    perspectiveInterface = interfaces.IWorkerMedium

    def __init__(self, brain):
        """
        @type brain: L{flumotion.worker.worker.WorkerBrain}
        """
        self._managerHost = brain.managerHost
        self._managerPort = brain.managerPort
        self.medium = brain.medium
        # doing this as a class method triggers a doc error
        factoryClass.__init__(self)
        # maximum 10 second delay for workers to attempt to log in again
        self.maxDelay = 10
        
    ### ReconnectingPBClientFactory methods
    def gotDeferredLogin(self, d):
        # the deferred from the login is now available
        # add some of our own to it
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
            self.error('Connection to %s:%d refused.' % (self._managerHost,
                                                         self._managerPort))
                                                          
        def NoSuchMethodErrback(failure):
            failure.trap(twisted.spread.flavors.NoSuchMethod)
            # failure.value is a str
            if failure.value.find('remote_getKeycardClasses') > -1:
                self.error(
                    "Manager %s:%d is older than version 0.3.0.  "
                    "Please upgrade." % (self._managerHost, self._managerPort))
                return

            return failure

        def loginFailedErrback(failure):
            self.error('Login failed, reason: %s' % str(failure))

        d.addCallback(loginCallback)
        d.addErrback(accessDeniedErrback)
        d.addErrback(connectionRefusedErrback)
        d.addErrback(alreadyConnectedErrback)
        d.addErrback(NoSuchMethodErrback)
        d.addErrback(loginFailedErrback)
            
    # override log.Loggable method so we don't traceback
    def error(self, message):
        self.warning('Shutting down worker because of error:')
        self.warning(message)
        print >> sys.stderr, 'ERROR: %s' % message
        reactor.stop()

class WorkerMedium(medium.PingingMedium):
    """
    I am a medium interfacing with the manager-side WorkerAvatar.

    @ivar brain: the worker brain
    @type brain: L{WorkerBrain}
    """
    
    logCategory = 'workermedium'

    implements(interfaces.IWorkerMedium)
    
    def __init__(self, brain, ports):
        """
        @type brain: L{WorkerBrain}
        """
        self.brain = brain
        self._ports = ports
        
    ### pb.Referenceable method for the manager's WorkerAvatar
    def remote_getPorts(self):
        """
        Gets the range of feed ports that this worker was configured to
        use.

        @rtype:  list of int
        @return: list of ports
        """
        return self._ports

    def remote_getFeedServerPort(self):
        """
        Return the TCP port the Feed Server is listening on.

        @rtype:  int
        @return: TCP port number
        """
        port = self.brain.feedServerPort
        return port

    def remote_create(self, avatarId, type, moduleName, methodName, nice=0):
        """
        Start a component of the given type with the given nice level.
        Will spawn a new job process to run the component in.

        @param avatarId:   avatar identification string
        @type  avatarId:   str
        @param type:       type of the component to create
        @type  type:       str
        @param moduleName: name of the module to create the component from
        @type  moduleName: str
        @param methodName: the factory method to use to create the component
        @type  methodName: str
        @param nice:       nice level
        @type  nice:       int

        @returns: a deferred fired when the process has started and created
                  the component
        """

        # from flumotion.common import debug
        # def write(indent, str, *args):
        #     print ('[%d]%s%s' % (os.getpid(), indent, str)) % args
        # debug.trace_start(ignore_files_re='twisted/python/rebuild',
        #      write=write)
        self.info('Starting component "%s" of type "%s"' % (avatarId, type))

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
            msg = ("Component '%s' has already received a create request"
                % avatarId)
            raise errors.ComponentCreateError(msg)

        # spawn the job process
        self.brain.kindergarten.play(avatarId, type, moduleName, methodName,
            nice, bundles)

        yield d

        try:
            result = d.value()
        except errors.ComponentCreateError, e:
            self.debug('create deferred for %s failed, forwarding error' %
                avatarId)
            raise
        self.debug('create deferred for %s succeeded (%r)'
                   % (avatarId, result))
        yield result
    remote_create = defer_generator_method(remote_create)

    def remote_checkElements(self, elementNames):
        """
        Checks if one or more GStreamer elements are present and can be
        instantiated.

        @param elementNames:   names of the Gstreamer elements
        @type  elementNames:   list of str

        @rtype:   list of str
        @returns: a list of instantiatable element names
        """
        self.debug('remote_checkElements: element names to check %r' % (
            elementNames,))

        list = []
        for name in elementNames:
            try:
                gst.element_factory_make(name)
                list.append(name)
            except gst.PluginNotFoundError:
                pass
        self.debug('remote_checkElements: returning elements names %r' % list)
        return list

    def remote_checkImport(self, moduleName):
        """
        Checks if the given module can be imported.

        @param moduleName: name of the module to check
        @type  moduleName: str

        @returns: None or Failure
        """
        self.debug('remote_checkImport: %s', moduleName)
        # FIXME: maybe find a nice way to check if we can import
        # without importing ?
        __import__(moduleName) 

    def remote_runFunction(self, module, function, *args, **kwargs):
        """
        Runs the given function in the given module with the given arguments.
        
        @param module:   module the function lives in
        @type  module:   str
        @param function: function to run
        @type  function: str

        @returns: the return value of the given function in the module.
        """
        return self.runBundledFunction(module, function, *args, **kwargs)

    def remote_getComponents(self):
        """
        I return a list of componentAvatarIds, I have.  I am called by the
        manager soon after I attach to it.  This is needed on reconnects
        so that the manager knows what components it needs to start on me.

        @returns: a list of componentAvatarIds
        """
        return self.brain.kindergarten.getKidAvatarIds()

class Kid:
    """
    I am an abstraction of a job process started by the worker.

    @cvar  pid:        PID of the child process
    @type  pid:        int
    @cvar  avatarId:   avatar identification string
    @type  avatarId:   str
    @cvar  type:       type of the component to create
    @type  type:       str
    @cvar  moduleName: name of the module to create the component from
    @type  moduleName: str
    @cvar  methodName: the factory method to use to create the component
    @type  methodName: str
    @cvar  nice:       the nice level to run the kid as
    @type  nice:       int
    @cvar  bundles:    ordered list of (bundleName, bundlePath) needed to
                       create the component
    @type  bundles:    list of (str, str)
    """
    def __init__(self, pid, avatarId, type, moduleName, methodName, nice,
                 bundles):
        self.pid = pid 
        self.avatarId = avatarId
        self.type = type
        self.moduleName = moduleName
        self.methodName = methodName
        self.nice = nice
        self.bundles = bundles

class JobProcessProtocol(worker.ProcessProtocol):
    def __init__(self, kindergarten, avatarId):
        worker.ProcessProtocol.__init__(self, kindergarten, avatarId,
                                        'component',
                                        kindergarten.brain.workerName)

    def sendMessage(self, message):
        kg = self.loggable
        kg.brain.callRemote('componentAddMessage', self.avatarId,
                                  message)

    def processEnded(self, status):
        kg = self.loggable
        signum = status.value.signal

        kg.removeKidByPid(self.pid)

        if signum is not None:
            # we need to trigger a failure on the create deferred 
            # if the job received a signal before logging in to the worker;
            # otherwise the manager still thinks it's starting up when it's
            # dead.  If the job already attached to the worker however,
            # the create deferred will already have callbacked.
            if kg.brain.deferredCreateRegistered(self.avatarId):
                text = "Component '%s' has received signal %d.  " \
                       "This is sometimes triggered by a corrupt " \
                       "GStreamer registry." % (self.avatarId, signum)
                kg.brain.deferredCreateFailed(self.avatarId, 
                    errors.ComponentCreateError(text))

        kg.brain.jobHeaven.lostAvatar(self.avatarId)
        if kg.brain.deferredShutdownRegistered(self.avatarId):
            kg.brain.deferredShutdownTrigger(self.avatarId)

        # chain up
        worker.ProcessProtocol.processEnded(self, status)
        
class Kindergarten(log.Loggable):
    """
    I spawn job processes.
    I live in the worker brain.
    """

    logCategory = 'workerbrain' # thomas: I don't like Kindergarten

    def __init__(self, options, socketPath, brain):
        """
        @param options:     the optparse option instance of command-line options
        @type  options:     dict
        @param socketPath:  the path of the Unix domain socket for PB
        @type  socketPath:  str
        @param brain:       a reference to the worker brain
        @type  brain:       L{WorkerBrain}
        """
        self.brain = brain
        self.options = options

        self._kids = {} # avatarId -> Kid
        self._socketPath = socketPath
        
    def play(self, avatarId, type, moduleName, methodName, nice, bundles):
        """
        Create a kid and make it "play" by starting a job.
        Starts a component with the given name, of the given type, with
        the given nice level.

        This will spawn a new flumotion-job process.

        @param avatarId:   avatarId the component should use to log in
        @type  avatarId:   str
        @param type:       type of component to start
        @type  type:       str
        @param moduleName: name of the module to create the component from
        @type  moduleName: str
        @param methodName: the factory method to use to create the component
        @type  methodName: str
        @param nice:       nice level
        @type  nice:       int
        @param bundles:    ordered list of (bundleName, bundlePath) for this
                           component
        @type  bundles:    list of (str, str)
        """
        p = JobProcessProtocol(self, avatarId)
        executable = os.path.join(os.path.dirname(sys.argv[0]), 'flumotion-job')
        if not os.path.exists(executable):
            self.error("Trying to spawn job process, but '%s' does not "
                       "exist" % executable)
        # Evil FIXME: make argv[0] of the kid insult the user
        argv = [executable, avatarId, self._socketPath]

        realexecutable = executable

        # Run some jobs under valgrind, optionally. Would be nice to have the
        # arguments to run it with configurable, but this'll do for now.
        # FLU_VALGRIND_JOB takes a comma-seperated list of full component
        # avatar IDs.
        if os.environ.has_key('FLU_VALGRIND_JOB'):
            jobnames = os.environ['FLU_VALGRIND_JOB'].split(',')
            if avatarId in jobnames:
                realexecutable = 'valgrind'
                # We can't just valgrind flumotion-job, we have to valgrind
                # python running flumotion-job, otherwise we'd need 
                # --trace-children (not quite sure why), which we don't want
                argv = ['valgrind', '--leak-check=full', '--num-callers=24', 
                    '--leak-resolution=high', '--show-reachable=yes', 
                    'python'] + argv

        childFDs = {0: 0, 1: 1, 2: 2}
        env = {}
        env.update(os.environ)
        # FIXME: publicize log._FLU_DEBUG ?
        env['FLU_DEBUG'] = log._FLU_DEBUG
        process = reactor.spawnProcess(p, realexecutable, env=env, args=argv,
            childFDs=childFDs)

        p.setPid(process.pid)

        self._kids[avatarId] = \
            Kid(process.pid, avatarId, type, moduleName, methodName, nice,
                bundles)

    def getKid(self, avatarId):
        return self._kids[avatarId]
    
    def getKids(self):
        return self._kids.values()

    def getKidAvatarIds(self):
        return self._kids.keys()

    def removeKidByPid(self, pid):
        """
        Remove the kid from the kindergarten based on the pid.
        Called by the signal handler in the brain.

        @returns: whether or not a kid with that pid was removed
        @rtype: boolean
        """
        for path, kid in self._kids.items():
            if kid.pid == pid:
                self.debug('Removing kid with name %s and pid %d' % (
                    path, pid))
                del self._kids[path]
                return True

        self.warning('Asked to remove kid with pid %d but not found' % pid)
        return False

def _getSocketPath():
    # FIXME: there is mkstemp for sockets, so we have a small window
    # here in which the socket could be created by something else
    # I didn't succeed in preparing a socket file with that name either

    # caller needs to delete name before using
    import tempfile
    fd, name = tempfile.mkstemp('.%d' % os.getpid(), 'flumotion.worker.')
    os.close(fd)
    
    return name

# Similar to Vishnu, but for worker related classes
class WorkerBrain(log.Loggable):
    """
    I am the main object in the worker process, managing jobs and everything
    related.
    I live in the main worker process.

    @ivar authenticator:       authenticator worker used to log in to manager
    @type authenticator        L{flumotion.twisted.pb.Authenticator}
    @ivar kindergarten:
    @type kindergarten:        L{Kindergarten}
    @ivar medium:
    @type medium:              L{WorkerMedium}
    @ivar jobHeaven:
    @type jobHeaven:           L{JobHeaven}
    @ivar workerClientFactory:
    @type workerClientFactory: L{WorkerClientFactory}
    @ivar feedServerPort:      TCP port the Feed Server is listening on
    @type feedServerPort:      int
    """

    compat.implements(interfaces.IFeedServerParent)

    logCategory = 'workerbrain'

    def __init__(self, options):
        """
        @param options: the optparsed dictionary of command-line options
        @type  options: an object with attributes
        """
        self.options = options
        self.workerName = options.name

        self.managerHost = options.host
        self.managerPort = options.port
        self.managerTransport = options.transport
        
        self.authenticator = None
        # the last one is reserved for our FeedServer
        self.medium = WorkerMedium(self, self.options.feederports[:-1])
        self._socketPath = _getSocketPath()
        self.kindergarten = Kindergarten(options, self._socketPath, self)
        self.jobHeaven = JobHeaven(self)
        self.workerClientFactory = WorkerClientFactory(self)

        self._port = None # port for unix domain socket, set from _setup
        self._oldSIGTERMHandler = None # stored by installSIGTERMHandler

        # we used to ignore SIGINT from here on down, but actually
        # the reactor catches these properly in both 1.3 and 2.0,
        # and in 2.0 setting it to ignore first will make the reactor
        # not catch it (because it compares to the default int handler)
        # signal.signal(signal.SIGINT, signal.SIG_IGN)

        self._jobServerFactory, self._jobServerPort = self._setupJobServer()
        self._feedServerFactory = feed.feedServerFactory(self)

        # set up feed server if we have the feederports for it
        self._feedServerPort = None # twisted port
        self.feedServerPort = None # port number
        self._setupFeedServer()

        self._createDeferreds = {} # avatarId => deferred that will fire
                                   # when the job attaches
        self._shutdownDeferreds = {} # avatarId => deferred for shutting
                                   # down jobs; fires when job is reaped

    def login(self, authenticator):
        self.authenticator = authenticator
        self.workerClientFactory.startLogin(authenticator)

    def _setupJobServer(self):
        """
        @returns: (factory, port)
        """
        # called from __init__
        dispatcher = JobDispatcher(self.jobHeaven)
        # FIXME: we should hand a username and password to log in with to
        # the job process instead of allowing anonymous
        checker = checkers.FlexibleCredentialsChecker()
        checker.allowPasswordless(True)
        p = portal.Portal(dispatcher, [checker])
        f = pb.PBServerFactory(p)
        try:
            os.unlink(self._socketPath)
        except:
            pass

        # Rather than a listenUNIX(), we use listenWith so that we can specify
        # our particular Port, which creates Transports that we know how to
        # pass FDs over.
        port = reactor.listenWith(fdserver.FDPort, self._socketPath, f)

        return f, port

    def _setupFeedServer(self):
        """
        @returns: (port, portNumber)
        """
        # called from __init__
        try:
            self.feedServerPort = self.options.feederports[-1]
        except IndexError:
            self.info('Not starting feed server because no port is configured')
            return

        self.debug('Listening for feed requests on TCP port %s' %
            self.feedServerPort)
        self._feedServerPort = reactor.listenWith(
            fdserver.PassableServerPort, self.feedServerPort, 
            self._feedServerFactory)

    # FIXME: this is only called from the tests
    def teardown(self):
        """
        Clean up after setup()

        @Returns: a L{twisted.internet.defer.Deferred} that fires when
                  the teardown is completed
        """
        self.debug("cleaning up port %r" % self._port)
        d = self._jobServerPort.stopListening()
        d.addCallback(lambda r: self._feedServerPort.stopListening())
        return d

    # override log.Loggable method so we don't traceback
    def error(self, message):
        self.warning('Shutting down worker because of error:')
        self.warning(message)
        print >> sys.stderr, 'ERROR: %s' % message
        reactor.stop()

    def callRemote(self, methodName, *args, **kwargs):
        return self.medium.callRemote(methodName, *args, **kwargs)

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
        d = self.jobHeaven.shutdown()

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

        @rtype: L{twisted.internet.defer.Deferred}
        """
        self.debug('making create deferred for %s' % avatarId)

        d = defer.Deferred()

        # the question of "what jobs do we know about" is answered in
        # three places: the create deferreds hash, the avatar list in
        # the jobheaven, and the shutdown deferreds hash. there are four
        # possible answers:
        if avatarId in self._createDeferreds:
            # (1) a job is already starting: it is in the
            # createdeferreds hash
            self.info('already have a create deferred for %s', avatarId)
            raise errors.ComponentAlreadyStartingError(avatarId)
        elif avatarId in self._shutdownDeferreds:
            # (2) a job is shutting down; note it is also in
            # heaven.avatars
            self.debug('waiting for previous %s to shut down like it '
                       'said it would', avatarId)
            def ensureShutdown(res,
                               shutdown=self._shutdownDeferreds[avatarId]):
                shutdown.addCallback(lambda _: res)
                return shutdown
            d.addCallback(ensureShutdown)
        elif avatarId in self.jobHeaven.avatars:
            # (3) a job is running fine
            self.info('avatar named %s already running', avatarId)
            raise errors.ComponentAlreadyRunningError(avatarId)
        else:
            # (4) it's new; we know of nothing with this avatarId
            pass

        self.debug('registering deferredCreate for %s', avatarId)
        self._createDeferreds[avatarId] = d
        return d

    def deferredCreateTrigger(self, avatarId):
        """
        Trigger a previously registered deferred for creating up the given
        component.
        """
        self.debug('triggering create deferred for %s' % avatarId)
        if not avatarId in self._createDeferreds:
            self.warning('No create deferred registered for %s' % avatarId)
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
        self.debug('create deferred failed for %s' % avatarId)
        if not avatarId in self._createDeferreds:
            self.warning('No create deferred registered for %s' % avatarId)
            return

        d = self._createDeferreds[avatarId]
        del self._createDeferreds[avatarId]
        d.errback(exception)

    def deferredCreateRegistered(self, avatarId):
        """
        Check if a deferred create has been registered for the given avatarId.
        """
        return avatarId in self._createDeferreds

    def deferredShutdown(self, avatarId):
        """
        Create and register a deferred for notifying the worker of a
        clean job shutdown. This deferred will be fired when the job is
        reaped.

        @rtype: L{twisted.internet.defer.Deferred}
        """
        self.debug('making shutdown deferred for %s' % avatarId)

        if avatarId in self._shutdownDeferreds:
            self.warning('already have a shutdown deferred for %s',
                         avatarId)
            return self._shutdownDeferreds[avatarId]
        else:
            self.debug('registering deferredShutdown for %s', avatarId)
            d = defer.Deferred()
            self._shutdownDeferreds[avatarId] = d
            return d

    def deferredShutdownTrigger(self, avatarId):
        """
        Trigger a previously registered deferred for creating up the given
        component.
        """
        self.debug('triggering shutdown deferred for %s', avatarId)
        if not avatarId in self._shutdownDeferreds:
            self.warning('No shutdown deferred registered for %s', avatarId)
            return

        d = self._shutdownDeferreds.pop(avatarId)
        d.callback(avatarId)

    def deferredShutdownRegistered(self, avatarId):
        """
        Check if a deferred shutdown has been registered for the given avatarId.
        """
        return avatarId in self._shutdownDeferreds

    ### IFeedServerParent methods
    def feedToFD(self, componentId, feedName, fd, eaterId):
        """
        Called from the FeedAvatar to pass a file descriptor on to
        the job running the component for this feeder.

        @returns: whether the fd was successfully handed off to the component.
        """
        avatar = self.jobHeaven.avatars[componentId]
        return avatar.sendFeed(feedName, fd, eaterId)

    def eatFromFD(self, componentId, feedId, fd):
        """
        Called from the FeedAvatar to pass a file descriptor on to
        the job running the given component.

        @returns: whether the fd was successfully handed off to the component.
        """
        avatar = self.jobHeaven.avatars[componentId]
        return avatar.receiveFeed(feedId, fd)
   
class JobDispatcher:
    """
    I am a Realm inside the worker for forked jobs to log in to.
    """
    implements(portal.IRealm)
    
    def __init__(self, root):
        """
        @type root: L{flumotion.worker.worker.JobHeaven}
        """
        self._root = root
        
    ### portal.IRealm methods
    # flumotion-worker job processes log in to us.
    # The mind is a RemoteReference which allows the brain to call back into
    # the job.
    # the avatar id is of the form /(parent)/(name) 
    def requestAvatar(self, avatarId, mind, *interfaces):
        if pb.IPerspective in interfaces:
            avatar = self._root.createAvatar(avatarId)
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
        @type  avatarId: str
        """
        self.avatarId = avatarId
        self.logName = avatarId
        self._heaven = heaven
        self._mind = None
        self.debug("created new JobAvatar")
            
    def hasRemoteReference(self):
        """
        Check if the avatar has a remote reference to the peer.

        @rtype: boolean
        """
        return self._mind != None

    def attached(self, mind):
        """
        @param mind: reference to the job's JobMedium on which we can call
        @type  mind: L{twisted.spread.pb.RemoteReference}
        
        I am scheduled from the dispatcher's requestAvatar method.
        """
        self._mind = mind
        self.log('Client attached mind %s' % mind)
        host = self._heaven.brain.managerHost
        port = self._heaven.brain.managerPort
        transport = self._heaven.brain.managerTransport

        kid = self._heaven.brain.kindergarten.getKid(self.avatarId)

        d = self._mind.callRemote('bootstrap', self._heaven.getWorkerName(),
            host, port, transport, self._heaven.getAuthenticator(), kid.bundles)

        yield d
        d.value() # allow exceptions

        self.debug(
            "asking job to create component with avatarId %s, type %s" % (
                kid.avatarId, kid.type))
        d = self._mind.callRemote('create', kid.avatarId, kid.type,
            kid.moduleName, kid.methodName, kid.nice)

        yield d
        try:
            d.value() # check for errors
            self.debug('job started component with avatarId %s' % kid.avatarId)
            self._heaven.brain.deferredCreateTrigger(kid.avatarId)
        except errors.ComponentCreateError, e:
            self.warning('could not create component %s of type %s: %r'
                         % (kid.avatarId, kid.type, e))
            self._heaven.brain.deferredCreateFailed(kid.avatarId, e)
        except Exception, e:
            self.warning('unhandled remote error: type %s, message %s'
                         % (e.__class__.__name__, e))
            self._heaven.brain.deferredCreateFailed(kid.avatarId, e)
    attached = defer_generator_method(attached)

    def logout(self):
        self.log('logout called, %s disconnected' % self.avatarId)
        self._mind = None
        
    def stop(self):
        """
        returns: a deferred marking completed stop.
        """
        self.debug('stopping %s' % self.avatarId)
        if not self._mind:
            return defer.succeed(None)
        
        return self._mind.callRemote('stop')
        
    def remote_ready(self):
        pass

    def sendFeed(self, feedName, fd, eaterId):
        """
        Tell the feeder to send the given feed to the given fd.

        @returns: whether the fd was successfully handed off to the component.
        """
        self.debug('Sending FD %d to component job to feed %s to fd' % (
            fd, feedName))

        # it is possible that the component has logged out, in which case
        # we don't have a _mind.  Trying to check for this earlier only
        # introduces a race, so we handle it here by triggering a disconnect
        # on the fd.
        if self._mind:
            try:
                self._mind.broker.transport.sendFileDescriptor(
                    fd, "sendFeed %s %s" % (feedName, eaterId))
                return True
            except exceptions.RuntimeError, e:
                # RuntimeError is what is thrown by the C code doing this
                # when there are issues
                self.debug("We got a Runtime Error %s sending file descriptors.",
                    log.getExceptionMessage(e))
                return False
        self.debug('my mind is gone, trigger disconnect')
        return False

    # FIXME: why do we ignore return value of sendFileDescriptor???
    def receiveFeed(self, feedId, fd):
        """
        Tell the feeder to receive the given feed from the given fd.

        @returns: whether the fd was successfully handed off to the component.
        """
        self.debug('Sending FD %d to component job to eat %s from fd' % (
            fd, feedId))
        try:
            self._mind.broker.transport.sendFileDescriptor(
                fd, "receiveFeed %s" % feedId)
            return True
        except exceptions.RuntimeError, e:
            # RuntimeError is what is thrown by the C code doing this
            # when there are issues
            self.debug("We got a Runtime Error %s sending file descriptors.",
                log.getExceptionMessage(e))
            return False

    def perspective_cleanShutdown(self):
        """
        This notification from the job process will be fired when it is
        shutting down, so that although the process might still be
        around, we know it's OK to accept new start requests for this
        avatar ID.
        """
        self.info("component %s shutting down cleanly", self.avatarId)
        self._heaven.brain.deferredShutdown(self.avatarId)

### this is a different kind of heaven, not IHeaven, for now...
class JobHeaven(pb.Root, log.Loggable):
    """
    I am similar to but not quite the same as a manager-side Heaven.
    I manage avatars inside the worker for job processes spawned by the worker.

    @ivar avatars: dict of avatarId -> avatar
    @type avatars: dict of str -> L{JobAvatar}
    @ivar brain:   the worker brain
    @type brain:   L{WorkerBrain}
    """
    logCategory = "job-heaven"
    def __init__(self, brain):
        """
        @type brain: L{WorkerBrain}
        """
        self.avatars = {} # componentId -> avatar
        self.brain = brain
        
    def createAvatar(self, avatarId):
        avatar = JobAvatar(self, avatarId)
        self.avatars[avatarId] = avatar
        return avatar

    def lostAvatar(self, avatarId):
        if avatarId not in self.avatars:
            self.warning("some programmer is telling me about an avatar "
                         "I have no idea about: %s", avatarId)
        else:
            return self.avatars.pop(avatarId)

    def shutdown(self):
        self.debug('Shutting down JobHeaven')
        self.debug('Stopping all jobs')
        dl = defer.DeferredList([x.stop() for x in self.avatars.values()])
        dl.addCallback(lambda result: self.debug('Stopped all jobs'))
        return dl

    def getAuthenticator(self):
        """
        Gets the authenticator that the worker used to log in to the manager.

        @rtype: L{flumotion.twisted.pb.Authenticator}
        """
        return self.brain.authenticator

    def getWorkerName(self):
        """
        Gets the name of the worker that spawns the process.

        @rtype: str
        """
        return self.brain.workerName
