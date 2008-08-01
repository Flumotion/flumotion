# -*- Mode: Python; test-case-name:flumotion.test.test_worker_worker -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# Flumotion - a streaming media server
# Copyright (C) 2004,2005,2006,2007,2008 Fluendo, S.L. (www.fluendo.com).
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

"""worker-side objects to handle worker clients
"""

import signal

from twisted.internet import defer, error, reactor
from zope.interface import implements

from flumotion.common import errors, interfaces, log
from flumotion.worker import medium, job, feedserver
from flumotion.twisted.defer import defer_call_later

__version__ = "$Rev$"


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
    @ivar medium:
    @type medium:              L{medium.WorkerMedium}
    @ivar jobHeaven:
    @type jobHeaven:           L{job.ComponentJobHeaven}
    @ivar checkHeaven:
    @type checkHeaven:         L{job.CheckJobHeaven}
    @ivar workerClientFactory:
    @type workerClientFactory: L{medium.WorkerClientFactory}
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

        # really should be componentJobHeaven, but this is shorter :)
        self.jobHeaven = job.ComponentJobHeaven(self)
        # for ephemeral checks
        self.checkHeaven = job.CheckJobHeaven(self)

        self.managerConnectionInfo = None

        # it's possible we don't have a feed server, if we are
        # configured to have 0 tcp ports; setup this in listen()
        self.feedServer = None

        self.stopping = False
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

        try:
            self.checkHeaven.listen()
        except error.CannotListenError, e:
            self.warning("Failed to listen on check server port: %r", e)
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
        if self.stopping:
            self.warning("Already shutting down, ignoring shutdown request")
            return

        self.info("Reactor shutting down, stopping jobHeaven")
        self.stopping = True

        l = [self.jobHeaven.shutdown(), self.checkHeaven.shutdown()]
        if self.feedServer:
            l.append(self.feedServer.shutdown())
        # Don't fire this other than from a callLater
        return defer_call_later(defer.DeferredList(l))

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

    def eatFromFD(self, componentId, eaterAlias, fd, feedId):
        """
        Called from the FeedAvatar to pass a file descriptor on to
        the job running the given component.

        @returns: whether the fd was successfully handed off to the component.
        """
        if componentId not in self.jobHeaven.avatars:
            self.warning("No such component %s running", componentId)
            return False

        avatar = self.jobHeaven.avatars[componentId]
        return avatar.receiveFeed(eaterAlias, fd, feedId)

    ### these methods called by WorkerMedium

    def getPorts(self):
        return self.ports, self.options.randomFeederports

    def getFeedServerPort(self):
        if self.feedServer:
            return self.feedServer.getPortNum()
        else:
            return None

    def create(self, avatarId, type, moduleName, methodName, nice,
               conf):

        def getBundles():
            # set up bundles as we need to have a pb connection to
            # download the modules -- can't do that in the kid yet.
            moduleNames = [moduleName]
            for plugs in conf.get('plugs', {}).values():
                for plug in plugs:
                    for entry in plug.get('entries', {}).values():
                        moduleNames.append(entry['module-name'])
            self.debug('setting up bundles for %r', moduleNames)
            return self.medium.bundleLoader.getBundles(moduleName=moduleNames)

        def spawnJob(bundles):
            return self.jobHeaven.spawn(avatarId, type, moduleName,
                                        methodName, nice, bundles, conf)

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

    def runCheck(self, module, function, *args, **kwargs):

        def getBundles():
            self.debug('setting up bundles for %s', module)
            return self.medium.bundleLoader.getBundles(moduleName=module)

        def runCheck(bundles):
            return self.checkHeaven.runCheck(bundles, module, function,
                                             *args, **kwargs)

        d = getBundles()
        d.addCallback(runCheck)
        return d

    def getComponents(self):
        return [job.avatarId for job in self.jobHeaven.getJobInfos()]

    def killJob(self, avatarId, signum):
        self.jobHeaven.killJob(avatarId, signum)
