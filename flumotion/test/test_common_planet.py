# -*- Mode: Python; test-case-name: flumotion.test.test_common_planet -*-
# vi:si:et:sw=4:sts=4:ts=4

# Flumotion - a streaming media server
# Copyright (C) 2004,2005,2006,2007,2008,2009 Fluendo, S.L.
# Copyright (C) 2010,2011 Flumotion Services, S.A.
# All rights reserved.
#
# This file may be distributed and/or modified under the terms of
# the GNU Lesser General Public License version 2.1 as published by
# the Free Software Foundation.
# This file is distributed without any warranty; without even the implied
# warranty of merchantability or fitness for a particular purpose.
# See "LICENSE.LGPL" in the source distribution for more information.
#
# Headers in this file shall remain intact.

from twisted.trial import unittest
from twisted.spread import jelly
from zope.interface import implements

from flumotion.common import testsuite
from flumotion.common import planet
from flumotion.common.planet import moods
from flumotion.twisted import flavors


class ManagerComponentStateTest(testsuite.TestCase):

    def setUp(self):
        self.state = planet.ManagerComponentState()

    def testGetSet(self):
        self.state.set('name', 'mynameis')
        self.failUnlessEqual(self.state.get('name'), 'mynameis')
        self.failUnlessEqual(self.state._dict['name'], 'mynameis')

    def testSetWrongArg(self):

        def assign(object):
            object.state.set('wrongarg', 'failure')

        self.assertRaises(KeyError, assign, self)


class AllComponentStateTest(testsuite.TestCase):

    def setUp(self):
        self.mstate = planet.ManagerComponentState()
        self.astate = jelly.unjelly(jelly.jelly(self.mstate))
        self.failUnless(isinstance(self.astate, planet.AdminComponentState))

    def mset(self, key, value):
        # helper function to set on manager state and propagate
        self.mstate.set(key, value)
        self.astate = jelly.unjelly(jelly.jelly(self.mstate))

    def testClass(self):
        self.failUnless(isinstance(
            self.mstate, planet.ManagerComponentState))
        self.failUnless(isinstance(
            self.astate, planet.AdminComponentState))

    def testMood(self):
        self.failIf(self.mstate.get('mood'))
        self.failIf(self.astate.get('mood'))

        self.mset('mood', moods.lost.value)
        self.failUnlessEqual(self.mstate.get('mood'), moods.lost.value)
        self.failUnlessEqual(self.astate.get('mood'), moods.lost.value)


class InvalidateTest(testsuite.TestCase):

    def testInvalidate(self):
        mcomp = planet.ManagerComponentState()
        mflow = planet.ManagerFlowState()
        mstate = planet.ManagerPlanetState()

        mflow.append('components', mcomp)
        mstate.append('flows', mflow)

        astate = jelly.unjelly(jelly.jelly(mstate))
        self.failUnless(isinstance(astate, planet.AdminPlanetState))

        aflow, = astate.get('flows')
        acomp, = aflow.get('components')

        invalidates = []

        def invalidate(obj):
            invalidates.append(obj)

        astate.addListener(self, invalidate=invalidate)
        aflow.addListener(self, invalidate=invalidate)
        acomp.addListener(self, invalidate=invalidate)

        self.assertEquals(invalidates, [])
        astate.invalidate()
        self.assertEquals(invalidates, [acomp, aflow, astate])

# FIXME: this test doesn't do anything since unjelly(jelly()) creates a
# new one, instead of updating the old one.  Find a way to make the old
# serialized object update first


class ListenerTest(testsuite.TestCase):
    implements(flavors.IStateListener)

    def setUp(self):
        self.mstate = planet.ManagerComponentState()
        self.astate = jelly.unjelly(jelly.jelly(self.mstate))
        self.astate.addListener(self, set_=self.stateSet)
        self.changes = []

    def stateSet(self, state, key, value):
        # listener "interface" function
        print "state set !"
        self.changes.append((state, key, value))

    def mset(self, key, value):
        # helper function to set on job state and propagate
        self.mstate.set(key, value)
        self.astate = jelly.unjelly(jelly.jelly(self.mstate))

    def mset(self, key, value):
        # helper function to set on manager state and propagate
        self.mstate.set(key, value)
        self.astate = jelly.unjelly(jelly.jelly(self.mstate))

    def testMood(self):
        self.failIf(self.mstate.get('mood'))
        self.failIf(self.astate.get('mood'))

        self.mset('mood', moods.lost.value)
        self.failUnlessEqual(self.mstate.get('mood'), moods.lost.value)
        self.failUnlessEqual(self.astate.get('mood'), moods.lost.value)

if __name__ == '__main__':
    unittest.main()
