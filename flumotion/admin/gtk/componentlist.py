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

"""widget to display a list of components.
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
from flumotion.common.messages import ERROR, WARNING, INFO
from flumotion.common.planet import moods
from flumotion.common.pygobject import gsignal, gproperty
from flumotion.common.xmlwriter import cmpComponentType
from flumotion.twisted import flavors

__version__ = "$Rev$"
_ = gettext.gettext

_stock_icons = {
    ERROR: gtk.STOCK_DIALOG_ERROR,
    WARNING: gtk.STOCK_DIALOG_WARNING,
    INFO: gtk.STOCK_DIALOG_INFO,
    }

MOODS_INFO = {
    moods.sad: _('Sad'),
    moods.happy: _('Happy'),
    moods.sleeping: _('Sleeping'),
    moods.waking: _('Waking'),
    moods.hungry: _('Hungry'),
    moods.lost: _('Lost')}

(COL_MOOD,
 COL_NAME,
 COL_WORKER,
 COL_PID,
 COL_MSG,
 COL_STATE,
 COL_MOOD_VALUE, # to sort COL_MOOD
 COL_TOOLTIP) = range(8)


def getComponentLabel(state):
    config = state.get('config')
    return config and config.get('label', config['name'])


class ComponentList(log.Loggable, gobject.GObject):
    """
    I present a view on the list of components logged in to the manager.
    """

    implements(flavors.IStateListener)

    logCategory = 'components'

    gsignal('selection-changed', object) # state-or-None
    gsignal('show-popup-menu', int, int) # button, click time

    gproperty(bool, 'can-start-any', 'True if any component can be started',
              False)
    gproperty(bool, 'can-stop-any', 'True if any component can be stopped',
              False)

    def __init__(self, treeView):
        """
        @param treeView: the gtk.TreeView to put the view in.
        """
        gobject.GObject.__init__(self)
        self.set_property('can-start-any', False)
        self.set_property('can-stop-any', False)

        self._iters = {} # componentState -> model iter
        self._lastStates = None
        self._model = None
        self._workers = []
        self._view = None
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
            gtk.gdk.Pixbuf, # message level
            object,         # state
            int,            # mood-value
            str,            # tooltip
            )
        treeView.set_model(treeModel)

        treeSelection = treeView.get_selection()
        treeSelection.set_mode(gtk.SELECTION_MULTIPLE)
        treeSelection.connect('changed', self._view_cursor_changed_cb)

        # put in all the columns
        col = gtk.TreeViewColumn('', gtk.CellRendererPixbuf(),
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

        col = gtk.TreeViewColumn('', gtk.CellRendererPixbuf(),
                                 pixbuf=COL_MSG)
        treeView.append_column(col)


        if gtk.pygtk_version >= (2, 12):
            treeView.set_tooltip_column(COL_TOOLTIP)

        if hasattr(gtk.TreeView, 'set_rubber_banding'):
            treeView.set_rubber_banding(False)

        self._model = treeModel
        self._view = treeView

    def getSelectedNames(self):
        """
        Get the names of the currently selected components, or None if none
        are selected.

        @rtype: list of str or None
        """
        return self._getSelected(COL_NAME)

    def getSelectedStates(self):
        """
        Get the states of the currently selected components, or None if none
        are selected.

        @rtype: list of L{flumotion.common.component.AdminComponentState}
                or None
        """
        return self._getSelected(COL_STATE)

    def getComponentNames(self):
        """
        Fetches a list of all component names.

        @returns: component names
        @rtype:   list of str
        """
        names = []
        for row in self._model:
            names.append(row[COL_NAME])
        return names

    def getComponentStates(self):
        """
        Fetches a list of all component states

        @returns: component states
        @rtype:   list of L{AdminComponentState}
        """
        names = []
        for row in self._model:
            names.append(row[COL_STATE])
        return names

    def canDelete(self):
        """
        Get whether the selected components can be deleted.

        Returns True if all components are sleeping.

        Also returns False if no components are selected.

        @rtype: bool
        """
        states = self.getSelectedStates()
        if not states:
            return False
        canDelete = True
        for state in states:
            moodname = moods.get(state.get('mood')).name
            canDelete = canDelete and moodname == 'sleeping'
        return canDelete

    def canStart(self):
        """
        Get whether the selected components can be started.

        Returns True if all components are sleeping and their worked has
        logged in.

        Also returns False if no components are selected.

        @rtype: bool
        """
        # additionally to canDelete, the worker needs to be logged intoo
        if not self.canDelete():
            return False

        canStart = True
        states = self.getSelectedStates()
        for state in states:
            workerName = state.get('workerRequested')
            canStart = canStart and workerName in self._workers

        return canStart

    def canStop(self):
        """
        Get whether the selected components can be stopped.

        Returns True if none of the components are sleeping.

        Also returns False if no components are selected.

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

    def clearAndRebuild(self, components, componentNameToSelect=None):
        """
        Update the components view by removing all old components and
        showing the new ones.

        @param components: dictionary of name ->
                           L{flumotion.common.component.AdminComponentState}
        @param componentNameToSelect: name of the component to select or None
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
            self.appendComponent(component, componentNameToSelect)

        self.debug('updated components view')

    def appendComponent(self, component, componentNameToSelect):
        self.debug('adding component %r to listview' % component)
        component.addListener(self, set_=self.stateSet, append=self.stateSet,
                              remove=self.stateSet)

        titer = self._model.append()
        self._iters[component] = titer

        mood = component.get('mood')
        self.debug('component has mood %r' % mood)
        messages = component.get('messages')
        self.debug('component has messages %r' % messages)
        self._setMsgLevel(titer, messages)

        if mood != None:
            self._setMoodValue(titer, mood)

        self._model.set(titer, COL_STATE, component)
        componentName = getComponentLabel(component)
        self._model.set(titer, COL_NAME, componentName)

        pid = component.get('pid')
        self._model.set(titer, COL_PID, (pid and str(pid)) or '')

        self._updateWorker(titer, component)
        selection = self._view.get_selection()
        if (componentNameToSelect is not None and
            componentName == componentNameToSelect and
            not selection.get_selected_rows()[1]):
            selection.select_iter(titer)

        self._updateStartStop()

    def removeComponent(self, component):
        self.debug('removing component %r to listview' % component)

        titer = self._iters[component]
        self._model.remove(titer)
        del self._iters[component]

        self._updateStartStop()

    # IStateListener implementation

    def stateSet(self, state, key, value):
        if not isinstance(state, planet.AdminComponentState):
            self.warning('Got state change for unknown object %r' % state)
            return

        titer = self._iters[state]
        self.log('stateSet: state %r, key %s, value %r' % (state, key, value))

        if key == 'mood':
            self.debug('stateSet: mood of %r changed to %r' % (state, value))

            if value == moods.sleeping.value:
                self.debug('sleeping, removing local messages on %r' % state)
                for message in state.get('messages', []):
                    state.observe_remove('messages', message)

            self._setMoodValue(titer, value)
            self._updateWorker(titer, state)
        elif key == 'name':
            if value:
                self._model.set(titer, COL_NAME, value)
        elif key == 'workerName':
            self._updateWorker(titer, state)
        elif key == 'pid':
            self._model.set(titer, COL_PID, (value and str(value) or ''))
        elif key =='messages':
            self._setMsgLevel(titer, state.get('messages'))

    # Private

    def _setMsgLevel(self, titer, messages):
        icon = None

        if messages:
            messages = sorted(messages, cmp=lambda x, y: x.level - y.level)
            level = messages[0].level
            st = _stock_icons.get(level, gtk.STOCK_MISSING_IMAGE)
            w = gtk.Invisible()
            icon = w.render_icon(st, gtk.ICON_SIZE_MENU)

        self._model.set(titer, COL_MSG, icon)

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

    def workerAppend(self, name):
        self._workers.append(name)

    def workerRemove(self, name):
        self._workers.remove(name)
        for state, titer in self._iters.items():
            self._updateWorker(titer, state)

    def _updateWorker(self, titer, componentState):
        # update the worker name:
        # - italic if workerName and workerRequested are not running
        # - normal if running

        workerName = componentState.get('workerName')
        workerRequested = componentState.get('workerRequested')
        if not workerName and not workerRequested:
            #FIXME: Should we raise an error here?
            #       It's an impossible situation.
            workerName = _("[any worker]")

        markup = workerName or workerRequested
        if markup not in self._workers:
            self._model.set(titer, COL_TOOLTIP,
                    _("<b>Worker %s is not connected</b>") % markup)
            markup = "<i>%s</i>" % markup
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
        mood = moods.get(value)
        self._model.set(titer, COL_TOOLTIP,
                _("<b>Component is %s</b>") % (MOODS_INFO[mood].lower(), ))

        self._updateStartStop()

    def _getSelected(self, col_name):
        # returns None if no components are selected, a list otherwise
        selection = self._view.get_selection()
        if not selection:
            return None
        model, selected_tree_rows = selection.get_selected_rows()
        selected = []
        for tree_row in selected_tree_rows:
            component_state = model[tree_row][col_name]
            selected.append(component_state)
        return selected

    def _getMoodPixbufs(self):
        # load all pixbufs for the moods
        pixbufs = {}
        for i in range(0, len(moods)):
            name = moods.get(i).name
            pixbufs[i] = gtk.gdk.pixbuf_new_from_file_at_size(
                os.path.join(configure.imagedir, 'mood-%s.png' % name),
                24, 24)

        return pixbufs

    def _selectionChanged(self):
        states = self.getSelectedStates()

        if not states:
            self.debug(
                'no component selected, emitting selection-changed None')
            # Emit this in an idle, since popups will not be shown
            # before this has completed, and it might possibly take a long
            # time to finish all the callbacks connected to selection-changed
            # This is not the proper fix, but makes the popups show up faster
            gobject.idle_add(self.emit, 'selection-changed', [])
            return

        if states == self._lastStates:
            self.debug('no new components selected, no emitting signal')
            return

        self.debug('components selected, emitting selection-changed')
        self.emit('selection-changed', states)
        self._lastStates = states

    def _showPopupMenu(self, event):
        selection = self._view.get_selection()
        retval = self._view.get_path_at_pos(int(event.x), int(event.y))
        if retval is None:
            selection.unselect_all()
            return
        clicked_path = retval[0]
        selected_path = selection.get_selected_rows()[1]
        if clicked_path not in selected_path:
            selection.unselect_all()
            selection.select_path(clicked_path)
        self.emit('show-popup-menu', event.button, event.time)

    # Callbacks

    def _view_cursor_changed_cb(self, *args):
        self._selectionChanged()

    def _view_button_press_event_cb(self, treeview, event):
        if event.button == 3:
            self._showPopupMenu(event)
            return True
        return False


gobject.type_register(ComponentList)


# this file can be run to test ComponentList
if __name__ == '__main__':

    from twisted.internet import reactor
    from twisted.spread import jelly

    class Main:

        def __init__(self):
            self.window = gtk.Window()
            self.widget = gtk.TreeView()
            self.window.add(self.widget)
            self.window.show_all()
            self.view = ComponentList(self.widget)
            self.view.connect('selection-changed', self._selection_changed_cb)
            self.view.connect('show-popup-menu', self._show_popup_menu_cb)
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
                {'config': {'name': 'one'},
                 'mood': moods.happy.value,
                 'workerName': 'R2D2', 'pid': 1, 'type': 'dummy'})
            components['one'] = c
            c = self._createComponent(
                {'config': {'name': 'two'},
                 'mood': moods.sad.value,
                 'workerName': 'R2D2', 'pid': 2, 'type': 'dummy'})
            components['two'] = c
            c = self._createComponent(
                {'config': {'name': 'three'},
                 'mood': moods.hungry.value,
                 'workerName': 'C3PO', 'pid': 3, 'type': 'dummy'})
            components['three'] = c
            c = self._createComponent(
                {'config': {'name': 'four'},
                 'mood': moods.sleeping.value,
                 'workerName': 'C3PO', 'pid': None, 'type': 'dummy'})
            components['four'] = c
            self.view.clearAndRebuild(components)

        def _selection_changed_cb(self, view, states):
            # states: list of AdminComponentState
            print "Selected component(s) %s" % ", ".join(
                [s.get('config')['name'] for s in states])

        def _show_popup_menu_cb(self, view, button, time):
            print "Pressed button %r at time %r" % (button, time)


    app = Main()

    app.update()

    gtk.main()
