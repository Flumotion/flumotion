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
from twisted.internet import defer

from flumotion.twisted import flavors
from flumotion.common import enum

# state of a component used for UI purposes
class WorkerComponentUIState(flavors.StateCacheable):
    pass
    #def append(self, key, value):
    #    print "THOMAS: %r.append(%s, %r)" % (self, key, value)
    #    flavors.StateCacheable.append(self, key, value)

class ManagerComponentUIState(flavors.StateCacheable, flavors.StateRemoteCache):
    pass
    #def __init__(self):
    #    print "THOMAS: Manager __init__"
    #    flavors.StateRemoteCache.__init__(self)
    #    flavors.StateCacheable.__init__(self)
        #self.addListener(self)
        #self._ensureListeners()
        #self._listeners.append(self) # this is the line that makes stuff work;
        # why ?
        # create circular reference so we don't go away
    #    self._self = self

    #def observe_append(self, key, value):
    #    print "THOMAS: observe_append on  self %r, key %s" % (self, key)
    #    flavors.StateRemoteCache.observe_append(self, key, value)

class AdminComponentUIState(flavors.StateRemoteCache):
    pass
    #__implements__ = flavors.IStateListener,

    #def __init__(self):
    #    print "THOMAS: __init__"
    #    flavors.StateRemoteCache.__init__(self)
        #self.addListener(self)
    #    self._ensureListeners()
        #self._listeners.append(self) # this is the line that makes stuff work;
        # why ?

#    def observe_append(self, key, value):
#        print "THOMAS: observe_append on  self %r, key %s" % (self, key)
#        flavors.StateRemoteCache.observe_append(self, key, value)

#    def observe_remove(self, key, value):
#        print "THOMAS: observe_remove on  self %r, key %s" % (self, key)
#        flavors.StateRemoteCache.observe_remove(self, key, value)


    #def stateAppend(self, object, key, value):
    #    pass
        #print "THOMAS: appending key %r" % key

pb.setUnjellyableForClass(WorkerComponentUIState, ManagerComponentUIState)
pb.setUnjellyableForClass(ManagerComponentUIState, AdminComponentUIState)
