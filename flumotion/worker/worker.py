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

import signal

import gst
import gst.interfaces

from twisted.cred import portal
from twisted.internet import defer, reactor
from twisted.spread import pb
from twisted.internet import error
from zope.interface import implements

from flumotion.common import errors, interfaces, log, bundleclient
from flumotion.common import common, medium, messages, worker
from flumotion.twisted import checkers, fdserver
from flumotion.twisted import pb as fpb
from flumotion.twisted import defer as fdefer
from flumotion.configure import configure
from flumotion.worker import medium, job, feedserver

class ProxyBouncer(log.Loggable):
    logCategory = "proxybouncer"

    """
    I am a bouncer that proxies authenticate calls to a remote FPB root
    object.
    """
    def __init__(self, remote):
        """
        @param remote: an object that has .callRemote()
        """
        self._remote = remote

    def getKeycardClasses(self):
        """
        Call me before asking me to authenticate, so I know what I can
        authenticate.
        """
        return self._remote.callRemote('getKeycardClasses')

    def authenticate(self, keycard):
        self.debug("Authenticating keycard %r against remote bouncer",
                   keycard)
        return self._remote.callRemote('authenticate', None, keycard)

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

    implements(interfaces.IFeedServerParent)

    logCategory = 'workerbrain'

    def __init__(self, options):
        """
        @param options: the optparsed dictionary of command-line options
        @type  options: an object with attributes
        """
        self.options = options
        self.workerName = options.name

        # the last port is reserved for our FeedServer
        if not self.options.randomFeederports:
            self.ports = self.options.feederports[:-1]
        else:
            self.ports = []

        self.medium = medium.WorkerMedium(self)

        self.jobHeaven = job.JobHeaven(self)

        self.managerConnectionInfo = None

        # it's possible we don't have a feed server, if we are
        # configured to have 0 tcp ports; setup this in listen()
        self.feedServer = None

        reactor.addSystemEventTrigger('before', 'shutdown',
                                      self.shutdownHandler)
        self._installHUPHandler()

    def _installHUPHandler(self):
        def sighup(signum, frame):
            if self._oldHUPHandler:
                self.log('got SIGHUP, calling previous handler %r',
                         self._oldHUPHandler)
                self._oldHUPHandler(signum, frame)
            self.debug('telling kids about new log file descriptors')
            self.jobHeaven.rotateChildLogFDs()

        handler = signal.signal(signal.SIGHUP, sighup)
        if handler == signal.SIG_DFL or handler == signal.SIG_IGN:
            self._oldHUPHandler = None
        else:
            self._oldHUPHandler = handler

    def listen(self):
        """
        Start listening on FeedServer (incoming eater requests) and 
        JobServer (through which we communicate with our children) ports

        @returns: True if we successfully listened on both ports
        """
        # set up feed server if we have the feederports for it
        try:
            self.feedServer = self._makeFeedServer()
        except error.CannotListenError, e:
            self.warning("Failed to listen on feed server port: %r", e)
            return False

        try:
            self.jobHeaven.listen()
        except error.CannotListenError, e:
            self.warning("Failed to listen on job server port: %r", e)
            return False

        return True

    def _makeFeedServer(self):
        """
        @returns: L{flumotion.worker.feedserver.FeedServer}
        """
        port = None
        if self.options.randomFeederports:
            port = 0
        elif not self.options.feederports:
            self.info('Not starting feed server because no port is '
                      'configured')
            return None
        else:
            port = self.options.feederports[-1]

        return feedserver.FeedServer(self, ProxyBouncer(self), port)

    def login(self, managerConnectionInfo):
        self.managerConnectionInfo = managerConnectionInfo
        self.medium.startConnecting(managerConnectionInfo)

    def callRemote(self, methodName, *args, **kwargs):
        return self.medium.callRemote(methodName, *args, **kwargs)

    def shutdownHandler(self):
        self.info("Reactor shutting down, stopping jobHeaven")

        l = [self.jobHeaven.shutdown()]
        if self.feedServer:
            l.append(self.feedServer.shutdown())
        # Don't fire this other than from a callLater
        return fdefer.defer_call_later(defer.DeferredList(l))

    ### These methods called by feed server
    def feedToFD(self, componentId, feedName, fd, eaterId):
        """
        Called from the FeedAvatar to pass a file descriptor on to
        the job running the component for this feeder.

        @returns: whether the fd was successfully handed off to the component.
        """
        if componentId not in self.jobHeaven.avatars:
            self.warning("No such component %s running", componentId)
            return False

        avatar = self.jobHeaven.avatars[componentId]
        return avatar.sendFeed(feedName, fd, eaterId)

    def eatFromFD(self, componentId, feedId, fd):
        """
        Called from the FeedAvatar to pass a file descriptor on to
        the job running the given component.

        @returns: whether the fd was successfully handed off to the component.
        """
        if componentId not in self.jobHeaven.avatars:
            self.warning("No such component %s running", componentId)
            return False

        avatar = self.jobHeaven.avatars[componentId]
        return avatar.receiveFeed(feedId, fd)
   
    ### these methods called by WorkerMedium
    def getPorts(self):
        return self.ports

    def getFeedServerPort(self):
        if self.feedServer:
            return self.feedServer.getPortNum()
        else:
            return None

    def create(self, avatarId, type, moduleName, methodName, nice=0):
        def getBundles():
            # set up bundles as we need to have a pb connection to
            # download the modules -- can't do that in the kid yet.
            # FIXME: find a way to rebuild less so this doesn't
            # take excessive amounts of CPU time
            self.debug('setting up bundles for %s', moduleName)
            return self.medium.bundleLoader.getBundles(moduleName=moduleName)

        def spawnJob(bundles):
            return self.jobHeaven.spawn(avatarId, type, moduleName,
                                        methodName, nice, bundles)

        def createError(failure):
            failure.trap(errors.ComponentCreateError)
            self.debug('create deferred for %s failed, forwarding error',
                       avatarId)
            return failure

        def success(res):
            self.debug('create deferred for %s succeeded (%r)',
                       avatarId, res)
            return res

        self.info('Starting component "%s" of type "%s"', avatarId,
                  type)
        d = getBundles()
        d.addCallback(spawnJob)
        d.addCallback(success)
        d.addErrback(createError)
        return d

    def checkElements(self, elementNames):
        self.debug('checkElements: element names to check %r',
                   elementNames)
        ret = []
        for name in elementNames:
            try:
                gst.element_factory_make(name)
                ret.append(name)
            except gst.PluginNotFoundError:
                pass
        self.debug('checkElements: returning elements names %r', ret)
        return ret

    def checkImport(self, moduleName):
        self.debug('checkImport: %s', moduleName)
        # FIXME: maybe find a nice way to check if we can import
        # without importing ?
        __import__(moduleName) 

    def getComponents(self):
        return [job.avatarId for job in self.jobHeaven.getJobInfos()]

    def killJob(self, avatarId, signum):
        self.jobHeaven.killJob(avatarId, signum)

