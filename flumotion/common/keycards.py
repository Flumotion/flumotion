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
from flumotion.common import common

# state enum values
REFUSED = 0
REQUESTING = 1
AUTHENTICATED = 2
_statesEnum=['REFUSED', 'REQUESTING', 'AUTHENTICATED']

class Keycard(pb.Copyable, pb.RemoteCopy):
    __implements__ = common.mergeImplements(pb.Copyable, pb.RemoteCopy) + (tcredentials.ICredentials, )

    def __init__(self):
        self.bouncerName = None         # set by requester,decides which bouncer
        self.requesterName = None       # who is requesting auth ?
        self.avatarId = None            # avatarId prefered by requester
        self.id = None                  # set by bouncer when authenticated
        self.duration = 0               # means unlimited
        self.state = REQUESTING

    def __repr__(self):
        
        return "<%s in state %s>" % (self.__class__.__name__, _statesEnum[self.state])

# class KeycardUACCP: username, address, crypt password
#       from UsernameCryptPasswordCrypt

UCPP = credentials.UsernameCryptPasswordPlaintext
class KeycardUACPP(Keycard, UCPP):
    """
    I am a keycard with a username, plaintext password and IP address.
    I get authenticated against a crypt password.
    """
    __implements__ = common.mergeImplements(Keycard, UCPP)
    def __init__(self, username, password, address):
        UCPP.__init__(self, username, password)
        Keycard.__init__(self)
        self.address = address
pb.setUnjellyableForClass(KeycardUACPP, KeycardUACPP)

#: username, address, crypt password
#       from UsernameCryptPasswordCrypt

UCPCC = credentials.UsernameCryptPasswordCryptChallenger
class KeycardUACPCC(Keycard, UCPCC):
    """
    I am a keycard with a username and IP address.
    I get authenticated through challenge/response on a crypt password.
    """
    __implements__ = common.mergeImplements(Keycard, UCPCC)
    def __init__(self, username, address):
        UCPCC.__init__(self, username)
        Keycard.__init__(self)
        self.address = address
        dir(self)
pb.setUnjellyableForClass(KeycardUACPCC, KeycardUACPCC)
