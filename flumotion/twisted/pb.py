# -*- Mode: Python -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# flumotion/twisted/pb.py: Persistent broker functions; see twisted.spread.pb
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

"""
Base classes handy for use with PB clients.
"""

import md5

from twisted.cred import checkers, credentials
from twisted.cred.portal import IRealm, Portal
from twisted.internet import protocol
from twisted.python import log, reflect
from twisted.spread import pb, flavors
from twisted.spread.pb import PBClientFactory

from flumotion.twisted import reflect as freflect
# TODO:
#   subclass FMClientFactory
#   merge FMCF back into twisted
#
class ReconnectingPBClientFactory(PBClientFactory,
                                  protocol.ReconnectingClientFactory):
    """Reconnecting client factory for PB brokers.

    Like PBClientFactory, but if the connection fails or is lost, the factory
    will attempt to reconnect.

    Instead of using f.getRootObject (which gives a Deferred that can only
    be fired once), override the gotRootObject method.

    Instead of using the newcred f.login (which is also one-shot), call
    f.startLogin() with the credentials and client, and override the
    gotPerspective method.

    Instead of using the oldcred f.getPerspective (also one-shot), call
    f.startGettingPerspective() with the same arguments, and override
    gotPerspective.

    gotRootObject and gotPerspective will be called each time the object is
    received (once per successful connection attempt). You will probably want
    to use obj.notifyOnDisconnect to find out when the connection is lost.

    If an authorization error occurs, failedToGetPerspective() will be
    invoked.

    To use me, subclass, then hand an instance to a connector (like
    TCPClient).
    """

    def __init__(self):
        PBClientFactory.__init__(self)
        self._doingLogin = False
        self._doingGetPerspective = False
        
    def clientConnectionFailed(self, connector, reason):
        PBClientFactory.clientConnectionFailed(self, connector, reason)
        RCF = protocol.ReconnectingClientFactory
        RCF.clientConnectionFailed(self, connector, reason)

    def clientConnectionLost(self, connector, reason):
        PBClientFactory.clientConnectionLost(self, connector, reason,
                                             reconnecting=True)
        RCF = protocol.ReconnectingClientFactory
        RCF.clientConnectionLost(self, connector, reason)

    def clientConnectionMade(self, broker):
        self.resetDelay()
        PBClientFactory.clientConnectionMade(self, broker)
        if self._doingLogin:
            self.doLogin(self._root)
        if self._doingGetPerspective:
            self.doGetPerspective(self._root)
        self.gotRootObject(self._root)

    def __getstate__(self):
        # this should get folded into ReconnectingClientFactory
        d = self.__dict__.copy()
        d['connector'] = None
        d['_callID'] = None
        return d

    # oldcred methods

    def getPerspective(self, *args):
        raise RuntimeError, "getPerspective is one-shot: use startGettingPerspective instead"

    def startGettingPerspective(self, username, password, serviceName,
                                perspectiveName=None, client=None):
        self._doingGetPerspective = True
        if perspectiveName == None:
            perspectiveName = username
        self._oldcredArgs = (username, password, serviceName,
                             perspectiveName, client)

    def doGetPerspective(self, root):
        # oldcred getPerspective()
        (username, password,
         serviceName, perspectiveName, client) = self._oldcredArgs
        d = self._cbAuthIdentity(root, username, password)
        d.addCallback(self._cbGetPerspective,
                      serviceName, perspectiveName, client)
        d.addCallbacks(self.gotPerspective, self.failedToGetPerspective)


    # newcred methods

    def login(self, *args):
        raise RuntimeError, "login is one-shot: use startLogin instead"

    def startLogin(self, credentials, avatarId, client, *interfaces):
        if not pb.IPerspective in interfaces:
            interfaces += (pb.IPerspective,)
        self._interfaces = [reflect.qual(interface)
                               for interface in interfaces]
        self._credentials = credentials
        self._avatarId = avatarId
        self._client = client
        
        self._doingLogin = True
        
    def doLogin(self, root):
        # newcred login()
        d = self._cbSendUsername(root,
                                 self._credentials.username,
                                 self._credentials.password,
                                 self._avatarId,
                                 self._client,
                                 self._interfaces)
        d.addCallbacks(self.gotPerspective, self.failedToGetPerspective)

    def _cbSendUsername(self, root, username, password, avatarId, client, interfaces):
        return root.callRemote("login", username, avatarId, *interfaces).addCallback(
            self._cbResponse, password, client)

    # methods to override

    def gotPerspective(self, perspective):
        """The remote avatar or perspective (obtained each time this factory
        connects) is now available."""
        pass

    def gotRootObject(self, root):
        """The remote root object (obtained each time this factory connects)
        is now available. This method will be called each time the connection
        is established and the object reference is retrieved."""
        pass

    def failedToGetPerspective(self, why):
        self.stopTrying() # logging in harder won't help
        log.err(why)

