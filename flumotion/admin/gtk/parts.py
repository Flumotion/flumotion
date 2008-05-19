# -*- Mode: Python; test-case-name: flumotion.test.test_parts -*-
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

import os

from gettext import gettext as _

import gobject
import gtk
from zope.interface import implements

from flumotion.configure import configure
from flumotion.common import log, planet
from flumotion.common.planet import moods
from flumotion.common.pygobject import gsignal, gproperty
from flumotion.common.pygobject import with_construct_properties
from flumotion.twisted import flavors

__version__ = "$Rev$"
(COL_MOOD,
 COL_NAME,
 COL_WORKER,
 COL_PID,
 COL_STATE,
 COL_MOOD_VALUE, # to sort COL_MOOD
 COL_CPU) = range(7)

MOODS_INFO = {
    moods.sad: _('Sad'),
    moods.happy: _('Happy'),
    moods.sleeping: _('Sleeping'),
    moods.waking: _('Waking'),
    moods.hungry: _('Hungry'),
    moods.lost: _('Lost')
    }

def getComponentLabel(state):
    config = state.get('config')
    return config and config.get('label', config['name'])

class AdminStatusbar:
    """
    I implement the status bar used in the admin UI.
    """
    def __init__(self, widget):
        """
        @param widget: a gtk.Statusbar to wrap.
        """
        self._widget = widget

        self._cids = {} # hash of context -> context id
        self._mids = {} # hash of context -> message id lists
        self._contexts = ['main', 'notebook']

        for context in self._contexts:
            self._cids[context] = widget.get_context_id(context)
            self._mids[context] = []

    def clear(self, context=None):
        """
        Clear the status bar for the given context, or for all contexts
        if none specified.
        """
        if context:
            self._clear_context(context)
            return

        for context in self._contexts:
            self._clear_context(context)

    def push(self, context, message):
        """
        Push the given message for the given context.

        @returns: message id
        """
        mid = self._widget.push(self._cids[context], message)
        self._mids[context].append(mid)
        return mid

    def pop(self, context):
        """
        Pop the last message for the given context.

        @returns: message id popped, or None
        """
        if len(self._mids[context]):
            mid = self._mids[context].pop()
            self._widget.remove(self._cids[context], mid)
            return mid

        return None

    def set(self, context, message):
        """
        Replace the current top message for this context with this new one.

        @returns: the message id of the message pushed
        """
        self.pop(context)
        return self.push(context, message)

    def remove(self, context, mid):
        """
        Remove the message with the given id from the given context.

        @returns: whether or not the given mid was valid.
        """
        if not mid in self._mids[context]:
            return False

        self._mids[context].remove(mid)
        self._widget.remove(self._cids[context], mid)
        return True

    def _clear_context(self, context):
        if not context in self._cids.keys():
            return

        for mid in self._mids[context]:
            self.remove(context, mid)

