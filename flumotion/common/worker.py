# -*- Mode: Python; test-case-name: flumotion.test.test_common_worker -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# flumotion/common/worker.py: worker state shared between manager and
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

# worker heaven state proxy objects
class ManagerWorkerHeavenState(flavors.StateCacheable):
    def __init__(self):
        flavors.StateCacheable.__init__(self)
        # FIXME: later on we would want a dict of names -> cacheables ?
        self.addKey('names', [])

    def __repr__(self):
        return "%r" % self._dict

class AdminWorkerHeavenState(flavors.StateRemoteCache):
    pass

pb.setUnjellyableForClass(ManagerWorkerHeavenState, AdminWorkerHeavenState)
