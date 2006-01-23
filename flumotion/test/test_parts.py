# -*- Mode: Python; test-case-name: flumotion.test.test_parts -*-
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

from twisted.trial import unittest

import common

import gobject
import gtk

from twisted.spread import jelly
from flumotion.admin.gtk import parts
from flumotion.common import planet

from flumotion.common.planet import moods

class TestAdminStatusbar(unittest.TestCase):
    def setUp(self):
        self.window = gtk.Window()
        self.widget = gtk.Statusbar()
        # work around a bug in Statusbar that ends up doing a negative
        # w/h size request by setting a window size
        self.window.set_size_request(100, 100)
        self.window.add(self.widget)
        self.window.show_all()
        self.bar = parts.AdminStatusbar(self.widget)

    def tearDown(self):
        self.window.destroy()

    def testPushRemove(self):
        mid = self.bar.push('main', 'I am a message')
        self.failUnless(self.bar.remove('main', mid))
        self.failIf(self.bar.remove('main', mid))

        # non-existing context
        self.assertRaises(KeyError, self.bar.remove, 'idontexist', 0)
        # non-existing mid
        self.bar.remove('main', 0)

    def testPushPop(self):
        mid = self.bar.push('main', 'I am a message')
        self.failUnlessEqual(self.bar.pop('main'), mid)
        self.failIf(self.bar.pop('main'))

    def testSet(self):
        mid = self.bar.push('main', 'I am a message')
        mid2 = self.bar.set('main', 'I am another message')
        self.failUnless(mid2)
        self.failIfEqual(mid, mid2)

    def testTwoContexts(self):
        mid1 = self.bar.push('main', 'I am a message')
        mid2 = self.bar.push('notebook', 'I am a notebook message')
        self.failUnless(mid2)
        self.failIfEqual(mid1, mid2)
        self.failUnlessEqual(self.bar.pop('main'), mid1)
        self.failUnlessEqual(self.bar.pop('notebook'), mid2)

    def testClear(self):
        self.bar.push('main', 'I am a message')
        self.bar.push('notebook', 'I am a notebook message')
        self.bar.push('notebook', 'I am a second notebook message')
        self.bar.clear('main')
        self.failIf(self.bar.pop('main'))
        self.failUnless(self.bar.pop('notebook'))
        self.bar.clear()
        self.failIf(self.bar.pop('main'))
        self.failIf(self.bar.pop('notebook'))

class TestComponentsView(unittest.TestCase):
    def setUp(self):
        self.window = gtk.Window()
        self.widget = gtk.TreeView()
        self.window.add(self.widget)
        self.window.show_all()
        self.view = parts.ComponentsView(self.widget)
        gtk.main_iteration()

    def _createComponent(self, dict):
        mstate = planet.ManagerComponentState()
        for key in dict.keys():
            mstate.set(key, dict[key]) 
        astate = jelly.unjelly(jelly.jelly(mstate))
        return astate

    def tearDown(self):
        self.window.destroy()

    def testNoneSelected(self):
        self.failIf(self.view.get_selected_name())

    def testUpdate(self):
        components = {}
        c = self._createComponent(
            {'name': 'one', 'mood': moods.happy.value, 'pid': 1})
        components['one'] = c
        c = self._createComponent(
            {'name': 'two', 'mood': moods.sad.value, 'pid': 2})
        components['two'] = c
        self.view.update(components)
        gtk.main_iteration()

    def testSelected(self):
        def assertSelected(view, state, test):
            name = state.get('name')
            test.assertEqual(name, 'one', 'name %s is not one' % name)
            test.asserted = True
            
        self.testUpdate()
        self.view.connect('has-selection', assertSelected, self)
        self.asserted = False
        self.view._view.set_cursor('0')
        self.failUnless(self.asserted)
