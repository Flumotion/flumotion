# -*- Mode: Python; -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# Flumotion - a streaming media server
# Copyright (C) 2004,2005 Fluendo, S.L. (www.fluendo.com). All rights reserved.

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

from twisted.spread import pb
from flumotion.twisted import flavors

class ManagerPlanetState(flavors.StateCacheable):
    def __init__(self):
        flavors.StateCacheable.__init__(self)
        self.addKey('name')
        self.addKey('manager')
        self.addKey('atmosphere')
        self.addListKey('flows')

class AdminPlanetState(flavors.StateRemoteCache):
    pass

pb.setUnjellyableForClass(ManagerPlanetState, AdminPlanetState)

class ManagerAtmosphereState(flavors.StateCacheable):
    def __init__(self):
        flavors.StateCacheable.__init__(self)
        self.addListKey('components')

class AdminAtmosphereState(flavors.StateRemoteCache):
    pass

pb.setUnjellyableForClass(ManagerAtmosphereState, AdminAtmosphereState)

class ManagerFlowState(flavors.StateCacheable):
    def __init__(self):
        flavors.StateCacheable.__init__(self)
        self.addKey('name')
        self.addListKey('components')

class AdminFlowState(flavors.StateRemoteCache):
    pass

pb.setUnjellyableForClass(ManagerFlowState, AdminFlowState)


