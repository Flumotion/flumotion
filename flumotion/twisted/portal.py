# -*- Mode: Python -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# flumotion/twisted/portal.py: portal stuff; see twisted.cred.portal
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

from twisted.spread import flavors
from twisted.cred.portal import Portal
from twisted.python.components import registerAdapter

from flumotion.twisted.pb import _PortalRoot

# we create a dummy subclass because there is already an adapter registered
# for Portal in twisted.spread.pb
class FlumotionPortal(Portal):
    pass

registerAdapter(_PortalRoot, FlumotionPortal, flavors.IPBRoot)
