# -*- Mode: Python; test-case-name: flumotion.test.test_common_component -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# flumotion/common/component.py: component state shared between manager and
# admin
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

# Headers in this file shall remain intact.


from twisted.spread import pb

from flumotion.twisted import flavors
from flumotion.common import enum

# moods
moods = enum.EnumClass(
    'Moods',
    ('happy', 'sad', 'lost', 'hungry', 'waking', 'sleeping')
)

# component state proxy objects
class JobComponentState(flavors.StateCacheable):
    def __init__(self):
        flavors.StateCacheable.__init__(self)
        self.addKey('name')
        self.addKey('mood')
        self.addKey('pid')
        self.addKey('workerName')
        self.addKey('ip')

    def __repr__(self):
        return "%r" % self._dict

    def setName(self, name):
        self.set('name', name)

    def setMood(self, mood):
        self.set('mood', mood)

class ManagerComponentState(flavors.StateCacheable, flavors.StateRemoteCache):
    #def __init__(self):
    #    flavors.StateCacheable.__init__(self)
    #    flavors.StateRemoteCache.__init__(self)

    def __repr__(self):
        return "%r" % self._dict

class AdminComponentState(flavors.StateRemoteCache):
    pass

pb.setUnjellyableForClass(JobComponentState, ManagerComponentState)
pb.setUnjellyableForClass(ManagerComponentState, AdminComponentState)
