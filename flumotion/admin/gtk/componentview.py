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

__version__ = "$Rev$"


import gobject
import gtk

from flumotion.common import planet, errors, common, log


class NodeBook(gtk.Notebook):
    def __init__(self, admingtk):
        """
        @param admingtk: the GTK Admin with its nodes
        @type  admingtk: L{flumotion.component.base.admin_gtk.BaseAdminGtk}

        """
        gtk.Notebook.__init__(self)
        self.admingtk = admingtk
        admingtk.setup()
        self.nodes = admingtk.getNodes()
        self._setup_pages()
        self.show()

    def _setup_pages(self):
        def render(widget, table):
            # dumb dumb dumb dumb
            old_parent = widget.get_parent()
            if old_parent:
                old_parent.remove(widget)
            map(table.remove, table.get_children())
            table.add(widget)
            widget.show()

        for name, node in self.nodes.items():
            table = gtk.Table(1,1)
            table.show()
            table.add(gtk.Label('Loading UI for %s...' % name))
            label = self._get_title_label(node, name)
            label.show()
            self.append_page(table, label)

            d = node.render()
            d.addCallback(render, table)

    def _get_title_label(self, node, name):
        title = node.title
        if not title:
            # FIXME: we have no way of showing an error message ?
            # This should be added so users can file bugs.
            self.warning("Component node %s does not have a "
                "translateable title. Please file a bug." % name)

            # fall back for now
            title = name

        return gtk.Label(title)


(OBJECT_UNSET,
 OBJECT_INACTIVE,
 OBJECT_ACTIVE) = range(3)

class ComponentView(gtk.VBox, log.Loggable):
    logCategory = 'componentview'

    def __init__(self):
        gtk.VBox.__init__(self)
        self.widget_constructor = None
        self._widget = None
        self._object_state = None
        self._state = OBJECT_UNSET
        self._callStamp = 0
        self.set_single_admin(None)

    # Public API

    def show_object(self, state):
        self._set_state(OBJECT_UNSET)
        if state:
            self._object_state = state
            self._set_state(OBJECT_INACTIVE)

    def set_single_admin(self, admin):
        self.admin = admin

    def get_admin_for_object(self, object):
        # override me to do e.g. multi.get_admin_for_object
        return self.admin

    # Private

    def _pack_widget(self, widget):
        assert self._widget == None
        self._widget = widget
        self._widget.show()
        self.pack_start(self._widget, True, True)

        return self._widget

    def _get_widget_constructor(self, state):
        def not_component_state():
            return gtk.Label('')

        def no_bundle(failure):
            failure.trap(errors.NoBundleError)
            self.debug(
                'No specific GTK admin for this component, using default')
            return ("flumotion/component/base/admin_gtk.py", "BaseAdminGtk")

        def got_entry_point((filename, procname)):
            # getEntryByType for admin/gtk returns a factory function
            # for creating
            # flumotion.component.base.admin_gtk.BaseAdminGtk
            # subclass instances
            modname = common.pathToModuleName(filename)
            return admin.getBundledFunction(modname, procname)

        def got_factory(factory):
            # instantiate from factory and wrap in a NodeBook
            return lambda: NodeBook(factory(state, admin))

        def sleeping_component(failure):
            failure.trap(errors.SleepingComponentError)
            return lambda: gtk.Label('Component %s is still sleeping' %
                                     state.get('name'))

        admin = self.get_admin_for_object(state)
        if not isinstance(state, planet.AdminComponentState):
            return not_component_state

        d = admin.callRemote('getEntryByType', state, 'admin/gtk')
        d.addErrback(no_bundle)
        d.addCallback(got_entry_point)
        d.addCallback(got_factory)
        d.addErrback(sleeping_component)
        return d

    def _object_unset_to_inactive(self):
        def invalidate(_):
            self._set_state(OBJECT_UNSET)
        def set(state, key, value):
            if key == 'mood':
                if (value != planet.moods.lost.value
                    and value != planet.moods.sleeping.value):
                    self._set_state(OBJECT_ACTIVE)
                else:
                    self._set_state(OBJECT_INACTIVE)

        assert self._object_state is not None
        self._object_state.addListener(
            self, invalidate=invalidate, set=set)
        if self._object_state.hasKey('mood'):
            set(self._object_state, 'mood', self._object_state.get('mood'))

    def _object_inactive_to_active(self):
        def got_widget_constructor(proc, callStamp):
            if callStamp != self._callStamp:
                # in the time that _get_widget_constructor was running,
                # perhaps the user selected another object; only update
                # the ui if that did not happen
                self.debug('ignoring widget constructor %r, state %d, '
                           'callstamps %d/%d', proc, self._state,
                           callStamp, self._callStamp)
                return
            widget = proc()
            return self._pack_widget(widget)

        self._callStamp += 1
        callStamp = self._callStamp
        d = self._get_widget_constructor(self._object_state)
        d.addCallback(got_widget_constructor, callStamp)

    def _object_active_to_inactive(self):
        # prevent got_widget_constructor from adding the widget above
        self._callStamp += 1
        if not self._widget:
            return

        self.remove(self._widget)
        # widget maybe a gtk.Label or a NodeBook
        if hasattr(self._widget, 'admingtk'):
            if self._widget.admingtk:
                # needed for compatibility with managers with old code
                if hasattr(self._widget.admingtk, 'cleanup'):
                    self._widget.admingtk.cleanup()
                del self._widget.admingtk
        self._widget = None

    def _object_inactive_to_unset(self):
        self._object_state.removeListener(self)
        self._object_state = None

    def _set_state(self, state):
        uptable = [self._object_unset_to_inactive,
                   self._object_inactive_to_active]
        downtable = [self._object_inactive_to_unset,
                     self._object_active_to_inactive]
        if self._state < state:
            while self._state < state:
                self.log('object %r state change: %d++', self._object_state,
                         self._state)
                self._state += 1
                uptable[self._state - 1]()
        else:
            while self._state > state:
                self.log('object %r state change: %d--', self._object_state,
                         self._state)
                self._state -= 1
                downtable[self._state]()

gobject.type_register(ComponentView)
