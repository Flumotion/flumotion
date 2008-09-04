# -*- Mode: Python  -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# Flumotion - a streaming media server
# Copyright (C) 2004,2005,2006,2007 Fluendo, S.L. (www.fluendo.com).
# All rights reserved.

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

"""manager-side identities of objects.
Manager-side identities of objects that can request operations
from the manager.
"""

__version__ = "$Rev$"


class Identity:
    """
    I represent the identity of an object that can ask the manager to
    perform functions.

    I exist for the AdminAction socket, defined in
    L{flumotion.component.plugs.adminaction}, so that specific actions
    can be taken when I request to perform a function.

    I serve as a point of extensibility for the IdentityProviderPlug socket,
    defined in L{flumotion.component.plugs.identity}.

    Subclasses should only implement __str__
    """

    def __str__(self):
        raise NotImplementedError


class LocalIdentity(Identity):
    """
    I represent a local identity.
    """

    def __init__(self, name):
        self.name = name

    def __str__(self):
        return "<%s>" % self.name


class RemoteIdentity(Identity):
    """
    I represent the identity of a remote avatar.

    I hold the username and host of the remote avatar.
    """

    def __init__(self, username, host):
        self.username = username
        self.host = host

    def __str__(self):
        return '%s@%s' % (self.username or '<unknown user>',
                          self.host or '<unknown host>')
