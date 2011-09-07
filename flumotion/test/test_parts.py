# -*- Mode: Python; test-case-name: flumotion.test.test_parts -*-
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

import gtk
from twisted.spread import jelly

from flumotion.admin.gtk.statusbar import AdminStatusbar
from flumotion.admin.gtk.componentlist import ComponentList
from flumotion.common import planet
from flumotion.common import testsuite
from flumotion.common.planet import moods


class TestAdminStatusbar(testsuite.TestCase):

    def setUp(self):
        self.window = gtk.Window()
        self.widget = gtk.Statusbar()
        # work around a bug in Statusbar that ends up doing a negative
        # w/h size request by setting a window size
        self.window.set_size_request(100, 100)
        self.window.add(self.widget)
        self.window.show_all()
        self.bar = AdminStatusbar(self.widget)

    def tearDown(self):
        # the iterations make sure the window goes away
        self.window.hide()
        gtk.main_iteration()
        self.window.destroy()
        gtk.main_iteration()

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

    def testClearAll(self):
        self.bar.push('main', 'I am the first message')
        self.bar.push('main', 'I am the second message')
        self.bar.clear(None)
        self.failIf(self.bar.pop('main'))


class TestComponentsView(testsuite.TestCase):

    def setUp(self):
        self.window = gtk.Window()
        self.widget = gtk.TreeView()
        self.window.add(self.widget)
        self.window.show_all()
        self.view = ComponentList(self.widget)
        gtk.main_iteration()

    def tearDown(self):
        # the iterations make sure the window goes away
        self.window.hide()
        gtk.main_iteration()
        self.window.destroy()
        gtk.main_iteration()

    def _createComponent(self, dict):
        mstate = planet.ManagerComponentState()
        for key in dict.keys():
            mstate.set(key, dict[key])
        astate = jelly.unjelly(jelly.jelly(mstate))
        return astate

    def testNoneSelected(self):
        self.failIf(self.view.getSelectedNames())

    def testNoComponents(self):
        # no components, so should be unable to start or stop any component
        self.failIf(self.view.get_property('can-stop-any'))
        self.failIf(self.view.get_property('can-start-any'))

    def testUpdate(self):
        components = {}
        c = self._createComponent(
            {'name': 'one', 'mood': moods.happy.value, 'pid': 1,
             'type': 'first'})
        components['one'] = c
        c = self._createComponent(
            {'name': 'two', 'mood': moods.sad.value, 'pid': 2,
             'type': 'second'})
        components['two'] = c
        self.view.clearAndRebuild(components)
        gtk.main_iteration()
        # no component is sleeping, so cannot start any
        self.failIf(self.view.get_property('can-start-any'))
        self.failUnless(self.view.get_property('can-stop-any'),
            "Should be able to stop component one")

    # builds on testUpdate

    def testOneSelected(self):

        def assertSelected(view, states, test):
            test.assertEqual(len(states), 1)
            name = states[0].get('name')
            test.assertEqual(name, 'one', 'name %s is not one' % name)
            test.asserted = True

        self.testUpdate()
        self.view.connect('selection-changed', assertSelected, self)
        self.asserted = False
        self.view._view.set_cursor('0')
        self.failUnless(self.asserted)

    def testMultipleSelected(self):

        def assertMultipleSelected(view, states, test):
            test.assertEqual(len(states), 2)
            name = states[0].get('name')
            test.assertEqual(name, 'one', 'name %s is not one' % name)
            name = states[1].get('name')
            test.assertEqual(name, 'two', 'name %s is not one' % name)
            test.asserted = True

        self.testUpdate()
        self.view.connect('selection-changed', assertMultipleSelected, self)
        self.asserted = False
        self.view._view.get_selection().select_all()
        self.failUnless(self.asserted)

    def testCanStartOneWhenSleeping(self):

        def assertCanStart(view, states, test):
            test.failIf(not view.canStart())
            test.asserted = True

        components = {}
        c = self._createComponent(
            {'name': 'one', 'mood': moods.sleeping.value, 'pid': 1,
             'type': 'foo', 'workerRequested': 'worker1'})
        components['one'] = c
        self.view.clearAndRebuild(components)
        self.view.workerAppend('worker1')

        gtk.main_iteration()
        self.view.connect('selection-changed', assertCanStart, self)
        self.asserted = False
        self.view._view.set_cursor('0')
        self.failUnless(self.asserted)

    def testCanNotStartOneWhenHappy(self):

        def assertCanStart(view, states, test):
            test.failIf(view.canStart())
            test.asserted = True

        components = {}
        c = self._createComponent(
            {'name': 'one', 'mood': moods.happy.value, 'pid': 1,
             'type': 'foo'})
        components['one'] = c
        self.view.clearAndRebuild(components)
        gtk.main_iteration()
        self.view.connect('selection-changed', assertCanStart, self)
        self.asserted = False
        self.view._view.set_cursor('0')
        self.failUnless(self.asserted)

    def testCanNotStartOneWhenSad(self):

        def assertCanStart(view, states, test):
            test.failIf(view.canStart())
            test.asserted = True

        components = {}
        c = self._createComponent(
            {'name': 'one', 'mood': moods.sad.value, 'pid': 1,
             'type': 'foo'})
        components['one'] = c
        self.view.clearAndRebuild(components)
        gtk.main_iteration()
        self.view.connect('selection-changed', assertCanStart, self)
        self.asserted = False
        self.view._view.set_cursor('0')
        self.failUnless(self.asserted)

    def testCanNotStartOneWhenHungry(self):

        def assertCanStart(view, states, test):
            test.failIf(view.canStart())
            test.asserted = True

        components = {}
        c = self._createComponent(
            {'name': 'one', 'mood': moods.hungry.value, 'pid': 1,
             'type': 'foo'})
        components['one'] = c
        self.view.clearAndRebuild(components)
        gtk.main_iteration()
        self.view.connect('selection-changed', assertCanStart, self)
        self.asserted = False
        self.view._view.set_cursor('0')
        self.failUnless(self.asserted)

    def testCanNotStartOneWhenWaking(self):

        def assertCanStart(view, states, test):
            test.failIf(view.canStart())
            test.asserted = True

        components = {}
        c = self._createComponent(
            {'name': 'one', 'mood': moods.waking.value, 'pid': 1,
             'type': 'foo'})
        components['one'] = c
        self.view.clearAndRebuild(components)
        gtk.main_iteration()
        self.view.connect('selection-changed', assertCanStart, self)
        self.asserted = False
        self.view._view.set_cursor('0')
        self.failUnless(self.asserted)

    def testCanNotStartOneWhenLost(self):

        def assertCanStart(view, states, test):
            test.failIf(view.canStart())
            test.asserted = True

        components = {}
        c = self._createComponent(
            {'name': 'one', 'mood': moods.lost.value, 'pid': 1,
             'type': 'foo'})
        components['one'] = c
        self.view.clearAndRebuild(components)
        gtk.main_iteration()
        self.view.connect('selection-changed', assertCanStart, self)
        self.asserted = False
        self.view._view.set_cursor('0')
        self.failUnless(self.asserted)

    def testCanNotStartWhenNoSelection(self):

        def assertCanStart(view, states, test):
            test.failIf(view.canStart())
            test.asserted = True
        components = {}
        c = self._createComponent(
            {'name': 'one', 'mood': moods.sleeping.value, 'pid': 1,
             'type': 'foo'})
        components['one'] = c
        self.view.clearAndRebuild(components)
        gtk.main_iteration()
        self.view._view.get_selection().select_all()
        self.view.connect('selection-changed', assertCanStart, self)
        self.asserted = False
        self.view._view.get_selection().unselect_all()
        # Using idles, this is not possibly any longer
        #self.failUnless(self.asserted)

    def testCanStartMultipleWhenSleeping(self):

        def assertCanStart(view, states, test):
            test.failIf(not view.canStart())
            test.asserted = True

        components = {}
        c = self._createComponent(
            {'name': 'one', 'mood': moods.sleeping.value, 'pid': 1,
             'type': 'foo', 'workerRequested': 'worker1'})
        components['one'] = c
        c = self._createComponent(
            {'name': 'two', 'mood': moods.sleeping.value, 'pid': 2,
             'type': 'foo', 'workerRequested': 'worker1'})
        components['two'] = c
        self.view.clearAndRebuild(components)
        self.view.workerAppend('worker1')
        gtk.main_iteration()
        self.view.connect('selection-changed', assertCanStart, self)
        self.asserted = False
        self.view._view.get_selection().select_all()
        self.failUnless(self.asserted)

    def testCanNotStartMultipleWhenOneIsSad(self):

        def assertCanStart(view, states, test):
            test.failIf(view.canStart())
            test.asserted = True

        components = {}
        c = self._createComponent(
            {'name': 'one', 'mood': moods.sleeping.value, 'pid': 1,
             'type': 'foo'})
        components['one'] = c
        c = self._createComponent(
            {'name': 'two', 'mood': moods.sad.value, 'pid': 2,
             'type': 'foo'})
        components['two'] = c
        self.view.clearAndRebuild(components)
        gtk.main_iteration()
        self.view.connect('selection-changed', assertCanStart, self)
        self.asserted = False
        self.view._view.get_selection().select_all()
        self.failUnless(self.asserted)

    def testCanNotStartMultipleWhenOneIsHappy(self):

        def assertCanStart(view, states, test):
            test.failIf(view.canStart())
            test.asserted = True

        components = {}
        c = self._createComponent(
            {'name': 'one', 'mood': moods.sleeping.value, 'pid': 1,
             'type': 'foo'})
        components['one'] = c
        c = self._createComponent(
            {'name': 'two', 'mood': moods.happy.value, 'pid': 2,
             'type': 'foo'})
        components['two'] = c
        self.view.clearAndRebuild(components)
        gtk.main_iteration()
        self.view.connect('selection-changed', assertCanStart, self)
        self.asserted = False
        self.view._view.get_selection().select_all()
        self.failUnless(self.asserted)

    def testCanNotStartMultipleWhenOneIsHungry(self):

        def assertCanStart(view, states, test):
            test.failIf(view.canStart())
            test.asserted = True

        components = {}
        c = self._createComponent(
            {'name': 'one', 'mood': moods.sleeping.value, 'pid': 1,
             'type': 'foo'})
        components['one'] = c
        c = self._createComponent(
            {'name': 'two', 'mood': moods.hungry.value, 'pid': 2,
             'type': 'foo'})
        components['two'] = c
        self.view.clearAndRebuild(components)
        gtk.main_iteration()
        self.view.connect('selection-changed', assertCanStart, self)
        self.asserted = False
        self.view._view.get_selection().select_all()
        self.failUnless(self.asserted)

    def testCanNotStartMultipleWhenOneIsWaking(self):

        def assertCanStart(view, states, test):
            test.failIf(view.canStart())
            test.asserted = True

        components = {}
        c = self._createComponent(
            {'name': 'one', 'mood': moods.sleeping.value, 'pid': 1,
             'type': 'foo'})
        components['one'] = c
        c = self._createComponent(
            {'name': 'two', 'mood': moods.waking.value, 'pid': 2,
             'type': 'foo'})
        components['two'] = c
        self.view.clearAndRebuild(components)
        gtk.main_iteration()
        self.view.connect('selection-changed', assertCanStart, self)
        self.asserted = False
        self.view._view.get_selection().select_all()
        self.failUnless(self.asserted)

    def testCanNotStartMultipleWhenOneIsLost(self):

        def assertCanStart(view, states, test):
            test.failIf(view.canStart())
            test.asserted = True

        components = {}
        c = self._createComponent(
            {'name': 'one', 'mood': moods.sleeping.value, 'pid': 1,
             'type': 'foo'})
        components['one'] = c
        c = self._createComponent(
            {'name': 'two', 'mood': moods.lost.value, 'pid': 2,
             'type': 'foo'})
        components['two'] = c
        self.view.clearAndRebuild(components)
        gtk.main_iteration()
        self.view.connect('selection-changed', assertCanStart, self)
        self.asserted = False
        self.view._view.get_selection().select_all()
        self.failUnless(self.asserted)

    def testCanNotStartMultipleWhenWorkerIsNotLogged(self):

        def assertCanStart(view, states, test):
            test.failIf(view.canStart())
            test.asserted = True

        components = {}
        c = self._createComponent(
            {'name': 'one', 'mood': moods.sleeping.value, 'pid': 1,
             'type': 'foo', 'workerRequested': 'worker1'})
        components['one'] = c
        c = self._createComponent(
            {'name': 'two', 'mood': moods.sad.value, 'pid': 2,
             'type': 'foo', 'workerRequested': 'worker2'})
        components['two'] = c
        self.view.clearAndRebuild(components)
        self.view.workerAppend('worker1')
        gtk.main_iteration()
        self.view.connect('selection-changed', assertCanStart, self)
        self.asserted = False
        self.view._view.get_selection().select_all()
        self.failUnless(self.asserted)

    def testCanStopOneWhenHappy(self):

        def assertCanStop(view, states, test):
            test.failIf(not view.canStop())
            test.asserted = True

        components = {}
        c = self._createComponent(
            {'name': 'one', 'mood': moods.happy.value, 'pid': 1,
             'type': 'foo'})
        components['one'] = c
        self.view.clearAndRebuild(components)
        gtk.main_iteration()
        self.view.connect('selection-changed', assertCanStop, self)
        self.asserted = False
        self.view._view.set_cursor('0')
        self.failUnless(self.asserted)

    def testCanStopOneWhenHungry(self):

        def assertCanStop(view, states, test):
            test.failIf(not view.canStop())
            test.asserted = True

        components = {}
        c = self._createComponent(
            {'name': 'one', 'mood': moods.hungry.value, 'pid': 1,
             'type': 'foo'})
        components['one'] = c
        self.view.clearAndRebuild(components)
        gtk.main_iteration()
        self.view.connect('selection-changed', assertCanStop, self)
        self.asserted = False
        self.view._view.set_cursor('0')
        self.failUnless(self.asserted)

    def testCanStopOneWhenSad(self):

        def assertCanStop(view, states, test):
            test.failIf(not view.canStop())
            test.asserted = True

        components = {}
        c = self._createComponent(
            {'name': 'one', 'mood': moods.sad.value, 'pid': 1,
             'type': 'foo'})
        components['one'] = c
        self.view.clearAndRebuild(components)
        gtk.main_iteration()
        self.view.connect('selection-changed', assertCanStop, self)
        self.asserted = False
        self.view._view.set_cursor('0')
        self.failUnless(self.asserted)

    def testCanStopOneWhenWaking(self):

        def assertCanStop(view, states, test):
            test.failIf(not view.canStop())
            test.asserted = True

        components = {}
        c = self._createComponent(
            {'name': 'one', 'mood': moods.waking.value, 'pid': 1,
             'type': 'foo'})
        components['one'] = c
        self.view.clearAndRebuild(components)
        gtk.main_iteration()
        self.view.connect('selection-changed', assertCanStop, self)
        self.asserted = False
        self.view._view.set_cursor('0')
        self.failUnless(self.asserted)

    def testCanStopOneWhenLost(self):

        def assertCanStop(view, states, test):
            test.failIf(not view.canStop())
            test.asserted = True

        components = {}
        c = self._createComponent(
            {'name': 'one', 'mood': moods.lost.value, 'pid': 1,
             'type': 'foo'})
        components['one'] = c
        self.view.clearAndRebuild(components)
        gtk.main_iteration()
        self.view.connect('selection-changed', assertCanStop, self)
        self.asserted = False
        self.view._view.set_cursor('0')
        self.failUnless(self.asserted)

    def testCanNotStopOneWhenSleeping(self):

        def assertCanStop(view, states, test):
            test.failIf(view.canStop())
            test.asserted = True

        components = {}
        c = self._createComponent(
            {'name': 'one', 'mood': moods.sad.sleeping.value, 'pid': 1,
             'type': 'foo'})
        components['one'] = c
        self.view.clearAndRebuild(components)
        gtk.main_iteration()
        self.view.connect('selection-changed', assertCanStop, self)
        self.asserted = False
        self.view._view.set_cursor('0')
        self.failUnless(self.asserted)

    def testCanNotStopWhenNoSelection(self):

        def assertCanStop(view, states, test):
            test.failIf(view.canStop())
            test.asserted = True

        components = {}
        c = self._createComponent(
            {'name': 'one', 'mood': moods.happy.value, 'pid': 1,
             'type': 'foo'})
        components['one'] = c
        self.view.clearAndRebuild(components)
        gtk.main_iteration()
        self.view._view.get_selection().select_all()
        self.view.connect('selection-changed', assertCanStop, self)
        self.asserted = False
        self.view._view.get_selection().unselect_all()
        # Using idles, this is not possibly any longer
        #self.failUnless(self.asserted)

    def testCanNotStopMultipleWhenOneIsSleeping(self):

        def assertCanStop(view, states, test):
            test.failIf(view.canStop())
            test.asserted = True

        components = {}
        c = self._createComponent(
            {'name': 'one', 'mood': moods.sleeping.value, 'pid': 1,
             'type': 'foo'})
        components['one'] = c
        c = self._createComponent(
            {'name': 'two', 'mood': moods.sad.value, 'pid': 2,
             'type': 'foo'})
        components['two'] = c
        self.view.clearAndRebuild(components)
        gtk.main_iteration()
        self.view.connect('selection-changed', assertCanStop, self)
        self.asserted = False
        self.view._view.get_selection().select_all()
        self.failUnless(self.asserted)

    def testCanStopMultipleWhenOneNoneIsSleeping(self):

        def assertCanStop(view, states, test):
            test.failIf(not view.canStop())
            test.asserted = True

        components = {}
        c = self._createComponent(
            {'name': 'one', 'mood': moods.happy.value, 'pid': 1,
             'type': 'foo'})
        components['one'] = c
        c = self._createComponent(
            {'name': 'two', 'mood': moods.sad.value, 'pid': 2,
             'type': 'foo'})
        components['two'] = c
        c = self._createComponent(
            {'name': 'three', 'mood': moods.hungry.value, 'pid': 3,
             'type': 'foo'})
        components['three'] = c
        c = self._createComponent(
            {'name': 'four', 'mood': moods.waking.value, 'pid': 4,
             'type': 'foo'})
        components['four'] = c
        c = self._createComponent(
            {'name': 'two', 'mood': moods.lost.value, 'pid': 5,
             'type': 'foo'})
        components['two'] = c
        self.view.clearAndRebuild(components)
        gtk.main_iteration()
        self.view.connect('selection-changed', assertCanStop, self)
        self.asserted = False
        self.view._view.get_selection().select_all()
        self.failUnless(self.asserted)
