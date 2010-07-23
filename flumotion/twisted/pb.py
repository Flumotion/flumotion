# -*- Mode: Python; test-case-name: flumotion.test.test_pb -*-
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
Flumotion Perspective Broker using keycards

Inspired by L{twisted.spread.pb}
"""

from twisted.cred import checkers, credentials
from twisted.cred.portal import IRealm, Portal
from twisted.internet import protocol, defer
from twisted.internet import error as terror
from twisted.python import log, reflect, failure
from twisted.spread import pb, flavors
from twisted.spread.pb import PBClientFactory
from zope.interface import implements

from flumotion.configure import configure
from flumotion.common import keycards, interfaces, common, errors
from flumotion.common import log as flog
from flumotion.common.netutils import addressGetHost
from flumotion.twisted import reflect as freflect
from flumotion.twisted import credentials as fcredentials
from flumotion.twisted.compat import reactor

__version__ = "$Rev$"


# TODO:
#   merge FMCF back into twisted

### Keycard-based FPB objects

# we made three changes to the standard PBClientFactory:
# 1) the root object has a getKeycardClasses() call that the server
#    uses to tell clients about the interfaces it supports
# 2) you can request a specific interface for the avatar to
#    implement, instead of only IPerspective
# 3) you send in a keycard, on which you can set a preference for an avatarId
# this way you can request a different avatarId than the user you authenticate
# with, or you can login without a username


class FPBClientFactory(pb.PBClientFactory, flog.Loggable):
    """
    I am an extended Perspective Broker client factory using generic
    keycards for login.


    @ivar keycard:              the keycard used last for logging in; set after
                                self.login has completed
    @type keycard:              L{keycards.Keycard}
    @ivar medium:               the client-side referenceable for the PB server
                                to call on, and for the client to call to the
                                PB server
    @type medium:               L{flumotion.common.medium.BaseMedium}
    @ivar perspectiveInterface: the interface we want to request a perspective
                                for
    @type perspectiveInterface: subclass of
                                L{flumotion.common.interfaces.IMedium}
    """
    logCategory = "FPBClientFactory"
    keycard = None
    medium = None
    perspectiveInterface = None # override in subclass
    _fpbconnector = None

    ## from protocol.ClientFactory

    def startedConnecting(self, connector):
        self._fpbconnector = connector
        return pb.PBClientFactory.startedConnecting(self, connector)

    ## from twisted.spread.pb.ClientFactory

    def disconnect(self):
        if self._fpbconnector:
            try:
                self._fpbconnector.stopConnecting()
            except terror.NotConnectingError:
                pass
        return pb.PBClientFactory.disconnect(self)

    def getKeycardClasses(self):
        """
        Ask the remote PB server for all the keycard interfaces it supports.

        @rtype: L{twisted.internet.defer.Deferred} returning list of str
        """

        def getRootObjectCb(root):
            return root.callRemote('getKeycardClasses')

        d = self.getRootObject()
        d.addCallback(getRootObjectCb)
        return d

    def login(self, authenticator):
        """
        Login, respond to challenges, and eventually get perspective
        from remote PB server.

        Currently only credentials implementing IUsernamePassword are
        supported.

        @return: Deferred of RemoteReference to the perspective.
        """
        assert authenticator, "I really do need an authenticator"
        assert not isinstance(authenticator, keycards.Keycard)
        interfaces = []
        if self.perspectiveInterface:
            self.debug('perspectiveInterface is %r' %
                       self.perspectiveInterface)
            interfaces.append(self.perspectiveInterface)
        else:
            self.warning('No perspectiveInterface set on %r' % self)
        if not pb.IPerspective in interfaces:
            interfaces.append(pb.IPerspective)
        interfaces = [reflect.qual(interface)
                          for interface in interfaces]

        def getKeycardClassesCb(keycardClasses):
            self.log('supported keycard classes: %r' % keycardClasses)
            d = authenticator.issue(keycardClasses)
            return d

        def issueCb(keycard):
            self.keycard = keycard
            self.debug('using keycard: %r' % self.keycard)
            return self.keycard

        d = self.getKeycardClasses()
        d.addCallback(getKeycardClassesCb)
        d.addCallback(issueCb)
        d.addCallback(lambda r: self.getRootObject())
        d.addCallback(self._cbSendKeycard, authenticator, self.medium,
            interfaces)
        return d

    # we are a different kind of PB client, so warn

    def _cbSendUsername(self, root, username, password,
                        avatarId, client, interfaces):
        self.warning("you really want to use cbSendKeycard")

    def _cbSendKeycard(self, root, authenticator, client, interfaces, count=0):
        self.log("_cbSendKeycard(root=%r, authenticator=%r, client=%r, "
                 "interfaces=%r, count=%d", root, authenticator, client,
                 interfaces, count)
        count = count + 1
        d = root.callRemote("login", self.keycard, client, *interfaces)
        return d.addCallback(self._cbLoginCallback, root,
                             authenticator, client, interfaces, count)

    # we can get either a keycard, None (?) or a remote reference

    def _cbLoginCallback(self, result, root, authenticator, client, interfaces,
        count):
        if count > 5:
            # too many recursions, server is h0rked
            self.warning('Too many recursions, internal error.')
        self.log("FPBClientFactory(): result %r" % result)

        if isinstance(result, pb.RemoteReference):
            # everything done, return reference
            self.debug('login successful, returning %r', result)
            return result

        # must be a keycard
        keycard = result
        if not keycard.state == keycards.AUTHENTICATED:
            self.log("FPBClientFactory(): requester needs to resend %r",
                     keycard)
            d = authenticator.respond(keycard)

            def _loginAgainCb(keycard):
                d = root.callRemote("login", keycard, client, *interfaces)
                return d.addCallback(self._cbLoginCallback, root,
                                     authenticator, client,
                                     interfaces, count)
            d.addCallback(_loginAgainCb)
            return d

        self.debug("FPBClientFactory(): authenticated %r" % keycard)
        return keycard


class ReconnectingPBClientFactory(pb.PBClientFactory, flog.Loggable,
                                  protocol.ReconnectingClientFactory):
    """
    Reconnecting client factory for normal PB brokers.

    Users of this factory call startLogin to start logging in, and should
    override getLoginDeferred to get the deferred returned from the PB server
    for each login attempt.
    """

    def __init__(self):
        pb.PBClientFactory.__init__(self)
        self._doingLogin = False

    def clientConnectionFailed(self, connector, reason):
        log.msg("connection failed to %s, reason %r" % (
            connector.getDestination(), reason))
        pb.PBClientFactory.clientConnectionFailed(self, connector, reason)
        RCF = protocol.ReconnectingClientFactory
        RCF.clientConnectionFailed(self, connector, reason)

    def clientConnectionLost(self, connector, reason):
        log.msg("connection lost to %s, reason %r" % (
            connector.getDestination(), reason))
        pb.PBClientFactory.clientConnectionLost(self, connector, reason,
                                             reconnecting=True)
        RCF = protocol.ReconnectingClientFactory
        RCF.clientConnectionLost(self, connector, reason)

    def clientConnectionMade(self, broker):
        log.msg("connection made")
        self.resetDelay()
        pb.PBClientFactory.clientConnectionMade(self, broker)
        if self._doingLogin:
            d = self.login(self._credentials, self._client)
            self.gotDeferredLogin(d)

    def startLogin(self, credentials, client=None):
        self._credentials = credentials
        self._client = client

        self._doingLogin = True

    # methods to override

    def gotDeferredLogin(self, deferred):
        """
        The deferred from login is now available.
        """
        raise NotImplementedError


class ReconnectingFPBClientFactory(FPBClientFactory,
                                   protocol.ReconnectingClientFactory):
    """
    Reconnecting client factory for FPB brokers (using keycards for login).

    Users of this factory call startLogin to start logging in.
    Override getLoginDeferred to get a handle to the deferred returned
    from the PB server.
    """

    def __init__(self):
        FPBClientFactory.__init__(self)
        self._doingLogin = False
        self._doingGetPerspective = False

    def clientConnectionFailed(self, connector, reason):
        log.msg("connection failed to %s, reason %r" % (
            connector.getDestination(), reason))
        FPBClientFactory.clientConnectionFailed(self, connector, reason)
        RCF = protocol.ReconnectingClientFactory
        RCF.clientConnectionFailed(self, connector, reason)
        if self.continueTrying:
            self.debug("will try reconnect in %f seconds", self.delay)
        else:
            self.debug("not trying to reconnect")

    def clientConnectionLost(self, connector, reason):
        log.msg("connection lost to %s, reason %r" % (
            connector.getDestination(), reason))
        FPBClientFactory.clientConnectionLost(self, connector, reason,
                                             reconnecting=True)
        RCF = protocol.ReconnectingClientFactory
        RCF.clientConnectionLost(self, connector, reason)

    def clientConnectionMade(self, broker):
        log.msg("connection made")
        self.resetDelay()
        FPBClientFactory.clientConnectionMade(self, broker)
        if self._doingLogin:
            d = self.login(self._authenticator)
            self.gotDeferredLogin(d)

    # TODO: This is a poorly named method; it just provides the appropriate
    # authentication information, and doesn't actually _start_ login at all.

    def startLogin(self, authenticator):
        assert not isinstance(authenticator, keycards.Keycard)
        self._authenticator = authenticator
        self._doingLogin = True

    # methods to override

    def gotDeferredLogin(self, deferred):
        """
        The deferred from login is now available.
        """
        raise NotImplementedError

### FIXME: this code is an adaptation of twisted/spread/pb.py
# it allows you to login to a FPB server requesting interfaces other than
# IPerspective.
# in other terms, you can request different "kinds" of avatars from the same
# PB server.
# this code needs to be sent upstream to Twisted


class _FPortalRoot:
    """
    Root object, used to login to bouncer.
    """

    implements(flavors.IPBRoot)

    def __init__(self, bouncerPortal):
        """
        @type bouncerPortal: L{flumotion.twisted.portal.BouncerPortal}
        """
        self.bouncerPortal = bouncerPortal

    def rootObject(self, broker):
        return _BouncerWrapper(self.bouncerPortal, broker)


class _BouncerWrapper(pb.Referenceable, flog.Loggable):

    logCategory = "_BouncerWrapper"

    def __init__(self, bouncerPortal, broker):
        self.bouncerPortal = bouncerPortal
        self.broker = broker

    def remote_getKeycardClasses(self):
        """
        @returns: the fully-qualified class names of supported keycard
                  interfaces
        @rtype:   L{twisted.internet.defer.Deferred} firing list of str
        """
        return self.bouncerPortal.getKeycardClasses()

    def remote_login(self, keycard, mind, *interfaces):
        """
        Start of keycard login.

        @param interfaces: list of fully qualified names of interface objects

        @returns: one of
            - a L{flumotion.common.keycards.Keycard} when more steps
              need to be performed
            - a L{twisted.spread.pb.AsReferenceable} when authentication
              has succeeded, which will turn into a
              L{twisted.spread.pb.RemoteReference} on the client side
            - a L{flumotion.common.errors.NotAuthenticatedError} when
              authentication is denied
        """

        def loginResponse(result):
            self.log("loginResponse: result=%r", result)
            # if the result is a keycard, we're not yet ready
            if isinstance(result, keycards.Keycard):
                return result
            else:
                # authenticated, so the result is the tuple
                interface, perspective, logout = result
                self.broker.notifyOnDisconnect(logout)
                return pb.AsReferenceable(perspective, "perspective")

        # corresponds with FPBClientFactory._cbSendKeycard
        self.log("remote_login(keycard=%s, *interfaces=%r" % (
            keycard, interfaces))
        interfaces = [freflect.namedAny(interface) for interface in interfaces]
        d = self.bouncerPortal.login(keycard, mind, *interfaces)
        d.addCallback(loginResponse)
        return d


class Authenticator(flog.Loggable, pb.Referenceable):
    """
    I am an object used by FPB clients to create keycards for me
    and respond to challenges.

    I encapsulate keycard-related data, plus secrets which are used locally
    and not put on the keycard.

    I can be serialized over PB connections to a RemoteReference and then
    adapted with RemoteAuthenticator to present the same interface.

    @cvar username: a username to log in with
    @type username: str
    @cvar password: a password to log in with
    @type password: str
    @cvar address:  an address to log in from
    @type address:  str
    @cvar avatarId: the avatarId we want to request from the PB server
    @type avatarId: str
    """
    logCategory = "authenticator"

    avatarId = None

    username = None
    password = None
    address = None
    ttl = 30
    # FIXME: we can add ssh keys and similar here later on

    def __init__(self, **kwargs):
        for key in kwargs:
            setattr(self, key, kwargs[key])

    def issue(self, keycardClasses):
        """
        Issue a keycard that implements one of the given interfaces.

        @param keycardClasses: list of fully qualified keycard classes
        @type  keycardClasses: list of str

        @rtype: L{twisted.internet.defer.Deferred} firing L{keycards.Keycard}
        """
        # this method returns a deferred so we present the same interface
        # as the RemoteAuthenticator adapter

        # construct a list of keycard interfaces we can support right now
        supported = []
        # address is allowed to be None
        if self.username is not None and self.password is not None:
            # We only want to support challenge-based keycards, for
            # security. Maybe later we want this to be configurable
            # supported.append(keycards.KeycardUACPP)
            supported.append(keycards.KeycardUACPCC)
            supported.append(keycards.KeycardUASPCC)

        # expand to fully qualified names
        supported = [reflect.qual(k) for k in supported]

        for i in keycardClasses:
            if i in supported:
                self.log('Keycard interface %s supported, looking up', i)
                name = i.split(".")[-1]
                methodName = "issue_%s" % name
                method = getattr(self, methodName)
                keycard = method()
                self.debug('Issuing keycard %r of class %s', keycard,
                           name)
                keycard.avatarId = self.avatarId
                if self.ttl is not None:
                    keycard.ttl = self.ttl
                return defer.succeed(keycard)

        self.debug('Could not issue a keycard')
        return defer.succeed(None)

    # non-challenge types

    def issue_KeycardUACPP(self):
        return keycards.KeycardUACPP(self.username, self.password,
            self.address)

    def issue_KeycardGeneric(self):
        keycard = keycards.KeycardGeneric()
        keycard.username = self.username
        keycard.address = self.address
        return keycard
    # challenge types

    def issue_KeycardUACPCC(self):
        return keycards.KeycardUACPCC(self.username, self.address)

    def issue_KeycardUASPCC(self):
        return keycards.KeycardUASPCC(self.username, self.address)

    def respond(self, keycard):
        """
        Respond to a challenge on the given keycard, based on the secrets
        we have.

        @param keycard: the keycard with the challenge to respond to
        @type  keycard: L{keycards.Keycard}

        @rtype:   L{twisted.internet.defer.Deferred} firing
                  a {keycards.Keycard}
        @returns: a deferred firing the keycard with a response set
        """
        self.debug('responding to challenge on keycard %r' % keycard)
        methodName = "respond_%s" % keycard.__class__.__name__
        method = getattr(self, methodName)
        return defer.succeed(method(keycard))

    def respond_KeycardUACPCC(self, keycard):
        self.log('setting password')
        keycard.setPassword(self.password)
        return keycard

    def respond_KeycardUASPCC(self, keycard):
        self.log('setting password')
        keycard.setPassword(self.password)
        return keycard

    ### pb.Referenceable methods

    def remote_issue(self, interfaces):
        return self.issue(interfaces)

    def remote_respond(self, keycard):
        return self.respond(keycard)


class RemoteAuthenticator:
    """
    I am an adapter for a pb.RemoteReference to present the same interface
    as L{Authenticator}
    """

    avatarId = None # not serialized
    username = None # for convenience, will always be None
    password = None # for convenience, will always be None

    def __init__(self, remoteReference):
        self._remote = remoteReference

    def copy(self, avatarId=None):
        ret = RemoteAuthenticator(self._remote)
        ret.avatarId = avatarId or self.avatarId
        return ret

    def issue(self, interfaces):

        def issueCb(keycard):
            keycard.avatarId = self.avatarId
            return keycard

        d = self._remote.callRemote('issue', interfaces)
        d.addCallback(issueCb)
        return d

    def respond(self, keycard):
        return self._remote.callRemote('respond', keycard)


class Referenceable(pb.Referenceable, flog.Loggable):
    """
    @cvar remoteLogName: name to use to log the other side of the connection
    @type remoteLogName: str
    """
    logCategory = 'referenceable'
    remoteLogName = 'remote'


    # a referenceable that logs receiving remote messages

    def remoteMessageReceived(self, broker, message, args, kwargs):
        args = broker.unserialize(args)
        kwargs = broker.unserialize(kwargs)
        method = getattr(self, "remote_%s" % message, None)
        if method is None:
            raise pb.NoSuchMethod("No such method: remote_%s" % (message, ))

        level = flog.DEBUG
        if message == 'ping':
            level = flog.LOG

        debugClass = self.logCategory.upper()
        # all this malarkey is to avoid actually interpolating variables
        # if it is not needed
        startArgs = [self.remoteLogName, debugClass, message]
        format, debugArgs = flog.getFormatArgs(
            '%s --> %s: remote_%s(', startArgs,
            ')', (), args, kwargs)
        # log going into the method
        logKwArgs = self.doLog(level, method, format, *debugArgs)

        # invoke the remote_ method
        d = defer.maybeDeferred(method, *args, **kwargs)

        # log coming out of the method

        def callback(result):
            format, debugArgs = flog.getFormatArgs(
                '%s <-- %s: remote_%s(', startArgs,
                '): %r', (flog.ellipsize(result), ), args, kwargs)
            self.doLog(level, -1, format, *debugArgs, **logKwArgs)
            return result

        def errback(failure):
            format, debugArgs = flog.getFormatArgs(
                '%s <-- %s: remote_%s(', startArgs,
                '): failure %r', (failure, ), args, kwargs)
            self.doLog(level, -1, format, *debugArgs, **logKwArgs)
            return failure

        d.addCallbacks(callback, errback)
        return broker.serialize(d, self.perspective)


class Avatar(pb.Avatar, flog.Loggable):
    """
    @cvar remoteLogName: name to use to log the other side of the connection
    @type remoteLogName: str
    """
    logCategory = 'avatar'
    remoteLogName = 'remote'

    def __init__(self, avatarId):
        self.avatarId = avatarId
        self.logName = avatarId
        self.mind = None
        self.debug("created new Avatar with id %s", avatarId)

    # a referenceable that logs receiving remote messages

    def perspectiveMessageReceived(self, broker, message, args, kwargs):
        args = broker.unserialize(args)
        kwargs = broker.unserialize(kwargs)
        return self.perspectiveMessageReceivedUnserialised(broker, message,
            args, kwargs)

    def perspectiveMessageReceivedUnserialised(self, broker, message,
            args, kwargs):
        method = getattr(self, "perspective_%s" % message, None)
        if method is None:
            raise pb.NoSuchMethod("No such method: perspective_%s" % (
                message, ))

        level = flog.DEBUG
        if message == 'ping':
            level = flog.LOG
        debugClass = self.logCategory.upper()
        startArgs = [self.remoteLogName, debugClass, message]
        format, debugArgs = flog.getFormatArgs(
            '%s --> %s: perspective_%s(', startArgs,
            ')', (), args, kwargs)
        # log going into the method
        logKwArgs = self.doLog(level, method, format, *debugArgs)

        # invoke the perspective_ method
        d = defer.maybeDeferred(method, *args, **kwargs)

        # log coming out of the method

        def callback(result):
            format, debugArgs = flog.getFormatArgs(
                '%s <-- %s: perspective_%s(', startArgs,
                '): %r', (flog.ellipsize(result), ), args, kwargs)
            self.doLog(level, -1, format, *debugArgs, **logKwArgs)
            return result

        def errback(failure):
            format, debugArgs = flog.getFormatArgs(
                '%s <-- %s: perspective_%s(', startArgs,
                '): failure %r', (failure, ), args, kwargs)
            self.doLog(level, -1, format, *debugArgs, **logKwArgs)
            return failure

        d.addCallbacks(callback, errback)

        return broker.serialize(d, self, method, args, kwargs)

    def setMind(self, mind):
        """
        Tell the avatar that the given mind has been attached.
        This gives the avatar a way to call remotely to the client that
        requested this avatar.

        It is best to call setMind() from within the avatar's __init__
        method. Some old code still does this via a callLater, however.

        @type mind: L{twisted.spread.pb.RemoteReference}
        """
        self.mind = mind

        def nullMind(x):
            self.debug('%r: disconnected from %r' % (self, self.mind))
            self.mind = None
        self.mind.notifyOnDisconnect(nullMind)

        transport = self.mind.broker.transport
        tarzan = transport.getHost()
        jane = transport.getPeer()
        if tarzan and jane:
            self.debug(
                "PB client connection seen by me is from me %s to %s" % (
                addressGetHost(tarzan),
                addressGetHost(jane)))
        self.log('Client attached is mind %s', mind)

    def mindCallRemoteLogging(self, level, stackDepth, name, *args,
                              **kwargs):
        """
        Call the given remote method, and log calling and returning nicely.

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
            format, debugArgs = flog.getFormatArgs(
                '%s --> %s: callRemote(%s, ', startArgs,
                ')', (), args, kwargs)
            logKwArgs = self.doLog(level, stackDepth - 1, format,
                                   *debugArgs)

        if not self.mind:
            self.warning('Tried to mindCallRemote(%s), but we are '
                         'disconnected', name)
            return defer.fail(errors.NotConnectedError())

        def callback(result):
            format, debugArgs = flog.getFormatArgs(
                '%s <-- %s: callRemote(%s, ', startArgs,
                '): %r', (flog.ellipsize(result), ), args, kwargs)
            self.doLog(level, -1, format, *debugArgs, **logKwArgs)
            return result

        def errback(failure):
            format, debugArgs = flog.getFormatArgs(
                '%s <-- %s: callRemote(%s, ', startArgs,
                '): %r', (failure, ), args, kwargs)
            self.doLog(level, -1, format, *debugArgs, **logKwArgs)
            return failure

        d = self.mind.callRemote(name, *args, **kwargs)
        if level is not None:
            d.addCallbacks(callback, errback)
        return d

    def mindCallRemote(self, name, *args, **kwargs):
        """
        Call the given remote method, and log calling and returning nicely.

        @param name: name of the remote method
        @type  name: str
        """
        return self.mindCallRemoteLogging(flog.DEBUG, -1, name, *args,
                                          **kwargs)

    def disconnect(self):
        """
        Disconnect the remote PB client. If we are already disconnected,
        do nothing.
        """
        if self.mind:
            return self.mind.broker.transport.loseConnection()


