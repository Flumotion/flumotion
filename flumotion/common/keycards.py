# -*- Mode: Python; test-case-name: flumotion.test.test_keycards -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# flumotion/common/keycards.py: keycard stuff
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
Keycards used for authentication.  Jellyable over PB connections.
"""

from twisted.cred import credentials as tcredentials
from twisted.spread import pb

from flumotion.twisted import credentials

# state enum values
REFUSED = 0
REQUESTING = 1
ACCEPTED = 2

class Keycard(pb.Copyable, pb.RemoteCopy):

    __implements__ = tcredentials.ICredentials,

    def __init__(self):
        self.bouncerName = None         # set by requester,decides which bouncer
        self.requesterName = None       # who is requesting auth ?
        self.avatarId = None            # avatarId prefered by requester
        self.id = None                  # set by bouncer when authenticated
        self.duration = 0               # means unlimited
        self.state = REQUESTING

# class KeycardUAPP: username, address, plaintext password;
#       from UsernameCryptPasswordPlaintext
# class KeycardUACP: username, address, crypt password
#       from UsernameCryptPasswordCrypt

credParent = credentials.UsernameCryptPasswordCryptChallenger
class KeycardUACPC(Keycard, credParent):

    """
    I am a keycard with a username and IP address.
    I get authenticated through challenge/response on a crypt password.
    """
    def __init__(self, username, address):
        Keycard.__init__(self)
        credParent.__init__(self, username)
        self.address = address

# FIXME: rewrite
class HTTPClientKeycard(tcredentials.UsernamePassword, Keycard):
    def __init__(self, componentName, username, password, ip):
        tcredentials.UsernamePassword.__init__(self, username, password)
        Keycard.__init__(self)
        self.requesterName = componentName
        self.username = username
        self.password = password
        self.ip = ip
        
# fixme: remove methods
    def getUsername(self):
        return self.username

    def getPassword(self):
        return self.password

    def getIP(self):
        return self.ip

pb.setUnjellyableForClass(HTTPClientKeycard, HTTPClientKeycard)
