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


import gobject
import gtk

from flumotion.twisted.defer import defer_generator_method
from flumotion.common import planet, errors, common, log


class NodeBook(gtk.Notebook):
    def __init__(self, admingtk):
        gtk.Notebook.__init__(self)
        self.admingtk = admingtk
        admingtk.setup()
        self.nodes = admingtk.getNodes()
        self._setup_pages()
        self.show_all()
        
    def _setup_pages(self):
        for name, node in self.nodes.items():
            table = gtk.Table(1,1)
            table.add(gtk.Label('Loading UI for %s...' % name))
            self.append_page(table, gtk.Label(name))

            def got_widget(w, name, table, node):
                # dumb dumb dumb dumb
                if w.get_parent():
                    w.get_parent().remove(w)
                map(table.remove, table.get_children())
                table.add(w)
                w.show()
            node.render().addCallback(got_widget, name, table, node)

NUM_STATES = 3
OBJECT_UNSET, OBJECT_INACTIVE, OBJECT_ACTIVE = range(NUM_STATES)

class ComponentView(gtk.VBox, log.Loggable):
    def __init__(self):
        gtk.VBox.__init__(self)
        self.widget_constructor = None
        self.widget = None
        self.object = None
        self._state = OBJECT_UNSET
        self._callStamp = 0
        self.set_single_admin(None)

    def set_single_admin(self, admin):
        self.admin = admin

    def get_admin_for_object(self, object):
        # override me to do e.g. multi.get_admin_for_object
        return self.admin

    @defer_generator_method
    def get_widget_constructor(self, state):
        def sleeping_component():
            return gtk.Label('Component %s is still sleeping' %
                             state.get('name'))
        def not_component_state():
            return gtk.Label('')
            
        admin = self.get_admin_for_object(state)
        if not isinstance(state, planet.AdminComponentState):
            yield not_component_state

        try:
            d = admin.callRemote('getEntryByType', state, 'admin/gtk')
            yield d
            filename, procname = d.value()
        except errors.NoBundleError, e:
            # Use a default of BaseAdminGtk so our plumbing nodes work
            filename = "flumotion/component/base/admin_gtk.py"
            procname  = "BaseAdminGtk"
        except errors.SleepingComponentError, e:
            yield sleeping_component
        
        modname = common.pathToModuleName(filename)
        d = admin.getBundledFunction(modname, procname)
        yield d
        proc = d.value()
        yield lambda: NodeBook(proc(state, admin))

    def object_unset_to_inactive(self):
        def invalidate(_):
            self._set_state(OBJECT_UNSET)
        def set(state, key, value):
            if key == 'mood':
                if (value != planet.moods.lost.value
                    and value != planet.moods.sleeping.value):
                    self._set_state(OBJECT_ACTIVE)
                else:
                    self._set_state(OBJECT_INACTIVE)

        assert self.object is not None
        self.object.addListener(self, invalidate=invalidate,
                                set=set)
        if self.object.hasKey('mood'):
            set(self.object, 'mood', self.object.get('mood'))

    def object_inactive_to_active(self):
        def got_widget_constructor(proc, callStamp):
            if (callStamp != self._callStamp
                or self._state != OBJECT_ACTIVE):
                # in the time that get_widget_constructor was running,
                # perhaps the user selected another object; only update
                # the ui if that did not happen
                self.debug('ignoring widget constructor %r, state %d, '
                           'callstamps %d/%d', proc, self._state,
                           callStamp, self._callStamp)
                return
            self.widget = proc()
            self.widget.show()
            self.pack_start(self.widget, True, True)
            return self.widget
            
        self._callStamp += 1
        callStamp = self._callStamp
        d = self.get_widget_constructor(self.object)
        d.addCallback(got_widget_constructor, callStamp)
        
    def object_active_to_inactive(self):
        self.remove(self.widget)
        self.widget = None
        
    def object_inactive_to_unset(self):
        self.object.removeListener(self)
        self.object = None

    def _set_state(self, state):
        uptable = [self.object_unset_to_inactive,
                   self.object_inactive_to_active]
        downtable = [self.object_inactive_to_unset,
                     self.object_active_to_inactive]
        if self._state < state:
            while self._state < state:
                self.log('object %r state change: %d++', self.object,
                         self._state)
                self._state += 1
                uptable[self._state - 1]()
        else:
            while self._state > state:
                self.log('object %r state change: %d--', self.object,
                         self._state)
                self._state -= 1
                downtable[self._state]()

    def show_object(self, state):
        self._set_state(OBJECT_UNSET)
        if state:
            self.object = state
            self._set_state(OBJECT_INACTIVE)

gobject.type_register(ComponentView)