class PingableAvatar(Avatar):
    _pingCheckInterval = (configure.heartbeatInterval *
                          configure.pingTimeoutMultiplier)

    def __init__(self, avatarId, clock=reactor):
        self._clock = clock
        Avatar.__init__(self, avatarId)

    def perspectiveMessageReceivedUnserialised(self, broker, message,
            args, kwargs):
        self._lastPing = self._clock.seconds()
        return Avatar.perspectiveMessageReceivedUnserialised(
            self, broker, message, args, kwargs)

    def perspective_ping(self):
        return defer.succeed(True)

    def mindCallRemoteLogging(self, level, stackDepth, name, *args,
                              **kwargs):
        d = Avatar.mindCallRemoteLogging(self, level, stackDepth, name, *args,
                                         **kwargs)

        def cb(result):
            self._lastPing = self._clock.seconds()
            return result
        d.addCallback(cb)
        return d

    def startPingChecking(self, disconnect):
        self._lastPing = self._clock.seconds()
        self._pingCheckDisconnect = disconnect
        self._pingCheck()

    def _pingCheck(self):
        self._pingCheckDC = None
        if self._clock.seconds() - self._lastPing > self._pingCheckInterval:
            self.info('no ping in %f seconds, closing connection',
                      self._pingCheckInterval)
            self._pingCheckDisconnect()
        else:
            self._pingCheckDC = self._clock.callLater(self._pingCheckInterval,
                                                      self._pingCheck)

    def stopPingChecking(self):
        if self._pingCheckDC:
            self._pingCheckDC.cancel()
        self._pingCheckDC = None

        # release the disconnect function, too, to help break any
        # potential cycles
        self._pingCheckDisconnect = None

    def setMind(self, mind):
        # chain up
        Avatar.setMind(self, mind)

        def stopPingCheckingCb(x):
            self.debug('stop pinging')
            self.stopPingChecking()
        self.mind.notifyOnDisconnect(stopPingCheckingCb)

        # Now we have a remote reference, so start checking pings.

        def _disconnect():
            if self.mind:
                self.mind.broker.transport.loseConnection()
        self.startPingChecking(_disconnect)
