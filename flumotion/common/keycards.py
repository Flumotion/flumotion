# -*- Mode: Python -*-
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

from twisted.cred import credentials
from twisted.spread import pb

class Keycard(pb.Copyable, pb.RemoteCopy):

    __implements__ = credentials.ICredentials,

    def __init__(self, componentName):
        self.componentName = componentName
        self.id = None # set by bouncer when authenticated


class HTTPClientKeycard(credentials.UsernamePassword, Keycard):
    def __init__(self, componentName, username, password, ip):
        credentials.UsernamePassword.__init__(self, username, password)
        Keycard.__init__(self, componentName)
        self.username = username
        self.password = password
        self.ip = ip
        
    def getUsername(self):
        return self.username

    def getPassword(self):
        return self.password

    def getIP(self):
        return self.ip

pb.setUnjellyableForClass(HTTPClientKeycard, HTTPClientKeycard)
