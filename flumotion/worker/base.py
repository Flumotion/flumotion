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
from flumotion.common import worker, startset
from flumotion.common.process import signalPid
from flumotion.twisted import checkers, fdserver
from flumotion.twisted import pb as fpb

__version__ = "$Rev$"

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
    def __init__(self, heaven, avatarId, startSet):
        self._startSet = startSet
        self._deferredStart = startSet.createRegistered(avatarId)
        worker.ProcessProtocol.__init__(self, heaven, avatarId,
                                        'component',
                                        heaven.getWorkerName())

    def sendMessage(self, message):
        heaven = self.loggable
        heaven.brain.callRemote('componentAddMessage', self.avatarId,
                                message)

    def processEnded(self, status):
        heaven = self.loggable
        dstarts = self._startSet
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
            text = ("Component '%s' has exited early (%s)." %
                    (self.avatarId, reason))
            dstarts.createFailed(self.avatarId,
                                 errors.ComponentCreateError(text))

        if dstarts.shutdownRegistered(self.avatarId):
            dstarts.shutdownSuccess(self.avatarId)

        heaven.jobStopped(self.pid)

        # chain up
        worker.ProcessProtocol.processEnded(self, status)


class BaseJobHeaven(pb.Root, log.Loggable):
    """
    I am similar to but not quite the same as a manager-side Heaven.
    I manage avatars inside the worker for job processes spawned by the worker.

    @ivar avatars: dict of avatarId -> avatar
    @type avatars: dict of str -> L{base.BaseJobAvatar}
    @ivar brain:   the worker brain
    @type brain:   L{worker.WorkerBrain}
    """

    logCategory = "job-heaven"
    implements(portal.IRealm)

    avatarClass = None

    def __init__(self, brain):
        """
        @param brain:       a reference to the worker brain
        @type  brain:       L{worker.WorkerBrain}
        """
        self.avatars = {} # componentId -> avatar
        self.brain = brain
        self._socketPath = _getSocketPath()
        self._port = None
        self._onShutdown = None # If set, a deferred to fire when
                                # our last child process exits

        self._jobInfos = {} # processid -> JobInfo

        self._startSet = startset.StartSet(
            lambda x: x in self.avatars,
            errors.ComponentAlreadyStartingError,
            errors.ComponentAlreadyRunningError)

    def listen(self):
        assert self._port is None
        assert self.avatarClass is not None
        # FIXME: we should hand a username and password to log in with to
        # the job process instead of allowing anonymous
        checker = checkers.FlexibleCredentialsChecker()
        checker.allowPasswordless(True)
        p = portal.Portal(self, [checker])
        f = pb.PBServerFactory(p)
        try:
            os.unlink(self._socketPath)
        except OSError:
            pass

        # Rather than a listenUNIX(), we use listenWith so that we can specify
        # our particular Port, which creates Transports that we know how to
        # pass FDs over.
        port = reactor.listenWith(fdserver.FDPort, self._socketPath, f)
        self._port = port

    ### portal.IRealm method
    def requestAvatar(self, avatarId, mind, *interfaces):
        if pb.IPerspective in interfaces:
            avatar = self.avatarClass(self, avatarId, mind)
            assert avatarId not in self.avatars
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

    def getWorkerName(self):
        """
        Gets the name of the worker that spawns the process.

        @rtype: str
        """
        return self.brain.workerName

    def addJobInfo(self, processId, jobInfo):
        self._jobInfos[processId] = jobInfo

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
        signalPid(jobInfo.pid, signum)

    def killJob(self, avatarId, signum):
        for job in self._jobInfos.values():
            if job.avatarId == avatarId:
                self.killJobByPid(job.pid, signum)


class BaseJobAvatar(fpb.Avatar, log.Loggable):
    """
    I am an avatar for the job living in the worker.
    """
    logCategory = 'job-avatar'

    def __init__(self, heaven, avatarId, mind):
        """
        @type  heaven:   L{flumotion.worker.base.BaseJobHeaven}
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
        self.haveMind()

    def haveMind(self):
        # implement me in subclasses
        pass

    def logout(self):
        self.log('logout called, %s disconnected', self.avatarId)

        self._heaven.removeAvatar(self.avatarId)

    def stop(self):
        """
        returns: a deferred marking completed stop.
        """
        raise NotImplementedError

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
