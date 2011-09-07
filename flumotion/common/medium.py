# -*- Mode: Python -*-
# vi:si:et:sw=4:sts=4:ts=4

# Flumotion - a streaming media server
# Copyright (C) 2004,2005,2006,2007,2008,2009 Fluendo, S.L.
# Copyright (C) 2010,2011 Flumotion Services, S.A.
# All rights reserved.
#
# This file may be distributed and/or modified under the terms of
# the GNU Lesser General Public License version 2.1 as published by
# the Free Software Foundation.
# This file is distributed without any warranty; without even the implied
# warranty of merchantability or fitness for a particular purpose.
# See "LICENSE.LGPL" in the source distribution for more information.
#
# Headers in this file shall remain intact.

"""base classes for PB client-side mediums.
"""

from twisted.spread import pb
from twisted.internet import defer
from zope.interface import implements

from flumotion.common import log, interfaces, bundleclient, errors, netutils
from flumotion.configure import configure
from flumotion.twisted import pb as fpb
from flumotion.twisted.compat import reactor

# register serializables
from flumotion.common import messages

__version__ = "$Rev$"


class BaseMedium(fpb.Referenceable):
    """
    I am a base interface for PB clients interfacing with PB server-side
    avatars.
    Used by admin/worker/component to talk to manager's vishnu,
    and by job to talk to worker's brain.

    @ivar remote:       a remote reference to the server-side object on
                        which perspective_(methodName) methods can be called
    @type remote:       L{twisted.spread.pb.RemoteReference}
    @type bundleLoader: L{flumotion.common.bundleclient.BundleLoader}
    """

    # subclasses will need to set this to the specific medium type
    # tho...
    implements(interfaces.IMedium)
    logCategory = "basemedium"
    remoteLogName = "baseavatar"

    remote = None
    bundleLoader = None

    def setRemoteReference(self, remoteReference):
        """
        Set the given remoteReference as the reference to the server-side
        avatar.

        @param remoteReference: L{twisted.spread.pb.RemoteReference}
        """
        self.debug('%r.setRemoteReference: %r' % (self, remoteReference))
        self.remote = remoteReference

        def nullRemote(x):
            self.debug('%r: disconnected from %r' % (self, self.remote))
            self.remote = None
        self.remote.notifyOnDisconnect(nullRemote)

        self.bundleLoader = bundleclient.BundleLoader(self.callRemote)

        # figure out connection addresses if it's an internet address
        tarzan = None
        jane = None
        try:
            transport = remoteReference.broker.transport
            tarzan = transport.getHost()
            jane = transport.getPeer()
        except Exception, e:
            self.debug("could not get connection info, reason %r" % e)
        if tarzan and jane:
            self.debug("connection is from me on %s to remote on %s" % (
                netutils.addressGetHost(tarzan),
                netutils.addressGetHost(jane)))

    def hasRemoteReference(self):
        """
        Does the medium have a remote reference to a server-side avatar ?
        """
        return self.remote != None

    def callRemoteLogging(self, level, stackDepth, name, *args, **kwargs):
        """
        Call the given method with the given arguments remotely on the
        server-side avatar.

        Gets serialized to server-side perspective_ methods.

        @param level: the level we should log at (log.DEBUG, log.INFO, etc)
        @type  level: int
        @param stackDepth: the number of stack frames to go back to get
        file and line information, negative or zero.
        @type  stackDepth: non-positive int
        @param name: name of the remote method
        @type  name: str
        """
        if level is not None:
            debugClass = str(self.__class__).split(".")[-1].upper()
            startArgs = [self.remoteLogName, debugClass, name]
            formatString, debugArgs = log.getFormatArgs(
                '%s --> %s: callRemote(%s, ', startArgs,
                ')', (), args, kwargs)
            logKwArgs = self.doLog(level, stackDepth - 1,
                                   formatString, *debugArgs)

        if not self.remote:
            self.warning('Tried to callRemote(%s), but we are disconnected'
                         % name)
            return defer.fail(errors.NotConnectedError())

        def callback(result):
            formatString, debugArgs = log.getFormatArgs(
                '%s <-- %s: callRemote(%s, ', startArgs,
                '): %s', (log.ellipsize(result), ), args, kwargs)
            self.doLog(level, -1, formatString, *debugArgs, **logKwArgs)
            return result

        def errback(failure):
            formatString, debugArgs = log.getFormatArgs(
                '%s <-- %s: callRemote(%s, ', startArgs,
                '): %r', (failure, ), args, kwargs)
            self.doLog(level, -1, formatString, *debugArgs, **logKwArgs)
            return failure

        d = self.remote.callRemote(name, *args, **kwargs)
        if level is not None:
            d.addCallbacks(callback, errback)
        return d

    def callRemote(self, name, *args, **kwargs):
        """
        Call the given method with the given arguments remotely on the
        server-side avatar.

        Gets serialized to server-side perspective_ methods.
        """
        return self.callRemoteLogging(log.DEBUG, -1, name, *args,
                                      **kwargs)

    def getBundledFunction(self, module, function):
        """
        Returns the given function in the given module, loading the
        module from a bundle.

        If we can't find the bundle for the given module, or if the
        given module does not contain the requested function, we will
        raise L{flumotion.common.errors.RemoteRunError} (perhaps a
        poorly chosen error). If importing the module raises an
        exception, that exception will be passed through unmodified.

        @param module:   module the function lives in
        @type  module:   str
        @param function: function to run
        @type  function: str

        @returns: a callable, the given function in the given module.
        """

        def gotModule(mod):
            if hasattr(mod, function):
                return getattr(mod, function)
            else:
                msg = 'No procedure named %s in module %s' % (function,
                                                              module)
                self.warning('%s', msg)
                raise errors.RemoteRunError(msg)

        def gotModuleError(failure):
            failure.trap(errors.NoBundleError)
            msg = 'Failed to find bundle for module %s' % module
            self.warning('%s', msg)
            raise errors.RemoteRunError(msg)

        d = self.bundleLoader.loadModule(module)
        d.addCallbacks(gotModule, gotModuleError)
        return d

    def runBundledFunction(self, module, function, *args, **kwargs):
        """
        Runs the given function in the given module with the given
        arguments.

        This method calls getBundledFunction and then invokes the
        function. Any error raised by getBundledFunction or by invoking
        the function will be passed through unmodified.

        Callers that expect to return their result over a PB connection
        should catch nonserializable exceptions so as to prevent nasty
        backtraces in the logs.

        @param module:   module the function lives in
        @type  module:   str
        @param function: function to run
        @type  function: str

        @returns: the return value of the given function in the module.
        """
        self.debug('runBundledFunction(%r, %r)', module, function)

        def gotFunction(proc):

            def invocationError(failure):
                self.warning('Exception raised while calling '
                             '%s.%s(*args=%r, **kwargs=%r): %s',
                             module, function, args, kwargs,
                             log.getFailureMessage(failure))
                return failure

            self.debug('calling %s.%s(%r, %r)', module, function, args,
                       kwargs)
            d = defer.maybeDeferred(proc, *args, **kwargs)
            d.addErrback(invocationError)
            return d

        d = self.getBundledFunction(module, function)
        d.addCallback(gotFunction)
        return d


