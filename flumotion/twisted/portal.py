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

### FIXME: deprecate FlumotionPortal
# we create a dummy subclass because there is already an adapter registered
# for Portal in twisted.spread.pb
class FlumotionPortal(Portal):
    pass
registerAdapter(_FPortalRoot, FlumotionPortal, flavors.IPBRoot)

# FIXME: rename
class BouncerPortal(log.Loggable):
    def __init__(self, realm, bouncer):
        """Create a BouncerPortal to a L{IRealm}.
        """
        self.realm = realm
        self.bouncer = bouncer

    def login(self, keycard, mind, *interfaces):
        self.debug("BouncerPortal._login(keycard=%r, mind=%r, interfaces=%r)" % (keycard, mind, interfaces))
        d = defer.maybeDeferred(self.bouncer.authenticate, keycard)
        d.addCallback(self._authenticateCallback, mind, *interfaces)
        #d.addCallback(self.realm.requestAvatar, mind, *interfaces)
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
            return keycard

        self.debug("BouncerPortal._authenticateCallback(%r), chaining through to next callback to request AvatarId from realm with mind %r and interfaces %r" % (result, mind, interfaces))
        return self.realm.requestAvatar(keycard.avatarId, mind, *interfaces)
registerAdapter(_FPortalRoot, BouncerPortal, flavors.IPBRoot)
