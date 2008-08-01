# -*- Mode: Python -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# Flumotion - a streaming media server
# Copyright (C) 2004,2005,2006,2007 Fluendo, S.L. (www.fluendo.com).
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

from twisted.internet import reactor

# importing "gtk" before reactor blows up with a TypeError in T1.3.0
import gobject
import gtk

from twisted.spread import jelly
from flumotion.admin.gtk import parts
from flumotion.common import planet
from flumotion.common.planet import moods


class TestComponentsView:

    def setUp(self):
        self.window = gtk.Window()
        self.widget = gtk.TreeView()
        self.window.add(self.widget)
        self.window.show_all()
        self.view = parts.ComponentsView(self.widget)
        self.view.connect('selection-changed', self._selection_changed_cb)
        self.view.connect('activated', self._activated_cb)
        self.window.connect('destroy', gtk.main_quit)

    def _createComponent(self, dict):
        mstate = planet.ManagerComponentState()
        for key in dict.keys():
            mstate.set(key, dict[key])
        astate = jelly.unjelly(jelly.jelly(mstate))
        return astate

    def tearDown(self):
        self.window.destroy()

    def update(self):
        components = {}
        c = self._createComponent(
            {'name': 'one', 'mood': moods.happy.value,
             'workerName': 'R2D2', 'pid': 1})
        components['one'] = c
        c = self._createComponent(
            {'name': 'two', 'mood': moods.sad.value,
             'workerName': 'R2D2', 'pid': 2})
        components['two'] = c
        c = self._createComponent(
            {'name': 'three', 'mood': moods.hungry.value,
             'workerName': 'C3PO', 'pid': 3})
        components['three'] = c
        c = self._createComponent(
            {'name': 'four', 'mood': moods.sleeping.value,
             'workerName': 'C3PO', 'pid': None})
        components['four'] = c
        self.view.update(components)

    def _selection_changed_cb(self, view, state):
        name = state.get('name')
        print "Selected component %s" % name

    def _activated_cb(self, view, state, action_name):
        name = state.get('name')
        print "Do action %s on component %s" % (action_name, name)


app = TestComponentsView()
app.setUp()
app.update()

gtk.main()