class ComponentsView(log.Loggable, gobject.GObject):
    """
    I present a view on the list of components logged in to the manager.
    """

    implements(flavors.IStateListener)

    logCategory = 'components'

    gsignal('selection-changed', object)  # state-or-None
    gsignal('activated', object, str) # state, action name
    #gsignal('right-clicked', object, int, float)

    gproperty(bool, 'can-start-any', 'True if any component can be started',
              False, construct=True)
    gproperty(bool, 'can-stop-any', 'True if any component can be stopped',
              False, construct=True)
    _model = _view = _moodPixbufs = None # i heart pychecker

    def __init__(self, tree_widget):
        """
        @param tree_widget: the gtk.TreeWidget to put the view in.
        """
        self.__gobject_init__()

        self._view = tree_widget

        # PyGTK bug #479012 was fixed in 2.12.1 and prevents this from crashing
        if gtk.pygtk_version >= (2, 12, 1):
            self._view.props.has_tooltip = True
            self._view.connect("query-tooltip",
                               self._tree_view_query_tooltip_cb)
            def selection_changed_cb(selection):
                self._view.trigger_tooltip_query()
            self._view.get_selection().connect('changed', selection_changed_cb)

        self._model = gtk.ListStore(gtk.gdk.Pixbuf, str, str, str, object,
                                     int, str)

        self._view.get_selection().connect('changed',
                                            self._view_cursor_changed_cb)
        self._view.connect('button-press-event',
            self._view_button_press_event_cb)
        self._view.set_model(self._model)
        self._view.set_headers_visible(True)

        self._add_columns()

        self._moodPixbufs = self._getMoodPixbufs()
        self._iters = {} # componentState -> model iter
        self._last_states = None
        self._view.get_selection().set_mode(gtk.SELECTION_MULTIPLE)
        if hasattr(gtk.TreeView, 'set_rubber_banding'):
            self._view.set_rubber_banding(False)

    __init__ = with_construct_properties (__init__)

    def _add_columns(self):
        # put in all the columns
        col = gtk.TreeViewColumn(_('Mood'), gtk.CellRendererPixbuf(),
                                 pixbuf=COL_MOOD)
        col.set_sort_column_id(COL_MOOD_VALUE)
        self._view.append_column(col)

        col = gtk.TreeViewColumn(_('Component'), gtk.CellRendererText(),
                                 text=COL_NAME)
        col.set_sort_column_id(COL_NAME)
        self._view.append_column(col)

        col = gtk.TreeViewColumn(_('Worker'), gtk.CellRendererText(),
                                 markup=COL_WORKER)
        col.set_sort_column_id(COL_WORKER)
        self._view.append_column(col)

        t = gtk.CellRendererText()
        col = gtk.TreeViewColumn(_('PID'), t, text=COL_PID)
        col.set_sort_column_id(COL_PID)
        self._view.append_column(col)

        # the additional columns need not be added

    # load all pixbufs for the moods
    def _getMoodPixbufs(self):
        pixbufs = {}
        for i in range(0, len(moods)):
            name = moods.get(i).name
            pixbufs[i] = gtk.gdk.pixbuf_new_from_file(os.path.join(
                configure.imagedir, 'mood-%s.png' % name))

        return pixbufs

    def _tooltips_get_context(self, treeview, keyboard_tip, x, y):
        if keyboard_tip:
            path = treeview.get_cursor()
            if not path:
                return
        else:
            x, y = treeview.convert_widget_to_bin_window_coords(x, y)
            path =  treeview.get_path_at_pos(x, y)
            if not path:
                return

        return path

    def _tree_view_query_tooltip_cb(self, treeview, x, y, keyboard_tip,
                                     tooltip):
        path = self._tooltips_get_context(treeview, keyboard_tip, x, y)
        if path is None:
            return

        mood = self._model[path[0]][COL_MOOD_VALUE]
        tooltip.set_markup("<b>%s</b>" % _("Component is %s") % (
            MOODS_INFO[moods.get(mood)]))

        return True

    def _view_cursor_changed_cb(self, *args):
        states = self.get_selected_states()

        if not states:
            self.debug('no component selected, emitting selection-changed None')
            self.emit('selection-changed', None)
            return

        if states is self._last_states:
            self.debug('no new components selected, no emitting signal')
            return

        self.debug('components selected, emitting selection-changed')
        self.emit('selection-changed', states)
        self._last_states = states

    def _view_button_press_event_cb(self, treeview, event):
        if event.button != 3:
            return
        path = treeview.get_path_at_pos(int(event.x),int(event.y))
        selection = treeview.get_selection()
        rows = selection.get_selected_rows()
        if path[0] not in rows[1]:
            selection.unselect_all()
            selection.select_path(path[0])
        states = self.get_selected_states()
        self.debug("button pressed selected states %r", states)
        time = event.time
        popup = ComponentMenu(self)
        popup.popup(None, None, None, event.button, time)
        popup.connect('activated', self._activated_cb, states)
        gtk.main_iteration()
        return True

    def _activated_cb(self, menu, action, states):
        self.debug('emitting activated')
        self.emit('activated', states, action)

    def _get_selected(self, col_name):
        selection = self._view.get_selection()
        if not selection:
            return None
        model, selected_tree_rows = selection.get_selected_rows()
        selected = []
        for tree_row in selected_tree_rows:
            component_state = model[tree_row][col_name]
            selected.append(component_state)
        return selected

    def get_selected_names(self):
        """
        Get the names of the currently selected component, or None.

        @rtype: string
        """
        return self._get_selected(COL_NAME)

    def get_selected_states(self):
        """
        Get the states of the currently selected component, or None.

        @rtype: L{flumotion.common.component.AdminComponentState}
        """
        return self._get_selected(COL_STATE)

    def can_start(self):
        """
        Get whether the selected components can be started.

        @rtype: bool
        """
        states = self.get_selected_states()
        if not states:
            return False
        can_start = True
        for state in states:
            moodname = moods.get(state.get('mood')).name
            can_start = can_start and moodname == 'sleeping'
        return can_start

    def can_stop(self):
        """
        Get whether the selected components can be stoped.

        @rtype: bool
        """
        states = self.get_selected_states()
        if not states:
            return False
        can_stop = True
        for state in states:
            moodname = moods.get(state.get('mood')).name
            can_stop = can_stop and moodname != 'sleeping'
        return can_stop

    def update_start_stop_props(self):
        oldstop = self.get_property('can-stop-any')
        oldstart = self.get_property('can-start-any')
        moodnames = [moods.get(x[COL_MOOD_VALUE]).name for x in self._model]
        can_stop = bool([x for x in moodnames if (x!='sleeping')])
        can_start = bool([x for x in moodnames if (x=='sleeping')])
        if oldstop != can_stop:
            self.set_property('can-stop-any', can_stop)
        if oldstart != can_start:
            self.set_property('can-start-any', can_start)

    def _removeListenerForeach(self, model, path, iter):
        # remove the listener for each state object
        state = model.get(iter, COL_STATE)[0]
        state.removeListener(self)

    def update(self, components):
        """
        Update the components view by removing all old components and
        showing the new ones.

        @param components: dictionary of name ->
                           L{flumotion.common.component.AdminComponentState}
        """
        # remove all Listeners
        self._model.foreach(self._removeListenerForeach)

        self.debug('updating components view')
        # clear and rebuild
        self._model.clear()
        self._iters = {}

        # get a dictionary of components
        names = components.keys()
        names.sort()

        for name in names:
            component = components[name]
            self.debug('adding component %r to listview' % component)
            component.addListener(self, self.stateSet)

            iter = self._model.append()
            self._iters[component] = iter

            mood = component.get('mood')
            self.debug('component has mood %r' % mood)
            messages = component.get('messages')
            self.debug('component has messages %r' % messages)

            if mood != None:
                self._set_mood_value(iter, mood)

            self._model.set(iter, COL_STATE, component)

            self._model.set(iter, COL_NAME, getComponentLabel(component))

            self._updateWorker(iter, component)
        self.debug('updated components view')

        self.update_start_stop_props()

    def _updateWorker(self, iter, componentState):
        # update the worker name:
        # - italic [any worker] if no workerName/workerRequested
        # - italic if workerName, or no workerName but workerRequested
        # - normal if running

        workerName = componentState.get('workerName')
        workerRequested = componentState.get('workerRequested')
        if not workerName:
            workerName = "%s" % workerRequested
            if not workerRequested:
                workerName = _("[any worker]")

        mood = componentState.get('mood')
        markup = workerName
        if mood == moods.sleeping.value:
            markup = "<i>%s</i>" % workerName
        self._model.set(iter, COL_WORKER, markup)
        pid = componentState.get('pid')
        self._model.set(iter, COL_PID, (pid and str(pid)) or '')

    def stateSet(self, state, key, value):
        if not isinstance(state, planet.AdminComponentState):
            self.warning('Got state change for unknown object %r' % state)
            return

        iter = self._iters[state]
        self.log('stateSet: state %r, key %s, value %r' % (state, key, value))

        if key == 'mood':
            self._set_mood_value(iter, value)
            self._updateWorker(iter, state)
        elif key == 'name':
            if value:
                self._model.set(iter, COL_NAME, value)
        elif key == 'workerName':
            self._updateWorker(iter, state)

    def _set_mood_value(self, iter, value):
        """
        Set the mood value on the given component name.

        @type  value: int
        """
        self._model.set(iter, COL_MOOD, self._moodPixbufs[value])
        self._model.set(iter, COL_MOOD_VALUE, value)

        self.update_start_stop_props()

