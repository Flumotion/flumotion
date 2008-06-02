# -*- Mode: Python; test-case-name: flumotion.test.test_parts -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# Flumotion - a streaming media server
# Copyright (C) 2004,2005,2006,2007,2008 Fluendo, S.L. (www.fluendo.com).
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

"""
This file contains a collection of widgets used to compose the list
of components used in the administration interface.
It contains:
  - ComponentList: a treeview + treemodel abstraction
  - ContextMenu: the menu which pops up when you right click
"""

import gettext
import os

import gobject
import gtk
from zope.interface import implements

from flumotion.configure import configure
from flumotion.common import log, planet
from flumotion.common.planet import moods
from flumotion.common.pygobject import gsignal, gproperty
from flumotion.common.pygobject import with_construct_properties
from flumotion.common.xmlwriter import cmpComponentType
from flumotion.twisted import flavors

__version__ = "$Rev$"
_ = gettext.gettext

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
        canStart = componentsView.canStart()
        if not canStart:
            i.set_property('sensitive', False)
        self.append(i)
        self._items['start'] = i

        i = gtk.MenuItem(_('St_op'))
        canStop = componentsView.canStop()
        if not canStop:
            i.set_property('sensitive', False)
        self.append(i)
        self._items['stop'] = i

        i = gtk.MenuItem(_('_Delete'))
        if not canStart:
            i.set_property('sensitive', False)
        self.append(i)
        self._items['delete'] = i

        # connect callback
        for name in self._items.keys():
            i = self._items[name]
            i.connect('activate', self._activated_cb, name)

        self.show_all()

    def _activated_cb(self, item, name):
        self.emit('activated', name)
gobject.type_register(ComponentMenu)


