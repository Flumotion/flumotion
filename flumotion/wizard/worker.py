# -*- Mode: Python -*-
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


import gobject
import gtk
from flumotion.common import pygobject
from flumotion.common.pygobject import gsignal
from flumotion.twisted import flavors
from flumotion.twisted.compat import implements

class WorkerListStore(gtk.ListStore):
    implements(flavors.IStateListener)
    gsignal('changed')

    def __init__(self, whs):
        gtk.ListStore.__init__(self, str)
        for x in whs.get('names'):
            i = self.append()
            self.set_value(i, 0, x)
        whs.addListener(self, set=None)

    def stateAppend(self, state, key, val):
        if key == 'names':
            i = self.append()
            self.set_value(i, 0, val)
            self.emit('changed')

    def stateRemove(self, state, key, val):
        if key == 'names':
            for r in self:
                if self.get_value(r.iter, 0) == val:
                    self.remove(r.iter)
                    self.emit('changed')
                    return
pygobject.type_register(WorkerListStore)

class WorkerList(gtk.HBox):
    gsignal('worker-selected', str)
    _combobox = None
    _label = None

    def __init__(self):
        gtk.HBox.__init__(self)

        self._combobox = gtk.ComboBox()
        self._label = gtk.Label('Worker: ')

        self._label.show()
        self.pack_start(self._label, False, False, 0)
        vb = gtk.VBox()
        self.pack_start(vb, False, False, 0)
        vb.show()
        a = gtk.Alignment(0.5, 0.5)
        a.show()
        vb.pack_start (a, True, False, 0)
        cell = gtk.CellRendererText()
        self._combobox.pack_start(cell, True)
        self._combobox.add_attribute(cell, 'text', 0)

        def on_changed(cb):
            self.emit('worker-selected', self.get_worker())

        self._combobox.connect('changed', on_changed)
        self._combobox.show()
        # GTK 2.4
        try:
            self._combobox.set_property('focus-on-click', False)
            self._combobox.set_property('has-frame', False)
        except TypeError:
            pass
        a.add(self._combobox)

    def set_worker_heaven_state(self, whs):
        self._combobox.set_model(WorkerListStore(whs))
        self.select_worker(None)

        def on_model_changed(model):
            if not self.get_worker():
                # need to select a new worker
                self.select_worker(None) # will emit if worker selected
                if not self.get_worker():
                    # no workers present!
                    self.emit('worker-selected', None)

        self._combobox.get_model().connect('changed', on_model_changed)

    def select_worker(self, worker):
        # worker == none means select first worker
        for r in self._combobox.get_model():
            if not worker or r.model.get_value(r.iter, 0) == worker:
                self._combobox.set_active_iter(r.iter)
                return

        if worker:
            # FIXME: let's not print, have correct logging
            print 'warning: worker %s not available' % worker

    def get_worker(self):
        i = self._combobox.get_active_iter()
        if i:
            return self._combobox.get_model().get_value(i, 0)

        return None

    def notify_selected(self):
        self.emit('worker-selected', self.get_worker())

pygobject.type_register(WorkerList)