gobject.type_register(ComponentsView)

class ComponentMenu(gtk.Menu):

    gsignal('activated', str)

    def __init__(self, componentsView):
        """
        @param state: L{flumotion.common.component.AdminComponentState}
        """
        gtk.Menu.__init__(self)
        self._items = {} # name -> gtk.MenuItem

        self.set_title(_('Component'))

        i = gtk.MenuItem(_('_Restart'))
        self.append(i)
        self._items['restart'] = i

        i = gtk.MenuItem(_('_Start'))
        can_start = componentsView.can_start()
        if not can_start:
            i.set_property('sensitive', False)
        self.append(i)
        self._items['start'] = i

        i = gtk.MenuItem(_('St_op'))
        can_stop = componentsView.can_stop()
        if not can_stop:
            i.set_property('sensitive', False)
        self.append(i)
        self._items['stop'] = i

        i = gtk.MenuItem(_('_Delete'))
        if not can_start:
            i.set_property('sensitive', False)
        self.append(i)
        self._items['delete'] = i

        self.append(gtk.SeparatorMenuItem())

        i = gtk.MenuItem(_('Reload _code'))
        self.append(i)
        self._items['reload'] = i

        i = gtk.MenuItem(_('_Modify element property ...'))
        self.append(i)
        self._items['modify'] = i

        i = gtk.MenuItem(_('_Kill job'))
        self.append(i)
        self._items['kill'] = i

        # connect callback
        for name in self._items.keys():
            i = self._items[name]
            i.connect('activate', self._activated_cb, name)

        self.show_all()

    def _activated_cb(self, item, name):
        self.emit('activated', name)

gobject.type_register(ComponentMenu)
