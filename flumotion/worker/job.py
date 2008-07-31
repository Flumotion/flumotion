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
import signal
import sys

from twisted.internet import defer, reactor

from flumotion.common import errors, log
from flumotion.common import messages
from flumotion.common.i18n import N_, gettexter
from flumotion.configure import configure
from flumotion.worker import base

__version__ = "$Rev$"
T_ = gettexter()


class ComponentJobAvatar(base.BaseJobAvatar):
    def haveMind(self):
        def bootstrap(*args):
            return self.mindCallRemote('bootstrap', *args)

        def create(_, job):
            self.debug("asking job to create component with avatarId %s,"
                       " type %s", job.avatarId, job.type)
            return self.mindCallRemote('create', job.avatarId, job.type,
                                       job.moduleName, job.methodName,
                                       job.nice, job.conf)

        def success(_, avatarId):
            self.debug('job started component with avatarId %s',
                       avatarId)
            # FIXME: drills down too much?
            self._heaven._startSet.createSuccess(avatarId)

        def error(failure, job):
            msg = log.getFailureMessage(failure)
            if failure.check(errors.ComponentCreateError):
                self.warning('could not create component %s of type %s:'
                             ' %s', job.avatarId, job.type, msg)
            else:
                self.warning('unhandled error creating component %s: %s',
                             job.avatarId, msg)
            # FIXME: drills down too much?
            self._heaven._startSet.createFailed(job.avatarId, failure)

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

    def receiveFeed(self, eaterAlias, fd, feedId):
        """
        Tell the feeder to receive the given feed from the given fd.

        @returns: whether the fd was successfully handed off to the component.
        """
        self.debug('Sending FD %d to component job to eat %s from fd',
                   fd, eaterAlias)

        # same note as in sendFeed
        if self.mind:
            message = "receiveFeed %s %s" % (eaterAlias, feedId)
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
        self._heaven._startSet.shutdownStart(self.avatarId)


class ComponentJobInfo(base.JobInfo):
    __slots__ = ('conf', )

    def __init__(self, pid, avatarId, type, moduleName, methodName,
                 nice, bundles, conf):
        base.JobInfo.__init__(self, pid, avatarId, type, moduleName,
                              methodName, nice, bundles)
        self.conf = conf


class ComponentJobHeaven(base.BaseJobHeaven):
    avatarClass = ComponentJobAvatar

    def getManagerConnectionInfo(self):
        """
        Gets the L{flumotion.common.connection.PBConnectionInfo}
        describing how to connect to the manager.

        @rtype: L{flumotion.common.connection.PBConnectionInfo}
        """
        return self.brain.managerConnectionInfo

    def spawn(self, avatarId, type, moduleName, methodName, nice,
              bundles, conf):
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
        @param conf:       component configuration
        @type  conf:       dict
        """
        d = self._startSet.createStart(avatarId)

        p = base.JobProcessProtocol(self, avatarId, self._startSet)
        executable = os.path.join(configure.bindir, 'flumotion-job')
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

        self.addJobInfo(process.pid,
                        ComponentJobInfo(process.pid, avatarId, type,
                                         moduleName, methodName, nice,
                                         bundles, conf))
        return d


class CheckJobAvatar(base.BaseJobAvatar):
    def haveMind(self):
        # FIXME: drills down too much?
        def gotPid(pid):
            self.pid = pid
            job = self._heaven.getJobInfo(pid)
            self._heaven._startSet.createSuccess(job.avatarId)

        d = self.mindCallRemote("getPid")
        d.addCallback(gotPid)
        return d

    def stop(self):
        """
        returns: a deferred marking completed stop.
        """
        self._heaven._startSet.shutdownStart(self.avatarId)
        self._heaven.killJob(self.avatarId, signal.SIGTERM)

    def perspective_cleanShutdown(self):
        self.debug("job is stopping")


class CheckJobHeaven(base.BaseJobHeaven):
    avatarClass = CheckJobAvatar

    _checkCount = 0
    _timeout = 45

    def __init__(self, brain):
        base.BaseJobHeaven.__init__(self, brain)

        # job processes that are available to do work (i.e. not actively
        # running checks)
        self.jobPool = []

    def getCheckJobFromPool(self):
        if self.jobPool:
            job, expireDC = self.jobPool.pop(0)
            expireDC.cancel()
            self.debug('running check in already-running job %s',
                       job.avatarId)
            return defer.succeed(job)

        avatarId = 'check-%d' % (self._checkCount, )
        self._checkCount += 1

        self.debug('spawning new job %s to run a check', avatarId)
        d = self._startSet.createStart(avatarId)

        p = base.JobProcessProtocol(self, avatarId, self._startSet)
        executable = os.path.join(configure.bindir, 'flumotion-job')
        argv = [executable, avatarId, self._socketPath]

        childFDs = {0: 0, 1: 1, 2: 2}
        env = {}
        env.update(os.environ)
        env['FLU_DEBUG'] = log.getDebug()
        process = reactor.spawnProcess(p, executable, env=env, args=argv,
                                       childFDs=childFDs)

        p.setPid(process.pid)
        jobInfo = base.JobInfo(process.pid, avatarId, type, None, None,
                               None, [])
        self._jobInfos[process.pid] = jobInfo

        def haveMind(_):
            # we have a mind, in theory; return the job avatar
            return self.avatars[avatarId]

        d.addCallback(haveMind)
        return d

    def runCheck(self, bundles, moduleName, methodName, *args, **kwargs):
        def haveJob(job):
            def callProc(_):
                return job.mindCallRemote('runFunction', moduleName,
                                          methodName, *args, **kwargs)

            def timeout(sig):
                self.killJobByPid(job.pid, sig)

            def haveResult(res):
                if not termtimeout.active():
                    self.info("Discarding error %s", res)
                    res = messages.Result()
                    res.add(messages.Error(T_(N_("Check timed out.")),
                                           debug=("Timed out running %s."%methodName)))
                else:
                    def expire():
                        if (job, expireDC) in self.jobPool:
                            self.debug('stopping idle check job process %s',
                                       job.avatarId)
                            self.jobPool.remove((job, expireDC))
                            job.mindCallRemote('stop')
                    expireDC = reactor.callLater(self._timeout, expire)
                    self.jobPool.append((job, expireDC))

                if termtimeout.active():
                    termtimeout.cancel()
                if killtimeout.active():
                    killtimeout.cancel()
                return res

            # add callbacks and errbacks that kill the job

            termtimeout = reactor.callLater(self._timeout, timeout,
                                            signal.SIGTERM)
            killtimeout = reactor.callLater(self._timeout, timeout,
                                            signal.SIGKILL)

            d = job.mindCallRemote('bootstrap', self.getWorkerName(),
                                   None, None, None, None, bundles)
            d.addCallback(callProc)
            d.addCallbacks(haveResult, haveResult)
            return d

        d = self.getCheckJobFromPool()
        d.addCallback(haveJob)

        return d
