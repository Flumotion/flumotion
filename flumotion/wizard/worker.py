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


import gobject
import gtk
from flumotion.common.pygobject import gsignal


class WorkerListStore(gtk.ListStore):
    def __init__(self, workers):
        gtk.ListStore.__init__(self, str)
        for x in workers:
            i = self.append()
            self.set_value(i, 0, x)

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
        self._combobox.pack_start(cell, gtk.TRUE)
        self._combobox.add_attribute(cell, 'text', 0)

        def on_changed(cb):
            self.emit('worker-selected', self.get_worker())

        self._combobox.connect('changed', on_changed)
        self._combobox.show()
        self._combobox.set_property('focus-on-click', False)
        self._combobox.set_property('has-frame', False)
        a.add(self._combobox)

    def set_workers(self, l):
        self._combobox.set_model(WorkerListStore(l))
        self.connect_after('realize', WorkerList.on_realize)

    def on_realize(self):
        # have to get the style from the theme, but it's not really
        # there until we're realized
        pass

    def select_worker(self, worker):
        # worker == none means select first worker
        for r in self._combobox.get_model():
            if not worker or r.model.get_value(r.iter, 0) == worker:
                self._combobox.set_active_iter(r.iter)
                return
        # FIXME: let's not print, have correct logging
        print 'warning: worker %s not available' % worker

    def get_worker(self):
        i = self._combobox.get_active_iter()
        if i:
            return self._combobox.get_model().get_value(i, 0)

        return None

gobject.type_register(WorkerList)
