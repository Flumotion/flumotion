# -*- Mode: Python; test-case-name:flumotion.test.test_worker_worker -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# Flumotion - a streaming media server
# Copyright (C) 2004,2005,2006,2007 Fluendo, S.L. (www.fluendo.com).
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
import sys
import signal

from twisted.cred import portal
from twisted.internet import defer, reactor
from twisted.spread import pb
from zope.interface import implements

from flumotion.common import errors, log
from flumotion.common import common, worker
from flumotion.twisted import checkers, fdserver
from flumotion.twisted import pb as fpb

JOB_SHUTDOWN_TIMEOUT = 5

def _getSocketPath():
    # FIXME: there is mkstemp for sockets, so we have a small window
    # here in which the socket could be created by something else
    # I didn't succeed in preparing a socket file with that name either

    # caller needs to delete name before using
    import tempfile
    fd, name = tempfile.mkstemp('.%d' % os.getpid(), 'flumotion.worker.')
    os.close(fd)
    
    return name

class JobInfo(object):
    """
    I hold information about a job.

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
    @cvar  nice:       the nice level to run the job as
    @type  nice:       int
    @cvar  bundles:    ordered list of (bundleName, bundlePath) needed to
                       create the component
    @type  bundles:    list of (str, str)
    """
    __slots__ = ('pid', 'avatarId', 'type', 'moduleName', 'methodName',
                 'nice', 'bundles')
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
    def __init__(self, heaven, avatarId, deferredStarts):
        self._deferredStarts = deferredStarts
        self._deferredStart = deferredStarts.createRegistered(avatarId)
        worker.ProcessProtocol.__init__(self, heaven, avatarId,
                                        'component',
                                        heaven.brain.workerName)

    def sendMessage(self, message):
        heaven = self.loggable
        heaven.brain.callRemote('componentAddMessage', self.avatarId,
                                message)

    def processEnded(self, status):
        heaven = self.loggable
        dstarts = self._deferredStarts
        signum = status.value.signal

        # we need to trigger a failure on the create deferred 
        # if the job failed before logging in to the worker;
        # otherwise the manager still thinks it's starting up when it's
        # dead.  If the job already attached to the worker however,
        # the create deferred will already have callbacked.
        deferred = dstarts.createRegistered(self.avatarId)
        if deferred is self._deferredStart:
            if signum:
                reason = "received signal %d" % signum
            else:
                reason = "unknown reason"
            text = "Component '%s' has exited early (%s).  " \
                   "This is sometimes triggered by a corrupt " \
                   "GStreamer registry." % (self.avatarId, reason)
            dstarts.createFailed(self.avatarId, 
                                 errors.ComponentCreateError(text))

        if dstarts.shutdownRegistered(self.avatarId):
            dstarts.shutdownTrigger(self.avatarId)

        heaven.jobStopped(self.pid)

        # chain up
        worker.ProcessProtocol.processEnded(self, status)
        