class ComponentList(log.Loggable, gobject.GObject):
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
    def __init__(self, treeView):
        """
        @param treeView: the gtk.TreeView to put the view in.
        """
        self.__gobject_init__()

        self._iters = {} # componentState -> model iter
        self._lastStates = None
        self._moodPixbufs = self._getMoodPixbufs()
        self._createUI(treeView)

    def _createUI(self, treeView):
        treeView.connect('button-press-event',
                         self._view_button_press_event_cb)
        treeView.set_headers_visible(True)

        treeModel = gtk.ListStore(
            gtk.gdk.Pixbuf, # mood
            str,            # name
            str,            # worker
            str,            # pid
            object,         # state
            int,            # mood-value
            str,            # cpu
            ) 
        treeView.set_model(treeModel)

        treeSelection = treeView.get_selection()
        treeSelection.set_mode(gtk.SELECTION_MULTIPLE)
        treeSelection.connect('changed', self._view_cursor_changed_cb)

        # put in all the columns
        col = gtk.TreeViewColumn(_('Status'), gtk.CellRendererPixbuf(),
                                 pixbuf=COL_MOOD)
        col.set_sort_column_id(COL_MOOD_VALUE)
        treeView.append_column(col)

        col = gtk.TreeViewColumn(_('Component'), gtk.CellRendererText(),
                                 text=COL_NAME)
        col.set_sort_column_id(COL_NAME)
        treeView.append_column(col)

        col = gtk.TreeViewColumn(_('Worker'), gtk.CellRendererText(),
                                 markup=COL_WORKER)
        col.set_sort_column_id(COL_WORKER)
        treeView.append_column(col)

        t = gtk.CellRendererText()
        col = gtk.TreeViewColumn(_('PID'), t, text=COL_PID)
        col.set_sort_column_id(COL_PID)
        treeView.append_column(col)

        # PyGTK bug #479012 was fixed in 2.12.1 and prevents this from crashing
        if gtk.pygtk_version >= (2, 12, 1):
            treeView.props.has_tooltip = True
            treeView.connect("query-tooltip", self._tree_view_query_tooltip_cb)
            def selection_changed_cb(selection):
                treeView.trigger_tooltip_query()
            treeSelection.connect('changed', selection_changed_cb)
        if hasattr(gtk.TreeView, 'set_rubber_banding'):
            treeView.set_rubber_banding(False)

        self._model = treeModel
        self._view = treeView

    __init__ = with_construct_properties (__init__)

    def getSelectedNames(self):
        """
        Get the names of the currently selected component, or None.

        @rtype: string
        """
        return self._getSelected(COL_NAME)

    def getSelectedStates(self):
        """
        Get the states of the currently selected component, or None.

        @rtype: L{flumotion.common.component.AdminComponentState}
        """
        return self._getSelected(COL_STATE)

    def getComponentNames(self):
        """Fetches a list of all component names
        @returns: component names
        @rtype: list of strings
        """
        names = []
        for row in self._model:
            names.append(row[COL_NAME])
        return names

    def getComponentStates(self):
        """Fetches a list of all component states
        @returns: component states
        @rtype: list of L{AdminComponentState}
        """
        names = []
        for row in self._model:
            names.append(row[COL_STATE])
        return names

    def canStart(self):
        """
        Get whether the selected components can be started.

        @rtype: bool
        """
        states = self.getSelectedStates()
        if not states:
            return False
        canStart = True
        for state in states:
            moodname = moods.get(state.get('mood')).name
            canStart = canStart and moodname == 'sleeping'
        return canStart

    def canStop(self):
        """
        Get whether the selected components can be stoped.

        @rtype: bool
        """
        states = self.getSelectedStates()
        if not states:
            return False
        canStop = True
        for state in states:
            moodname = moods.get(state.get('mood')).name
            canStop = canStop and moodname != 'sleeping'
        return canStop

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

        # FIXME: When we can depend on Python 2.4, use
        #        sorted(components.values(),
        #               cmp=cmpComponentType,
        #               key=operator.attrgetter('type'))
        #
        def componentSort(a, b):
            return cmpComponentType(a.get('type'),
                                    b.get('type'))
        componentsSorted = components.values()
        componentsSorted.sort(cmp=componentSort)

        for component in componentsSorted:
            self.debug('adding component %r to listview' % component)
            component.addListener(self, self.stateSet)

            titer = self._model.append()
            self._iters[component] = titer

            mood = component.get('mood')
            self.debug('component has mood %r' % mood)
            messages = component.get('messages')
            self.debug('component has messages %r' % messages)

            if mood != None:
                self._setMoodValue(titer, mood)

            self._model.set(titer, COL_STATE, component)

            self._model.set(titer, COL_NAME, getComponentLabel(component))

            pid = component.get('pid')
            self._model.set(titer, COL_PID, (pid and str(pid)) or '')

            self._updateWorker(titer, component)
        self.debug('updated components view')

        self._updateStartStop()

    # IStateListener implementation
    
    def stateSet(self, state, key, value):
        if not isinstance(state, planet.AdminComponentState):
            self.warning('Got state change for unknown object %r' % state)
            return

        titer = self._iters[state]
        self.log('stateSet: state %r, key %s, value %r' % (state, key, value))

        if key == 'mood':
            self._setMoodValue(titer, value)
            self._updateWorker(titer, state)
        elif key == 'name':
            if value:
                self._model.set(titer, COL_NAME, value)
        elif key == 'workerName':
            self._updateWorker(titer, state)

    # Private

    def _updateStartStop(self):
        oldstop = self.get_property('can-stop-any')
        oldstart = self.get_property('can-start-any')
        moodnames = [moods.get(x[COL_MOOD_VALUE]).name for x in self._model]
        canStop = bool([x for x in moodnames if (x!='sleeping')])
        canStart = bool([x for x in moodnames if (x=='sleeping')])
        if oldstop != canStop:
            self.set_property('can-stop-any', canStop)
        if oldstart != canStart:
            self.set_property('can-start-any', canStart)

    def _updateWorker(self, titer, componentState):
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
        self._model.set(titer, COL_WORKER, markup)

    def _removeListenerForeach(self, model, path, titer):
        # remove the listener for each state object
        state = model.get(titer, COL_STATE)[0]
        state.removeListener(self)

    def _setMoodValue(self, titer, value):
        """
        Set the mood value on the given component name.

        @type  value: int
        """
        self._model.set(titer, COL_MOOD, self._moodPixbufs[value])
        self._model.set(titer, COL_MOOD_VALUE, value)

        self._updateStartStop()

    def _getSelected(self, col_name):
        selection = self._view.get_selection()
        if not selection:
            return None
        model, selected_tree_rows = selection.get_selected_rows()
        selected = []
        for tree_row in selected_tree_rows:
            component_state = model[tree_row][col_name]
            selected.append(component_state)
        return selected

    def _tooltipsGetContext(self, treeview, keyboard_tip, x, y):
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

    def _getMoodPixbufs(self):
        # load all pixbufs for the moods
        pixbufs = {}
        for i in range(0, len(moods)):
            name = moods.get(i).name
            pixbufs[i] = gtk.gdk.pixbuf_new_from_file(os.path.join(
                configure.imagedir, 'mood-%s.png' % name))

        return pixbufs

    def _activate(self, states, action):
        self.debug('emitting activated')
        self.emit('activated', states, action)

    def _selectionChanged(self):
        states = self.getSelectedStates()

        if not states:
            self.debug('no component selected, emitting selection-changed None')
            self.emit('selection-changed', [])
            return

        if states is self._lastStates:
            self.debug('no new components selected, no emitting signal')
            return

        self.debug('components selected, emitting selection-changed')
        self.emit('selection-changed', states)
        self._lastStates = states

    def _updateTooltip(self, path, tooltip):
        mood = self._model[path[0]][COL_MOOD_VALUE]
        tooltip.set_markup("<b>%s</b>" % _("Component is %s") % (
            MOODS_INFO[moods.get(mood)]))

    def _showPopupMenu(self, event):
        path = self._view.get_path_at_pos(int(event.x),int(event.y))
        selection = self._view.get_selection()
        rows = selection.get_selected_rows()
        if path[0] not in rows[1]:
            selection.unselect_all()
            selection.select_path(path[0])
        states = self.getSelectedStates()
        self.debug("button pressed selected states %r", states)
        popup = ComponentMenu(self)
        popup.popup(None, None, None, event.button, event.time)
        popup.connect('activated', self._activated_cb, states)
        gtk.main_iteration()
        return True

    # Callbacks

    def _activated_cb(self, menu, action, states):
        self._activate(states, action)

    def _tree_view_query_tooltip_cb(self, treeview, x, y, keyboard_tip,
                                    tooltip):
        path = self._tooltipsGetContext(treeview, keyboard_tip, x, y)
        if path is None:
            return
        self._updateTooltip(path, tooltip)
        return True

    def _view_cursor_changed_cb(self, *args):
        self._selectionChanged()

    def _view_button_press_event_cb(self, treeview, event):
        if event.button == 3:
            self._showPopupMenu(event)
            return True
        return False



gobject.type_register(ComponentList)
