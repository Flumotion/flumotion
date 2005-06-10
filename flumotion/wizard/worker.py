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

    def __init__(self):
        gtk.HBox.__init__(self)

        def on_changed(cb):
            self.emit('worker-selected', self.get_worker())

        self.label = gtk.Label('Worker: ')
        self.label.show()
        self.pack_start(self.label, False, False, 0)
        vb = gtk.VBox()
        self.pack_start(vb, False, False, 0)
        vb.show()
        a = gtk.Alignment(0.5, 0.5)
        a.show()
        vb.pack_start (a, True, False, 0)
        self.cb = gtk.ComboBox()
        cell = gtk.CellRendererText()
        self.cb.pack_start(cell, gtk.TRUE)
        self.cb.add_attribute(cell, 'text', 0)
        self.cb.connect('changed', on_changed)
        self.cb.show()
        self.cb.set_property('focus-on-click', False)
        self.cb.set_property('has-frame', False)
        a.add(self.cb)

    def set_workers(self, l):
        self.cb.set_model(WorkerListStore(l))
        self.connect_after('realize', WorkerList.on_realize)

    def on_realize(self):
        # have to get the style from the theme, but it's not really
        # there until we're realized
        pass

    def select_worker(self, worker):
        # worker == none means select first worker
        for r in self.cb.get_model():
            if not worker or r.model.get_value(r.iter, 0) == worker:
                self.cb.set_active_iter(r.iter)
                return
        print 'warning: worker %s not available' % worker

    def get_worker(self):
        i = self.cb.get_active_iter()
        if i:
            return self.cb.get_model().get_value(i, 0)
gobject.type_register(WorkerList)
