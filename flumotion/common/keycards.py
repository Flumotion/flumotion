# -*- Mode: Python; test-case-name: flumotion.test.test_keycards -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# flumotion/common/keycards.py: keycard stuff
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
