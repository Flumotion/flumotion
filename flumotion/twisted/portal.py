# -*- Mode: Python -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# flumotion/twisted/portal.py: portal stuff
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

import md5

from twisted.cred.portal import IRealm, Portal
from twisted.python.components import registerAdapter
from twisted.spread import pb
from twisted.spread import flavors

### stolen from twisted.python.reflect and changed
### the version in Twisted 1.3.0 checks length of backtrace as metric for
### ImportError; for me this fails because two lines of ihooks.py are in
### between
### filed as http://www.twistedmatrix.com/users/roundup.twistd/twisted/issue698
### remove this when fixed and depending on new upstream twisted
def namedAny(name):
    """Get a fully named package, module, module-global object, or attribute.
    """
    names = name.split('.')
    topLevelPackage = None
    moduleNames = names[:]
    while not topLevelPackage:
        try:
            trialname = '.'.join(moduleNames)
            topLevelPackage = __import__(trialname)
        except ImportError:
            import sys
            # if the ImportError happened in the module being imported,
            # this is a failure that should be handed to our caller.
            shortname = trialname.split('.')[-1]
            r = str(sys.exc_info()[1])
            if not (r.startswith('No module named') and
                    r.endswith(shortname)):
                raise
            
            #if str(sys.exc_info()[1]) != "No module named %s" % trialname:
            #    raise
            moduleNames.pop()
                                                                                
    obj = topLevelPackage
    for n in names[1:]:
        obj = getattr(obj, n)
                                                                                
    return obj

class FlumotionPortal(Portal):
    pass

class _PortalRoot:
    """Root object, used to login to portal."""

    __implements__ = flavors.IPBRoot,
    
    def __init__(self, portal):
        self.portal = portal

    def rootObject(self, broker):
        return _PortalWrapper(self.portal, broker)

registerAdapter(_PortalRoot, FlumotionPortal, flavors.IPBRoot)

class _PortalWrapper(pb.Referenceable):
    """Root Referenceable object, used to login to portal."""

    def __init__(self, portal, broker):
        self.portal = portal
        self.broker = broker

    def remote_login(self, username, *interfaces):
        """Start of username/password login."""
        interfaces = [namedAny(interface) for interface in interfaces]
        c = pb.challenge()
        return c, _PortalAuthChallenger(self, username, c, *interfaces)

class _PortalAuthChallenger(pb.Referenceable):
    """Called with response to password challenge."""

    __implements__ = pb.IUsernameHashedPassword, pb.IUsernameMD5Password

    def __init__(self, portalWrapper, username, challenge, *interfaces):
        self.portalWrapper = portalWrapper
        self.username = username
        self.challenge = challenge
        self.interfaces = interfaces
        
    def remote_respond(self, response, mind):
        self.response = response
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

