# -*- Mode: Python -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# flumotion/twisted/portal.py: portal stuff; see twisted.cred.portal
#
# Flumotion - a streaming media server
# Copyright (C) 2004 Fluendo (www.fluendo.com)

# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
# See "LICENSE.GPL" in the source distribution for more information.

# This program is also licensed under the Flumotion license.
# See "LICENSE.Flumotion" in the source distribution for more information.

from twisted.spread import flavors
from twisted.internet import defer
from twisted.cred import error
from twisted.cred.portal import Portal
from twisted.python import failure
from twisted.python.components import registerAdapter

from flumotion.common import keycards, log
from flumotion.twisted.pb import _FPortalRoot

"""
Portal-related functionality inspired by twisted.cred.portal
"""

class BouncerPortal(log.Loggable):
    """
    I am a portal for an FPB server using a bouncer to decide on FPB client
    access.
    """
    def __init__(self, realm, bouncer):
        """
        Create a BouncerPortal to a L{twisted.cred.portal.IRealm}.

        @param realm:   an implementor of L{twisted.cred.portal.IRealm}
        @param bouncer: a bouncer to use for authentication
        @type  bouncer: L{flumotion.component.bouncers.bouncer.Bouncer}
        """
        self.realm = realm
        self.bouncer = bouncer

    def login(self, keycard, mind, *interfaces):
        """
        Log in the keycard to the portal using the bouncer.

        @param keycard:    the keycard used to login
        @type  keycard:    L{flumotion.common.keycards.Keycard}
        @param mind:       a reference to the client-side requester
        @type  mind:       L{twisted.spread.pb.RemoteReference}
        @param interfaces: a list of interfaces for the perspective that the
                           mind wishes to attach to
        
        @returns: a deferred which will fire a tuple of
                  (interface, avatarAspect, logout)
        """
        self.debug("BouncerPortal._login(keycard=%r, mind=%r, interfaces=%r)" % (keycard, mind, interfaces))
        if not self.bouncer:
            # FIXME: do we really want anonymous login when no bouncer is
            # present ?
            self.warning("BouncerPortal has no bouncer, allowing anonymous in")
            keycard.state = keycards.AUTHENTICATED
            d = defer.maybeDeferred(lambda x: x, keycard)
        else:
            d = defer.maybeDeferred(self.bouncer.authenticate, keycard)
            
        d.addCallback(self._authenticateCallback, mind, *interfaces)
        return d

    def _authenticateCallback(self, result, mind, *interfaces):
        self.debug("BouncerPortal._authenticateCallback(result=%r, mind=%r, interfaces=%r)" % (result, mind, interfaces))
        if not result:
            f = failure.Failure(error.UnauthorizedLogin())
            self.debug("BouncerPortal._authenticateCallback: returning deferred failure %r" % f)
            return defer.fail(f)

        keycard = result
        if not keycard.state == keycards.AUTHENTICATED:
            # challenge
            self.debug("BouncerPortal._authenticateCallback: returning keycard for further authentication")
            return keycard

        self.debug("BouncerPortal._authenticateCallback(%r), chaining through to next callback to request AvatarId from realm with mind %r and interfaces %r" % (result, mind, interfaces))

        return self.realm.requestAvatar(keycard.avatarId, mind, *interfaces)
registerAdapter(_FPortalRoot, BouncerPortal, flavors.IPBRoot)
