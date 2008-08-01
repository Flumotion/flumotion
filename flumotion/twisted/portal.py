# -*- Mode: Python -*-
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
portal-related functionality inspired by twisted.cred.portal
"""

from twisted.spread import flavors
from twisted.internet import defer
from twisted.cred.portal import Portal
from twisted.python import failure, reflect
from twisted.python.components import registerAdapter

from flumotion.common import keycards, log, interfaces, errors
from flumotion.twisted.pb import _FPortalRoot

__version__ = "$Rev$"


class BouncerPortal(log.Loggable):
    """
    I am a portal for an FPB server using a bouncer to decide on FPB client
    access.
    """

    logCategory = "BouncerPortal"

    def __init__(self, realm, bouncer):
        """
        Create a BouncerPortal to a L{twisted.cred.portal.IRealm}.

        @param realm:   an implementor of L{twisted.cred.portal.IRealm}
        @param bouncer: a bouncer to use for authentication
        @type  bouncer: L{flumotion.component.bouncers.bouncer.Bouncer}
        """
        self.realm = realm
        self.bouncer = bouncer
        self._adminCounter = 0

    def getKeycardClasses(self):
        """
        Return the Keycard interfaces supported by this portal's bouncer.

        @rtype: L{twisted.internet.defer.Deferred} firing list of str
        """
        if not self.bouncer:
            # no logins will be possible, but we can wait until they try
            # to login() to reject them
            return []
        if hasattr(self.bouncer, 'getKeycardClasses'):
            # must return a deferred
            return self.bouncer.getKeycardClasses()
        else:
            interfaces = [reflect.qual(k) for k in self.bouncer.keycardClasses]
            return defer.succeed(interfaces)

    def login(self, keycard, mind, *ifaces):
        """
        Log in the keycard to the portal using the bouncer.

        @param keycard:    the keycard used to login
        @type  keycard:    L{flumotion.common.keycards.Keycard}
        @param mind:       a reference to the client-side requester
        @type  mind:       L{twisted.spread.pb.RemoteReference}
        @param ifaces:     a list of interfaces for the perspective that the
                           mind wishes to attach to

        @returns: a deferred, which will fire a tuple of
                  (interface, avatarAspect, logout) or None.
        """
        self.debug("_login(keycard=%r, mind=%r, ifaces=%r)" % (
            keycard, mind, ifaces))

        if not self.bouncer:
            self.warning("no bouncer, refusing login")
            mind.broker.transport.loseConnection()
            return defer.fail(errors.NotAuthenticatedError(
                "No bouncer configured, no logins possible"))

        def onErrorCloseConnection(failure):
            try:
                host = mind.broker.transport.getHost()
                remote = '%s:%d' % (host.host, host.port)
            except:
                remote = '(unknown)'

            self.warning('failed login -- closing connection to %s',
                         remote)
            self.debug('failure: %s', log.getFailureMessage(failure))
            try:
                mind.broker.transport.loseConnection()
            except Exception, e:
                self.info('loseConnection failed: %s',
                          log.getExceptionMessage(e))
                # ignore it
            return failure

        def bouncerResponse(result):
            # we either got a keycard as result, or None from the
            # bouncer; would be better if the bouncers returned failures
            # directly, but that's not how the current interface works.
            if not result:
                self.info("unauthorized login for interfaces %r", ifaces)
                return defer.fail(errors.NotAuthenticatedError(
                    "Unauthorized login"))

            keycard = result
            if not keycard.state == keycards.AUTHENTICATED:
                # challenge
                self.log('returning keycard for further authentication')
                return keycard

            # this is where we request the Avatar and can influence naming
            self.debug('authenticated login of %r into realm %r', keycard,
                       self.realm)

            # FIXME: this is a hack
            if interfaces.IAdminMedium in ifaces:
                # we decide on a unique name for admin clients here
                keycard.avatarId = "admin-%06x" % self._adminCounter
                self._adminCounter += 1

            self.log(
                'calling %r.requestAvatar(keycard=%r, mind=%r, ifaces=%r)',
                self.realm, keycard, mind, ifaces)

            return self.realm.requestAvatar(keycard.avatarId,
                                            keycard, mind, *ifaces)

        if hasattr(keycard, 'address'):
            try:
                keycard.address = mind.broker.transport.getHost().host
            except:
                self.debug("can't get address of remote, setting to None")
                keycard.address = None

        d = defer.maybeDeferred(self.bouncer.authenticate, keycard)
        d.addCallback(bouncerResponse)
        d.addErrback(onErrorCloseConnection)
        return d

registerAdapter(_FPortalRoot, BouncerPortal, flavors.IPBRoot)
