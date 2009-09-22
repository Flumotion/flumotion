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

from twisted.internet import reactor, error
from twisted.spread import flavors
from zope.interface import implements

from flumotion.common import errors, interfaces, debug
from flumotion.common import medium
from flumotion.common.vfs import listDirectory, registerVFSJelly
from flumotion.twisted.pb import ReconnectingFPBClientFactory

__version__ = "$Rev$"
JOB_SHUTDOWN_TIMEOUT = 5


class WorkerClientFactory(ReconnectingFPBClientFactory):
    """
    I am a client factory for the worker to log in to the manager.
    """
    logCategory = 'worker'
    perspectiveInterface = interfaces.IWorkerMedium

    def __init__(self, medium, host, port):
        """
        @type medium: L{flumotion.worker.medium.WorkerMedium}
        @type host:   str
        @type port:   int
        """
        self._managerHost = host
        self._managerPort = port
        self.medium = medium
        # doing this as a class method triggers a doc error
        ReconnectingFPBClientFactory.__init__(self)
        # maximum 10 second delay for workers to attempt to log in again
        self.maxDelay = 10

    def clientConnectionFailed(self, connector, reason):
        """
        @param reason: L{twisted.spread.pb.failure.Failure}
        """
        # this method exists so that we log the failure
        ReconnectingFPBClientFactory.clientConnectionFailed(self,
            connector, reason)
        # delay is now updated
        self.debug("failed to connect, will try to reconnect in %f seconds" %
                   self.delay)

    ### ReconnectingPBClientFactory methods

    def gotDeferredLogin(self, d):
        # the deferred from the login is now available
        # add some of our own to it

        def remoteDisconnected(remoteReference):
            if reactor.killed:
                self.log('Connection to manager lost due to shutdown')
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
            self.warning('A worker with the name "%s" is already connected.' %
                failure.value)

        def accessDeniedErrback(failure):
            failure.trap(errors.NotAuthenticatedError)
            self.warning('Access denied.')

        def connectionRefusedErrback(failure):
            failure.trap(error.ConnectionRefusedError)
            self.warning('Connection to %s:%d refused.' % (self._managerHost,
                                                         self._managerPort))

        def NoSuchMethodErrback(failure):
            failure.trap(flavors.NoSuchMethod)
            # failure.value is a str
            if failure.value.find('remote_getKeycardClasses') > -1:
                self.warning(
                    "Manager %s:%d is older than version 0.3.0.  "
                    "Please upgrade." % (self._managerHost, self._managerPort))
                return

            return failure

        def loginFailedErrback(failure):
            self.warning('Login failed, reason: %s' % str(failure))

        d.addCallback(loginCallback)
        d.addErrback(accessDeniedErrback)
        d.addErrback(connectionRefusedErrback)
        d.addErrback(alreadyConnectedErrback)
        d.addErrback(NoSuchMethodErrback)
        d.addErrback(loginFailedErrback)


class WorkerMedium(medium.PingingMedium):
    """
    I am a medium interfacing with the manager-side WorkerAvatar.

    @ivar brain:   the worker brain
    @type brain:   L{worker.WorkerBrain}
    @ivar factory: the worker client factory
    @type factory: L{WorkerClientFactory}
    """

    logCategory = 'workermedium'

    implements(interfaces.IWorkerMedium)

    def __init__(self, brain):
        """
        @type brain: L{worker.WorkerBrain}
        """
        self.brain = brain
        self.factory = None
        registerVFSJelly()

    def startConnecting(self, connectionInfo):
        info = connectionInfo

        self.factory = WorkerClientFactory(self, info.host, info.port)
        self.factory.startLogin(info.authenticator)

        if info.use_ssl:
            from flumotion.common import common
            common.assertSSLAvailable()
            from twisted.internet import ssl
            reactor.connectSSL(info.host, info.port, self.factory,
                               ssl.ClientContextFactory())
        else:
            reactor.connectTCP(info.host, info.port, self.factory)

    def stopConnecting(self):
        # only called by test suites
        self.factory.disconnect()
        self.factory.stopTrying()

    ### pb.Referenceable method for the manager's WorkerAvatar

    def remote_getPorts(self):
        """
        Gets the set of TCP ports that this worker is configured to use.

        @rtype:  2-tuple: (list of int, bool)
        @return: list of ports, and a boolean if we allocate ports
                 randomly
        """
        return self.brain.getPorts()

    def remote_getFeedServerPort(self):
        """
        Return the TCP port the Feed Server is listening on.

        @rtype:  int, or NoneType
        @return: TCP port number, or None if there is no feed server
        """
        return self.brain.getFeedServerPort()

    def remote_create(self, avatarId, type, moduleName, methodName,
                      nice, conf):
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
        @param conf:       component config
        @type  conf:       dict

        @returns: a deferred fired when the process has started and created
                  the component
        """
        return self.brain.create(avatarId, type, moduleName, methodName,
                                 nice, conf)

    def remote_checkElements(self, elementNames):
        """
        Checks if one or more GStreamer elements are present and can be
        instantiated.

        @param elementNames:   names of the Gstreamer elements
        @type  elementNames:   list of str

        @rtype:   list of str
        @returns: a list of instantiatable element names
        """
        return self.brain.runCheck('flumotion.worker.checks.check',
                                   'checkElements', elementNames)

    def remote_checkImport(self, moduleName):
        """
        Checks if the given module can be imported.

        @param moduleName: name of the module to check
        @type  moduleName: str

        @returns: None or Failure
        """
        return self.brain.runCheck(
            'flumotion.worker.checks.check', 'checkImport',
            moduleName)

    def remote_runCheck(self, module, function, *args, **kwargs):
        """
        Runs the given function in the given module with the given arguments.

        @param module:   module the function lives in
        @type  module:   str
        @param function: function to run
        @type  function: str

        @returns: the return value of the given function in the module.
        """
        return self.brain.runCheck(module, function, *args, **kwargs)
    remote_runFunction = remote_runCheck

    def remote_getComponents(self):
        """
        I return a list of componentAvatarIds, I have.  I am called by the
        manager soon after I attach to it.  This is needed on reconnects
        so that the manager knows what components it needs to start on me.

        @returns: a list of componentAvatarIds
        """
        return self.brain.getComponents()

    def remote_killJob(self, avatarId, signum=signal.SIGKILL):
        """Kill one of the worker's jobs.

        This method is intended for exceptional purposes only; a normal
        component shutdown is performed by the manager via calling
        remote_stop() on the component avatar.

        Raises L{flumotion.common.errors.UnknownComponentError} if the
        job is unknown.

        @param avatarId: the avatar Id of the component, e.g.
        '/default/audio-encoder'
        @type avatarId: string
        @param signum: Signal to send, optional. Defaults to SIGKILL.
        @type signum: int
        """
        self.brain.killJob(avatarId, signum)

    def remote_getVersions(self):
        return debug.getVersions()

    def remote_listDirectory(self, directoryName):
        """List the directory called path.

        Raises L{flumotion.common.errors.NotDirectoryError} if directoryName is
        not a directory.

        @param directoryName: the name of the directory to list
        @type directoryName: string
        @returns: the directory
        @rtype: deferred that will fire an object implementing L{IDirectory}
        """
        return listDirectory(directoryName)
