# -*- Mode: Python -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# flumotion/twisted/portal.py: portal stuff; see twisted.cred.portal
#
# Flumotion - a streaming media server
# Copyright (C) 2004 Fluendo, S.L. (www.fluendo.com). All rights reserved.

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

from twisted.spread import flavors
from twisted.internet import defer
from twisted.cred import error
from twisted.cred.portal import Portal
from twisted.python import failure
from twisted.python.components import registerAdapter

from flumotion.common import keycards, log, interfaces
from flumotion.twisted.pb import _FPortalRoot

"""
Portal-related functionality inspired by twisted.cred.portal
"""

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

    def login(self, keycard, mind, *ifaces):
        """
        Log in the keycard to the portal using the bouncer.

        @param keycard:    the keycard used to login
        @type  keycard:    L{flumotion.common.keycards.Keycard}
        @param mind:       a reference to the client-side requester
        @type  mind:       L{twisted.spread.pb.RemoteReference}
        @param ifaces:     a list of interfaces for the perspective that the
                           mind wishes to attach to
        
        @returns: a deferred which will fire a tuple of
                  (interface, avatarAspect, logout), or a failure.
        """
        self.debug("_login(keycard=%r, mind=%r, ifaces=%r)" % (
            keycard, mind, ifaces))
        if not self.bouncer:
            # FIXME: do we really want anonymous login when no bouncer is
            # present ?
            self.warning("no bouncer, allowing anonymous in")
            keycard.state = keycards.AUTHENTICATED
            d = defer.succeed(keycard)
        else:
            d = defer.maybeDeferred(self.bouncer.authenticate, keycard)
            
        d.addCallback(self._authenticateCallback, mind, *ifaces)
        return d

    def _authenticateCallback(self, result, mind, *ifaces):
        # we either got a keycard as result, or None from the bouncer
        self.debug("_authenticateCallback(result=%r, mind=%r, ifaces=%r)" % (result, mind, ifaces))

        if not result:
            # just like a checker, we return a failure object
            f = failure.Failure(error.UnauthorizedLogin())
            self.debug("_authenticateCallback: returning failure %r" % f)
            return f

        keycard = result
        if not keycard.state == keycards.AUTHENTICATED:
            # challenge
            self.debug("_authenticateCallback: returning keycard for further authentication")
            return keycard

        self.debug("_authenticateCallback(%r), chaining through to next callback to request AvatarId from realm with mind %r and ifaces %r" % (result, mind, ifaces))

        # this is where we request the Avatar and can influence naming
        
        if interfaces.IAdminMedium in ifaces:
            # we decide on a unique name for admin clients here
            keycard.avatarId = "admin-%06x" % self._adminCounter
            self._adminCounter += 1

        return self.realm.requestAvatar(keycard.avatarId, mind, *ifaces)
registerAdapter(_FPortalRoot, BouncerPortal, flavors.IPBRoot)
