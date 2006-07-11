# -*- Mode: Python  -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# Flumotion - a streaming media server
# Copyright (C) 2004,2005,2006 Fluendo, S.L. (www.fluendo.com).
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

"""
Manager-side representations of the identity of an avatar.
"""

class RemoteIdentity(object):
    """
    Representation of the identity of a remote avatar.

    This object only exists for the AdminAction socket, defined in
    L{flumotion.component.plugs.adminaction}. This base class exists to
    hold the username and host of the remote avatar, and also to serve
    as a point of extensibility for the IdentityProvider socket, defined
    in L{flumotion.component.plugs.identity}.
    """

    def __init__(self, username, host):
        self.username = username
        self.host = host

    def __str__(self):
        return '%s@%s' % (self.username or '<unknown user>',
                          self.host or '<unknown host>')
