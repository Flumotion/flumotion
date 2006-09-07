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

import os

from gettext import gettext as _

import gobject
import gtk
import gtk.glade

from flumotion.configure import configure
from flumotion.common import log, planet, pygobject
from flumotion.twisted import flavors
from flumotion.twisted.compat import implements
from flumotion.common.planet import moods
from flumotion.common.pygobject import gsignal, gproperty
from flumotion.common.pygobject import with_construct_properties

COL_MOOD       = 0
COL_NAME       = 1
COL_WORKER     = 2
COL_PID        = 3
COL_STATE      = 4
COL_MOOD_VALUE = 5 # to sort COL_MOOD
COL_CPU        = 6

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
    
    gsignal('has-selection', object)  # state-or-None
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
        self._model = gtk.ListStore(gtk.gdk.Pixbuf, str, str, str, object, int, str)

        self._view.connect('cursor-changed', self._view_cursor_changed_cb)
        self._view.connect('button-press-event',
            self._view_button_press_event_cb)
        self._view.set_model(self._model)
        self._view.set_headers_visible(True)

        self._add_columns()

        self._moodPixbufs = self._getMoodPixbufs()
        self._iters = {} # componentState -> model iter
        self._last_state = None
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
        
        def type_pid_datafunc(column, cell, model, iter):
            state = model.get_value(iter, COL_STATE)
            pid = state.get('pid')
            cell.set_property('text', pid and str(pid) or '')

        t = gtk.CellRendererText()
        col = gtk.TreeViewColumn('PID', t, text=COL_PID)
        col.set_cell_data_func(t, type_pid_datafunc)
        col.set_sort_column_id(COL_PID)
        self._view.append_column(col)

        def type_cpu_datafunc(column, cell, model, iter):
            state = model.get_value(iter, COL_STATE)
            cpu = state.get('cpu')
            if isinstance(cpu, float):
                cell.set_property('text', '%.2f' % (cpu * 100.0))
            else:
                cell.set_property('text', '')
                
        t = gtk.CellRendererText()
        col = gtk.TreeViewColumn('CPU %', t, text=COL_CPU)
        col.set_cell_data_func(t, type_cpu_datafunc)
        col.set_sort_column_id(COL_CPU)
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

    def _view_cursor_changed_cb(self, *args):
        # name needs to exist before being used in the child functions
        state = self.get_selected_state()

        if not state:
            self.debug('no component selected, emitting has-selection None')
            self.emit('has-selection', None)
            return
        
        if state == self._last_state:
            return

        self._last_state = state
        self.debug('component selected, emitting has-selection')
        self.emit('has-selection', state)

    def _view_button_press_event_cb(self, treeview, event):
        # right-click ?
        if event.button != 3:
            return
            
        # get iter from coordinates
        x = int(event.x)
        y = int(event.y)
        time = event.time
        pthinfo = treeview.get_path_at_pos(x, y)
        if pthinfo == None:
            return

        path, col, cellx, celly = pthinfo
        model = treeview.get_model()
        iter = model.get_iter(path)
        state = model.get(iter, COL_STATE)[0]

        popup = ComponentMenu(state)
        popup.popup(None, None, None, event.button, time)
        popup.connect('activated', self._activated_cb, state)
        gtk.main_iteration()

    def _activated_cb(self, menu, action, state):
        self.debug('emitting activated')
        self.emit('activated', state, action)
    
    def get_selected_name(self):
        """
        Get the name of the currently selected component, or None.

        @rtype: string
        """
        selection = self._view.get_selection()
        sel = selection.get_selected()
        if not sel:
            return None
        model, iter = sel
        if not iter:
            return
        
        return model.get(iter, COL_NAME)[0]

    def get_selected_state(self):
        """
        Get the state of the currently selected component, or None.

        @rtype: L{flumotion.common.component.AdminComponentState}
        """
        selection = self._view.get_selection()
        if not selection:
            return None
        sel = selection.get_selected()
        if not sel:
            return None
        model, iter = sel
        if not iter:
            return
        
        return model.get(iter, COL_STATE)[0]

    def update_start_stop_props(self):
        oldstop = self.get_property('can-stop-any')
        oldstart = self.get_property('can-start-any')
        moodnames = [moods.get(x[COL_MOOD_VALUE]).name for x in self._model]
        can_stop = bool([x for x in moodnames if (x!='lost' and x!='sleeping')])
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
            component.addListener(self)

            iter = self._model.append()
            self._iters[component] = iter
            
            mood = component.get('mood')
            self.debug('component has mood %r' % mood)
            messages = component.get('messages')
            self.debug('component has messages %r' % messages)
            
            if mood != None:
                self._set_mood_value(iter, mood)

            self._model.set(iter, COL_STATE, component)

            self._model.set(iter, COL_NAME, component.get('name'))

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
        elif key == 'cpu':
            self._model.set(iter, COL_CPU, value)

    # FIXME: proxy messages to message area
    def stateAppend(self, state, key, value):
        self.debug('stateAppend: state %r, key %s, value %r' % (
            state, key, value))
    def stateRemove(self, state, key, value):
        self.debug('stateRemove: state %r, key %s, value %r' % (
            state, key, value))
    
    def _set_mood_value(self, iter, value):
        """
        Set the mood value on the given component name.

        @type  value: int
        """
        self._model.set(iter, COL_MOOD, self._moodPixbufs[value])
        self._model.set(iter, COL_MOOD_VALUE, value)

        self.update_start_stop_props()

pygobject.type_register(ComponentsView)

class ComponentMenu(gtk.Menu):

    gsignal('activated', str)

    def __init__(self, state):
        """
        @param state: L{flumotion.common.component.AdminComponentState}
        """
        gtk.Menu.__init__(self)
        self._items = {} # name -> gtk.MenuItem

        self.set_title(_('Component'))

        i = gtk.MenuItem(_('_Start'))
        mood = moods.get(state.get('mood'))
        if mood == moods.happy:
            i.set_property('sensitive', False)
        self.append(i)
        self._items['start'] = i
        
        i = gtk.MenuItem(_('St_op'))
        if mood == moods.sleeping:
            i.set_property('sensitive', False)
        self.append(i)
        self._items['stop'] = i
        
        self.append(gtk.SeparatorMenuItem())

        i = gtk.MenuItem(_('Reload _code'))
        self.append(i)
        self._items['reload'] = i

        i = gtk.MenuItem(_('_Modify element property ...'))
        self.append(i)
        self._items['modify'] = i

        # connect callback
        for name in self._items.keys():
            i = self._items[name]
            i.connect('activate', self._activated_cb, name)
            
        self.show_all()

    def _activated_cb(self, item, name):
        self.emit('activated', name)

pygobject.type_register(ComponentMenu)

