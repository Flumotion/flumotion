# -*- Mode: Python -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# flumotion/common/keycard.py: keycard stuff
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

from twisted.cred import credentials
from twisted.spread import pb

# create basic subclass

class HTTPClientKeycard(credentials.UsernamePassword):
    
    __implements__ = credentials.ICredentials,
    
    def __init__(self, username, password, ip):
        credentials.UsernamePassword.__init__(self, username, password)
        self.username = username
        self.password = password
        self.ip = ip
        
    def getUsername(self):
        return self.username

    def getPassword(self):
        return self.password

    def getIP(self):
        return self.ip

class CopyHTTPClientKeycard(HTTPClientKeycard, pb.Copyable):
    pass

class RemoteCopyHTTPClientKeycard(HTTPClientKeycard, pb.RemoteCopy):
    pass
pb.setUnjellyableForClass(CopyHTTPClientKeycard, RemoteCopyHTTPClientKeycard)
