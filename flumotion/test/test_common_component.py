# -*- Mode: Python; test-case-name: flumotion.test.test_common_component -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# flumotion/test/test_common_component.py:
# test for flumotion.common.component
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

from twisted.trial import unittest
from twisted.spread import jelly
from twisted.internet import reactor

import common as mcommon

from flumotion.common import component, common
from flumotion.common.common import moods

class JobComponentStateTest(unittest.TestCase):
    def setUp(self):
        self.state = component.JobComponentState()

    def testGetSet(self):
        self.state.set('name', 'mynameis')
        self.failUnlessEqual(self.state.get('name'), 'mynameis')
        self.failUnlessEqual(self.state._dict['name'], 'mynameis')

    def testSetWrongArg(self):
        def assign(object):
            object.state.set('wrongarg', 'failure')
        
        self.assertRaises(KeyError, assign, self)
    
class AllComponentStateTest(unittest.TestCase):
    def setUp(self):
        self.jstate = component.JobComponentState()
        self.mstate = jelly.unjelly(jelly.jelly(self.jstate))
        self.astate = jelly.unjelly(jelly.jelly(self.mstate))

    def jset(self, key, value):
        # helper function to set on job state and propagate
        self.jstate.set(key, value)
        self.mstate = jelly.unjelly(jelly.jelly(self.jstate))
        self.astate = jelly.unjelly(jelly.jelly(self.mstate))

    def mset(self, key, value):
        # helper function to set on manager state and propagate
        self.mstate.set(key, value)
        self.astate = jelly.unjelly(jelly.jelly(self.mstate))

    def testClass(self):
        self.failUnless(isinstance(
            self.mstate, component.ManagerComponentState))
        self.failUnless(isinstance(
            self.jstate, component.JobComponentState))
        self.failUnless(isinstance(
            self.astate, component.AdminComponentState))

    def testMood(self):
        self.failIf(self.jstate.get('mood'))
        self.failIf(self.mstate.get('mood'))
        self.failIf(self.astate.get('mood'))

        self.jset('mood', moods.HAPPY)
        self.failUnlessEqual(self.jstate.get('mood'), moods.HAPPY)
        self.failUnlessEqual(self.mstate.get('mood'), moods.HAPPY)
        self.failUnlessEqual(self.astate.get('mood'), moods.HAPPY)

        self.mset('mood', moods.LOST)
        self.failUnlessEqual(self.jstate.get('mood'), moods.HAPPY)
        self.failUnlessEqual(self.mstate.get('mood'), moods.LOST)
        self.failUnlessEqual(self.astate.get('mood'), moods.LOST)

# FIXME: this test doesn't do anything since unjelly(jelly()) creates a
# new one, instead of updating the old one.  Find a way to make the old
# serialized object update first
class ListenerTest(unittest.TestCase):
    __implements__ = common.IStateListener

    def setUp(self):
        self.jstate = component.JobComponentState()
        self.mstate = jelly.unjelly(jelly.jelly(self.jstate))
        self.astate = jelly.unjelly(jelly.jelly(self.mstate))
        self.mstate.addListener(self)
        self.astate.addListener(self)
        self.changes = []

    def stateSet(self, state, key, value):
        # listener "interface" function
        print "state set !"
        self.changes.append((state, key, value))
        
    def jset(self, key, value):
        # helper function to set on job state and propagate
        self.jstate.set(key, value)
        self.mstate = jelly.unjelly(jelly.jelly(self.jstate))
        self.astate = jelly.unjelly(jelly.jelly(self.mstate))

    def mset(self, key, value):
        # helper function to set on manager state and propagate
        self.mstate.set(key, value)
        self.astate = jelly.unjelly(jelly.jelly(self.mstate))

    def testMood(self):
        self.failIf(self.jstate.get('mood'))
        self.failIf(self.mstate.get('mood'))
        self.failIf(self.astate.get('mood'))

        self.jset('mood', moods.HAPPY)
        self.failUnlessEqual(self.jstate.get('mood'), moods.HAPPY)
        self.failUnlessEqual(self.mstate.get('mood'), moods.HAPPY)
        self.failUnlessEqual(self.astate.get('mood'), moods.HAPPY)

        self.mset('mood', moods.LOST)
        self.failUnlessEqual(self.jstate.get('mood'), moods.HAPPY)
        self.failUnlessEqual(self.mstate.get('mood'), moods.LOST)
        self.failUnlessEqual(self.astate.get('mood'), moods.LOST)

if __name__ == '__main__':
    unittest.main()