class DeferredStartSet(log.Loggable):
    def __init__(self, getAvatars):
        self._getAvatars = getAvatars # function of no arguments,
                                      # returns {avatarId=>avatar}

        self._createDeferreds = {} # avatarId => deferred that will fire
                                   # when the job attaches
        self._shutdownDeferreds = {} # avatarId => deferred for shutting
                                   # down jobs; fires when job is reaped

    def create(self, avatarId):
        """
        Create and register a deferred for creating the given component.
        This deferred will be fired when the JobAvatar has instructed the
        job to create the component.

        @rtype: L{twisted.internet.defer.Deferred}
        """
        self.debug('making create deferred for %s', avatarId)

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
        elif avatarId in self._getAvatars():
            # (3) a job is running fine
            self.info('avatar named %s already running', avatarId)
            raise errors.ComponentAlreadyRunningError(avatarId)
        else:
            # (4) it's new; we know of nothing with this avatarId
            pass

        self.debug('registering deferredCreate for %s', avatarId)
        self._createDeferreds[avatarId] = d
        return d

    def createTrigger(self, avatarId):
        """
        Trigger a previously registered deferred for creating up the given
        component.
        """
        self.debug('triggering create deferred for %s', avatarId)
        if not avatarId in self._createDeferreds:
            self.warning('No create deferred registered for %s', avatarId)
            return

        d = self._createDeferreds[avatarId]
        del self._createDeferreds[avatarId]
        # return the avatarId the component will use to the original caller
        d.callback(avatarId)
 
    def createFailed(self, avatarId, exception):
        """
        Notify the caller that a create has failed, and remove the create
        from the list of pending creates.
        """
        self.debug('create deferred failed for %s', avatarId)
        if not avatarId in self._createDeferreds:
            self.warning('No create deferred registered for %s', avatarId)
            return

        d = self._createDeferreds[avatarId]
        del self._createDeferreds[avatarId]
        d.errback(exception)

    def createRegistered(self, avatarId):
        """
        Check if a deferred create has been registered for the given avatarId,
        and return it or none
        """
        return self._createDeferreds.get(avatarId, None)

    def shutdown(self, avatarId):
        """
        Create and register a deferred for notifying the worker of a
        clean job shutdown. This deferred will be fired when the job is
        reaped.

        @rtype: L{twisted.internet.defer.Deferred}
        """
        self.debug('making shutdown deferred for %s', avatarId)

        if avatarId in self._shutdownDeferreds:
            self.warning('already have a shutdown deferred for %s',
                         avatarId)
            return self._shutdownDeferreds[avatarId]
        else:
            self.debug('registering shutdown for %s', avatarId)
            d = defer.Deferred()
            self._shutdownDeferreds[avatarId] = d
            return d

    def shutdownTrigger(self, avatarId):
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

    def shutdownRegistered(self, avatarId):
        """
        Check if a deferred shutdown has been registered for the given avatarId.
        """
        return avatarId in self._shutdownDeferreds

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
    implements(portal.IRealm)

    def __init__(self, brain):
        """
        @param brain:       a reference to the worker brain
        @type  brain:       L{WorkerBrain}
        @param socketPath:  the path of the Unix domain socket for PB
        @type  socketPath:  str
        """
        self.avatars = {} # componentId -> avatar
        self.brain = brain
        self._socketPath = _getSocketPath()
        self._port = None
        self._onShutdown = None # If set, a deferred to fire when our last child
                                # process exits

        self._jobInfos = {} # processid -> JobInfo

        self._deferredStarts = DeferredStartSet(lambda: self.avatars)

    def listen(self):
        assert self._port is None
        # FIXME: we should hand a username and password to log in with to
        # the job process instead of allowing anonymous
        checker = checkers.FlexibleCredentialsChecker()
        checker.allowPasswordless(True)
        p = portal.Portal(self, [checker])
        f = pb.PBServerFactory(p)
        try:
            os.unlink(self._socketPath)
        except:
            pass

        # Rather than a listenUNIX(), we use listenWith so that we can specify
        # our particular Port, which creates Transports that we know how to
        # pass FDs over.
        port = reactor.listenWith(fdserver.FDPort, self._socketPath, f)
        self._port = port
        
    ### portal.IRealm method
    def requestAvatar(self, avatarId, mind, *interfaces):
        if pb.IPerspective in interfaces:
            avatar = JobAvatar(self, avatarId, mind)
            self.avatars[avatarId] = avatar
            return pb.IPerspective, avatar, avatar.logout
        else:
            raise NotImplementedError("no interface")

    def removeAvatar(self, avatarId):
        if avatarId in self.avatars:
            del self.avatars[avatarId]
        else:
            self.warning("some programmer is telling me about an avatar "
                         "I have no idea about: %s", avatarId)

    def getManagerConnectionInfo(self):
        """
        Gets the L{flumotion.common.connection.PBConnectionInfo}
        describing how to connect to the manager.

        @rtype: L{flumotion.common.connection.PBConnectionInfo}
        """
        return self.brain.managerConnectionInfo

    def getWorkerName(self):
        """
        Gets the name of the worker that spawns the process.

        @rtype: str
        """
        return self.brain.workerName

    def spawn(self, avatarId, type, moduleName, methodName, nice, bundles):
        """
        Spawn a new job.

        This will spawn a new flumotion-job process, running under the
        requested nice level. When the job logs in, it will be told to
        load bundles and run a function, which is expected to return a
        component.

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
        d = self._deferredStarts.create(avatarId)

        p = JobProcessProtocol(self, avatarId, self._deferredStarts)
        executable = os.path.join(os.path.dirname(sys.argv[0]), 'flumotion-job')
        if not os.path.exists(executable):
            self.error("Trying to spawn job process, but '%s' does not "
                       "exist", executable)
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
        env['FLU_DEBUG'] = log.getDebug()
        process = reactor.spawnProcess(p, realexecutable, env=env, args=argv,
            childFDs=childFDs)

        p.setPid(process.pid)

        jobInfo = JobInfo(process.pid, avatarId, type, moduleName,
                          methodName, nice, bundles)
        self._jobInfos[process.pid] = jobInfo
        return d

    def getJobInfo(self, processId):
        return self._jobInfos[processId]

    def getJobInfos(self):
        return self._jobInfos.values()
    
    def getJobPids(self):
        return self._jobInfos.keys()

    def rotateChildLogFDs(self):
        self.debug('telling kids about new log file descriptors')
        for avatar in self.avatars.values():
            avatar.logTo(sys.stdout.fileno(), sys.stderr.fileno())

    def jobStopped(self, pid):
        if pid in self._jobInfos:
            self.debug('Removing job info for %d', pid)
            del self._jobInfos[pid]

            if not self._jobInfos and self._onShutdown:
                self.debug("Last child exited")
                self._onShutdown.callback(None)
        else:
            self.warning("some programmer is telling me about a pid "
                         "I have no idea about: %d", pid)

    def shutdown(self):
        self.debug('Shutting down JobHeaven')
        self.debug('Stopping all jobs')
        for avatar in self.avatars.values():
            avatar.stop()

        if self.avatars:
            # If our jobs fail to shut down nicely within some period of
            # time, shut them down less nicely
            dc = reactor.callLater(JOB_SHUTDOWN_TIMEOUT, self.kill)
            def cancelDelayedCall(res, dc):
                # be nice to unit tests
                if dc.active():
                    dc.cancel()
                return res

            self._onShutdown = defer.Deferred()
            self._onShutdown.addCallback(cancelDelayedCall, dc)
            ret = self._onShutdown
        else:
            # everything's gone already, return success
            ret = defer.succeed(None)

        def stopListening(_):
            # possible for it to be None, if we haven't been told to
            # listen yet, as in some test cases
            if self._port:
                port = self._port
                self._port = None
                return port.stopListening()
        ret.addCallback(stopListening)
        return ret

    def kill(self, signum=signal.SIGKILL):
        self.warning("Killing all children immediately")
        for pid in self.getJobPids():
            self.killJobByPid(pid, signum)

    def killJobByPid(self, pid, signum):
        if pid not in self._jobInfos:
            raise errors.UnknownComponentError(pid)

        jobInfo = self._jobInfos[pid]
        self.debug("Sending signal %d to job %s at pid %d", signum,
                   jobInfo.avatarId, jobInfo.pid)
        common.signalPid(jobInfo.pid, signum)

    def killJob(self, avatarId, signum):
        for job in self.jobInfos.values():
            if job.avatarId == avatarId:
                self.killJobByPid(job.pid, signum)

class JobAvatar(fpb.Avatar, log.Loggable):
    """
    I am an avatar for the job living in the worker.
    """
    logCategory = 'job-avatar'

    def __init__(self, heaven, avatarId, mind):
        """
        @type  heaven:   L{flumotion.worker.worker.JobHeaven}
        @type  avatarId: str
        """
        fpb.Avatar.__init__(self, avatarId)
        self._heaven = heaven
        self.setMind(mind)
        self.pid = None
            
    def setMind(self, mind):
        """
        @param mind: reference to the job's JobMedium on which we can call
        @type  mind: L{twisted.spread.pb.RemoteReference}
        """
        fpb.Avatar.setMind(self, mind)

        def bootstrap(*args):
            return self.mindCallRemote('bootstrap', *args)

        def create(_, job):
            self.debug("asking job to create component with avatarId %s,"
                       " type %s", job.avatarId, job.type)
            return self.mindCallRemote('create', job.avatarId, job.type,
                                       job.moduleName, job.methodName,
                                       job.nice)

        def success(_, avatarId):
            self.debug('job started component with avatarId %s',
                       avatarId)
            # FIXME: drills down too much?
            self._heaven._deferredStarts.createTrigger(avatarId)

        def error(failure, job):
            msg = log.getFailureMessage(failure)
            if failure.check(errors.ComponentCreateError):
                self.warning('could not create component %s of type %s:'
                             ' %s', job.avatarId, job.type, msg)
            else:
                self.warning('unhandled error creating component %s: %s',
                             job.avatarId, msg)
            # FIXME: drills down too much?
            self._heaven._deferredStarts.createFailed(job.avatarId, failure)

        def gotPid(pid):
            self.pid = pid
            info = self._heaven.getManagerConnectionInfo()
            if info.use_ssl:
                transport = 'ssl'
            else:
                transport = 'tcp'
            job = self._heaven.getJobInfo(pid)
            workerName = self._heaven.getWorkerName()

            d = bootstrap(workerName, info.host, info.port, transport,
                          info.authenticator, job.bundles)
            d.addCallback(create, job)
            d.addCallback(success, job.avatarId)
            d.addErrback(error, job)
            return d
        d = self.mindCallRemote("getPid")
        d.addCallback(gotPid)
        return d

    def logout(self):
        self.log('logout called, %s disconnected', self.avatarId)

        self._heaven.removeAvatar(self.avatarId)
        
    def stop(self):
        """
        returns: a deferred marking completed stop.
        """
        if not self.mind:
            self.debug('already logged out')
            return defer.succeed(None)
        else:
            self.debug('stopping')
            return self.mindCallRemote('stop')

    def _sendFileDescriptor(self, fd, message):
        try:
            # FIXME: pay attention to the return value of
            # sendFileDescriptor; is the same as the return value of
            # sendmsg(2)
            self.mind.broker.transport.sendFileDescriptor(fd, message)
            return True
        except RuntimeError, e:
            # RuntimeError is what is thrown by the C code doing this
            # when there are issues
            self.warning("RuntimeError %s sending file descriptors",
                         log.getExceptionMessage(e))
            return False

    def logTo(self, stdout, stderr):
        """
        Tell the job to log to the given file descriptors.
        """
        self.debug('Giving job new stdout and stderr')
        if self.mind:
            self._sendFileDescriptor(stdout, "redirectStdout")
            self._sendFileDescriptor(stdout, "redirectStderr")

    def sendFeed(self, feedName, fd, eaterId):
        """
        Tell the feeder to send the given feed to the given fd.

        @returns: whether the fd was successfully handed off to the component.
        """
        self.debug('Sending FD %d to component job to feed %s to fd',
                   fd, feedName)

        # it is possible that the component has logged out, in which
        # case we don't have a mind. Trying to check for this earlier
        # only introduces a race, so we handle it here by triggering a
        # disconnect on the fd.
        if self.mind:
            message = "sendFeed %s %s" % (feedName, eaterId)
            return self._sendFileDescriptor(fd, message)
        else:
            self.debug('my mind is gone, trigger disconnect')
            return False

    def receiveFeed(self, feedId, fd):
        """
        Tell the feeder to receive the given feed from the given fd.

        @returns: whether the fd was successfully handed off to the component.
        """
        self.debug('Sending FD %d to component job to eat %s from fd',
                   fd, feedId)

        # same note as in sendFeed
        if self.mind:
            message = "receiveFeed %s" % (feedId,)
            return self._sendFileDescriptor(fd, message)
        else:
            self.debug('my mind is gone, trigger disconnect')
            return False

    def perspective_cleanShutdown(self):
        """
        This notification from the job process will be fired when it is
        shutting down, so that although the process might still be
        around, we know it's OK to accept new start requests for this
        avatar ID.
        """
        self.info("component %s shutting down cleanly", self.avatarId)
        # FIXME: drills down too much?
        self._heaven._deferredStarts.shutdown(self.pid)
