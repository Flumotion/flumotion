# -*- Mode: Python -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# Flumotion - a streaming media server
# Copyright (C) 2004,2005 Fluendo, S.L. (www.fluendo.com). All rights reserved.

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

import gobject
import gtk
import gtk.glade

from flumotion.configure import configure
from flumotion.common import log, component

from flumotion.common.component import moods
from flumotion.common.pygobject import gsignal

COL_MOOD      = 0
COL_NAME      = 1
COL_WORKER    = 2
COL_PID       = 3
COL_STATE     = 4

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
    
    logCategory = 'components'
    gsignal('selected', str)
    
    def __init__(self, tree_widget):
        """
        @param tree_widget: the gtk.TreeWidget to put the view in.
        """
        self.__gobject_init__()
        
        self._view = tree_widget
        self._model = gtk.ListStore(gtk.gdk.Pixbuf, str, str, int, object)

        self._view.connect('cursor-changed', self._view_cursor_changed_cb)
        self._view.set_model(self._model)
        self._view.set_headers_visible(True)

        # put in all the columns
        col = gtk.TreeViewColumn('Mood', gtk.CellRendererPixbuf(),
                                 pixbuf=COL_MOOD)
        self._view.append_column(col)

        col = gtk.TreeViewColumn('Component', gtk.CellRendererText(),
                                 text=COL_NAME)
        self._view.append_column(col)

        col = gtk.TreeViewColumn('Worker', gtk.CellRendererText(),
                                 text=COL_WORKER)
        self._view.append_column(col)
        
        col = gtk.TreeViewColumn('PID', gtk.CellRendererText(),
                                 text=COL_PID)

        self._view.append_column(col)

        self._moodPixbufs = self._getMoodPixbufs()
        self._iters = {} # componentState -> model iter

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
        name = self.get_selected_name()

        if not name:
            self.debug('no component selected')
            return

        self.emit('selected', name)

    def get_selected_name(self):
        """
        Get the name of the currently selected component, or None.
        """
        selection = self._view.get_selection()
        sel = selection.get_selected()
        if not sel:
            return None
        model, iter = sel
        if not iter:
            return
        
        return model.get(iter, COL_NAME)[0]

    def update(self, components):
        """
        Update the components view.

        @param components: list of
                           L{flumotion.common.component.AdminComponentState}
        """
        self._model.clear()
        self._iters = {}

        # get a dictionary of components
        names = components.keys()
        names.sort()

        for name in names:
            component = components[name]
            iter = self._model.append()
            self._iters[component] = iter
            mood = component.get('mood')
            self._model.set(iter, COL_MOOD, self._moodPixbufs[mood])
            self._model.set(iter, COL_NAME, component.get('name'))
            self._model.set(iter, COL_WORKER, component.get('workerName'))
            self._model.set(iter, COL_PID, component.get('pid'))
            self._model.set(iter, COL_STATE, component)

    def set_mood_value(self, state, value):
        """
        Set the mood value on the given component name.
        @param state: L{flumotion.common.component.AdminComponentState}
        @param value: int
        """
        iter = self._iters[state]
        self._model.set(iter, COL_MOOD, self._moodPixbufs[value])

gobject.type_register(ComponentsView)
    
