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

import os

import gettext
import gtk

from twisted.internet import defer

from flumotion.common import errors, componentui
from flumotion.twisted import flavors
from flumotion.component.base.admin_gtk import BaseAdminGtk, BaseAdminGtkNode

_ = gettext.gettext
__version__ = "$Rev$"
(
  COLUMN_ID,
  COLUMN_USER,
  COLUMN_ADDRESS,
) = range(3)


class KeycardsNode(BaseAdminGtkNode):
    def render(self):
        self._iters = {} # iter -> data dict mapping
        self.model = gtk.ListStore(str, str, str)

        gladeFile = os.path.join('flumotion', 'component', 'bouncers',
            'bouncer.glade')
        d = self.loadGladeFile(gladeFile)
        d.addCallback(self._loadGladeFileCallback)
        return d

    def _loadGladeFileCallback(self, widgetTree):
        self.wtree = widgetTree

        self.widget = self.wtree.get_widget('keycards-widget')
        self.tree = self.wtree.get_widget('keycards-treeview')
        self.tree.set_model(self.model)
        self.tree.set_headers_clickable(True)
        treeselection = self.tree.get_selection()
        treeselection.set_mode(gtk.SELECTION_MULTIPLE)

        button = self.wtree.get_widget('expire-button')
        button.connect('clicked', self._expire_clicked, treeselection)

        col = gtk.TreeViewColumn('ID', gtk.CellRendererText(), text=COLUMN_ID)
        self.tree.append_column(col)
        col = gtk.TreeViewColumn('user', gtk.CellRendererText(),
            text=COLUMN_USER)
        self.tree.append_column(col)
        col = gtk.TreeViewColumn('address', gtk.CellRendererText(),
            text=COLUMN_ADDRESS)
        self.tree.append_column(col)

        d = self.callRemote('getUIState')
        d.addCallback(self._gotStateCallback)
        d.addCallback(lambda x: self.widget)
        return d

    def _gotStateCallback(self, result):
        # we need to store the state ref we get; if not, it gets GC'd here,
        # and then in the manager, and then our listener doesn't work anymore
        self._uiState = result
        keycardsData = result.get('keycards')
        self.debug('_gotState: got %d keycards' % len(keycardsData))

        for data in keycardsData:
            self._append(data)

        def append(object, key, value):
            self._append(value)
        def remove(object, key, value):
            self._remove(value)

        self._uiState.addListener(self, append=append, remove=remove)

    def _expire_clicked(self, button, treeselection):
        (model, pathlist) = treeselection.get_selected_rows()
        ids = []
        for path in pathlist:
            iter = model.get_iter(path)
            id = model.get_value(iter, COLUMN_ID)
            ids.append(id)

        self.debug('expiring %d keycards' % len(ids))

        d = defer.succeed(None)
        for id in ids:
            # we need to pass in i as well, to make sure we actually iterate
            # instead of adding a bunch of lambdas with the same id to expire
            d.addCallback(lambda res, i: self.callRemote('expireKeycardId', i),
                id)

        return d

    def _append(self, data):
        id = data['id']
        iter = self.model.append()
        # GtkListStore garantuees validity of iter as long as row lives
        self._iters[id] = iter
        self.model.set_value(iter, COLUMN_ID, id)

        if 'username' in data.keys():
            self.model.set_value(iter, COLUMN_USER, data['username'])
        if 'address' in data.keys():
            self.model.set_value(iter, COLUMN_ADDRESS, data['address'])

    def _remove(self, data):
        id = data['id']
        iter = self._iters[id]
        del self._iters[id]
        self.model.remove(iter)

    def cleanup(self):
        self._uiState.removeListener(self)

class HTPasswdCryptAdminGtk(BaseAdminGtk):
    def setup(self):
        # FIXME: have constructor take self instead ?
        keycards = KeycardsNode(self.state, self.admin, _("Keycards"))
        self.nodes['Keycards'] = keycards
        return BaseAdminGtk.setup(self)

    def cleanup(self):
        self.nodes['Keycards'].cleanup()

GUIClass = HTPasswdCryptAdminGtk
