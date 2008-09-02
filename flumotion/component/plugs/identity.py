# -*- Mode: Python -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# Flumotion - a streaming media server
# Copyright (C) 2006 Fluendo, S.L. (www.fluendo.com).
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

import random

from flumotion.twisted import defer

from flumotion.common.identity import RemoteIdentity
from flumotion.component.plugs import base

__version__ = "$Rev$"


class IdentityProviderPlug(base.ManagerPlug):
    """
    Base class for plugs can calculate an identity of a remote host. See
    L{flumotion.manager.manager.Vishnu.computeIdentity} for more
    information.
    """

    def computeIdentity(self, keycard, remoteHost):
        """
        @param keycard:    the keycard that the remote host used to log in.
        @type  keycard:    L{flumotion.common.keycards.Keycard}
        @param remoteHost: the ip of the remote host
        @type  remoteHost: str

        @rtype: a deferred that will fire a
                L{flumotion.common.identity.RemoteIdentity}
        """
        raise NotImplementedError


class IdentityProviderExamplePlug(IdentityProviderPlug):
    """
    Example implementation of the IdentityProvider socket, randomly
    chooses an identity for the remote host.
    """

    def computeIdentity(self, keycard, remoteHost):
        i = RemoteIdentity(random.choice(['larry', 'curly', 'moe']),
                           random.choice(['chicago', 'detroit']))
        return defer.succeed(i)
