# -*- Mode: Python -*-
# vi:si:et:sw=4:sts=4:ts=4

# Flumotion - a streaming media server
# Copyright (C) 2004,2005,2006,2007,2008,2009 Fluendo, S.L.
# Copyright (C) 2010,2011 Flumotion Services, S.A.
# All rights reserved.
#
# This file may be distributed and/or modified under the terms of
# the GNU Lesser General Public License version 2.1 as published by
# the Free Software Foundation.
# This file is distributed without any warranty; without even the implied
# warranty of merchantability or fitness for a particular purpose.
# See "LICENSE.LGPL" in the source distribution for more information.
#
# Headers in this file shall remain intact.

import gettext

import gobject
import gtk
import pango
from zope.interface import implements

from flumotion.common.pygobject import gsignal
from flumotion.twisted import flavors

__version__ = "$Rev$"
_ = gettext.gettext


class WorkerListStore(gtk.ListStore):
    implements(flavors.IStateListener)
    gsignal('changed')

    def __init__(self, whs):
        gtk.ListStore.__init__(self, str)
        for x in whs.get('names'):
            i = self.append()
            self.set_value(i, 0, x)
        whs.addListener(self, append=self.stateAppend,
                        remove=self.stateRemove)

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
gobject.type_register(WorkerListStore)


class WorkerList(gtk.HBox):
    gsignal('worker-selected', str)
    _combobox = None
    _label = None

    def __init__(self):
        gtk.HBox.__init__(self)

        self._combobox = gtk.ComboBox()
        self._label = gtk.Label(_('Worker:'))

        self._label.show()
        self.pack_start(self._label, False, False, 0)
        vb = gtk.VBox()
        self.pack_start(vb, False, False, 10)
        vb.show()
        a = gtk.Alignment(0.5, 0.5)
        a.show()
        vb.pack_start(a, True, False, 0)
        cell = gtk.CellRendererText()
        cell.set_property('ellipsize', pango.ELLIPSIZE_MIDDLE)
        cell.set_property('width', 100)
        self._combobox.pack_start(cell, True)
        self._combobox.add_attribute(cell, 'text', 0)

        def onChanged(cb):
            self.emit('worker-selected', self.getWorker())

        self._combobox.connect('changed', onChanged)
        self._combobox.show()
        # GTK 2.4
        try:
            self._combobox.set_property('focus-on-click', False)
            self._combobox.set_property('has-frame', False)
        except TypeError:
            pass
        a.add(self._combobox)

    def setWorkerHeavenState(self, whs):
        self._combobox.set_model(WorkerListStore(whs))
        self.selectWorker(None)

        def onModelChanged(model):
            if not self.getWorker():
                # need to select a new worker
                self.selectWorker(None) # will emit if worker selected
                if not self.getWorker():
                    # no workers present!
                    self.emit('worker-selected', None)

        self._combobox.get_model().connect('changed', onModelChanged)

    def selectWorker(self, worker):
        # worker == none means select first worker
        for r in self._combobox.get_model():
            if not worker or r.model.get_value(r.iter, 0) == worker:
                self._combobox.set_active_iter(r.iter)
                return

        if worker:
            # FIXME: let's not print, have correct logging
            print 'warning: worker %s not available' % worker

    def getWorker(self):
        i = self._combobox.get_active_iter()
        if i:
            return self._combobox.get_model().get_value(i, 0)

        return None

    def notifySelected(self):
        self.emit('worker-selected', self.getWorker())

gobject.type_register(WorkerList)