class PingingMedium(BaseMedium):
    _pingInterval = configure.heartbeatInterval
    _pingCheckInterval = (configure.heartbeatInterval *
                          configure.pingTimeoutMultiplier)
    _pingDC = None
    _clock = reactor

    def startPinging(self, disconnect):
        """
        @param disconnect: a method to call when we do not get ping replies
        @type  disconnect: callable
        """
        self.debug('startPinging')
        self._lastPingback = self._clock.seconds()
        if self._pingDC:
            self.debug("Cannot start pinging, already pinging")
            return
        self._pingDisconnect = disconnect
        self._ping()
        self._pingCheck()

    def _ping(self):

        def pingback(result):
            self._lastPingback = self._clock.seconds()
            self.log('pinged, pingback at %r' % self._lastPingback)

        def pingFailed(failure):
            # ignoring the connection failures so they don't end up in
            # the logs - we'll notice the lack of pingback eventually
            failure.trap(pb.PBConnectionLost)
            self.log('ping failed: %s' % log.getFailureMessage(failure))

        if self.remote:
            self.log('pinging')
            d = self.callRemoteLogging(log.LOG, 0, 'ping')
            d.addCallbacks(pingback, pingFailed)
        else:
            self.info('tried to ping, but disconnected yo')

        self._pingDC = self._clock.callLater(self._pingInterval,
                                             self._ping)

    def remoteMessageReceived(self, broker, message, args, kw):
        self._lastPingback = self._clock.seconds()
        return BaseMedium.remoteMessageReceived(
            self, broker, message, args, kw)

    def callRemoteLogging(self, level, stackDepth, name, *args, **kwargs):
        d = BaseMedium.callRemoteLogging(
            self, level, stackDepth, name, *args, **kwargs)

        def cb(result):
            self._lastPingback = self._clock.seconds()
            return result
        d.addCallback(cb)
        return d

    def _pingCheck(self):
        self._pingCheckDC = None
        if (self.remote and
            ((self._clock.seconds() - self._lastPingback) >
             self._pingCheckInterval)):
            self.info('no pingback in %f seconds, closing connection',
                      self._pingCheckInterval)
            self._pingDisconnect()
        else:
            self._pingCheckDC = self._clock.callLater(self._pingCheckInterval,
                                                      self._pingCheck)

    def stopPinging(self):
        if self._pingCheckDC:
            self._pingCheckDC.cancel()
        self._pingCheckDC = None

        if self._pingDC:
            self._pingDC.cancel()
        self._pingDC = None

    def _disconnect(self):
        if self.remote:
            self.remote.broker.transport.loseConnection()

    def setRemoteReference(self, remote, clock=reactor):
        self._clock = clock

        BaseMedium.setRemoteReference(self, remote)

        def stopPingingCb(x):
            self.debug('stop pinging')
            self.stopPinging()
        self.remote.notifyOnDisconnect(stopPingingCb)

        self.startPinging(self._disconnect)

    def remote_writeFluDebugMarker(self, level, marker):
        """
        Sets a marker that will be prefixed to the log strings. Setting this
        marker to multiple elements at a time helps debugging.
        @param marker: A string to prefix all the log strings.
        @type marker: str
        """
        self.writeMarker(marker, level)