# we made two changes to the standard PBClientFactory
# first of all, you can request a specific interface for the avatar to
# implement, instead of only IPerspective
# second, you can express your wish for an avatarId, by setting an
# avatarId member on the credentials you give to login()
# this way you can request a different avatarId than the user you authenticate
# with
class FMClientFactory(pb.PBClientFactory):
    def _cbSendUsername(self, root, username, password, avatarId, client, interfaces):
        d = root.callRemote("login", username, avatarId, *interfaces)
        return d.addCallback(self._cbResponse, password, client)

    def login(self, credentials, client=None, *interfaces):
        """
        Login and get perspective from remote PB server.

        Currently only credentials implementing IUsernamePassword are
        supported.

        @return: Deferred of RemoteReference to the perspective.
        """
        
        if not pb.IPerspective in interfaces:
            interfaces += (pb.IPerspective,)
        interfaces = [reflect.qual(interface)
                          for interface in interfaces]
            
        d = self.getRootObject()
        avatarId = getattr(credentials, 'avatarId', None)
        d.addCallback(self._cbSendUsername,
                      credentials.username,
                      credentials.password,
                      avatarId,
                      client,
                      interfaces)
        return d

### FIXME: this code is an adaptation of twisted/spread/pb.py
# it allows you to login to a PB server requesting interfaces other than
# IPerspective.
# in other terms, you can request different "kinds" of avatars from the same
# PB server.
# this code needs to be send upstream to Twisted
class _PortalRoot:
    """Root object, used to login to portal."""

    __implements__ = flavors.IPBRoot,
    
    def __init__(self, portal):
        self.portal = portal

    def rootObject(self, broker):
        return _PortalWrapper(self.portal, broker)

class _PortalWrapper(pb.Referenceable):
    """Root Referenceable object, used to login to portal."""

    def __init__(self, portal, broker):
        self.portal = portal
        self.broker = broker

    def remote_login(self, username, avatarId, *interfaces):
        # corresponds with FMClientFactory._cbSendUsername
        """Start of username/password login."""
        interfaces = [freflect.namedAny(interface) for interface in interfaces]
        c = pb.challenge()
        return c, _PortalAuthChallenger(self, username, avatarId, c, *interfaces)

class _PortalAuthChallenger(pb.Referenceable):
    # I am a credentials created pb.server side to be presented to the
    # portal
    """Called with response to password challenge."""

    __implements__ = pb.IUsernameHashedPassword, pb.IUsernameMD5Password

    def __init__(self, portalWrapper, username, avatarId, challenge, *interfaces):
        self.portalWrapper = portalWrapper
        self.username = username
        self.challenge = challenge
        self.interfaces = interfaces
        self.avatarId = avatarId

        self.componentName = "manager" # because we give this to a bouncer
        
    def remote_respond(self, response, mind):
        self.response = response
        # avatarId is now again a member of the credentials,
        # so since we pass ourselves to the portal's login, which
        # will use the checker, the checker can get our desired avatarId !
        d = self.portalWrapper.portal.login(self, mind, *self.interfaces)
        d.addCallback(self._loggedIn)
        return d

    def _loggedIn(self, (interface, perspective, logout)):
        self.portalWrapper.broker.notifyOnDisconnect(logout)
        return pb.AsReferenceable(perspective, "perspective")

    # IUsernameHashedPassword:
    def checkPassword(self, password):
        return self.checkMD5Password(md5.md5(password).digest())

    # IUsernameMD5Password
    def checkMD5Password(self, md5Password):
        md = md5.new()
        md.update(md5Password)
        md.update(self.challenge)
        correct = md.digest()
        return self.response == correct

