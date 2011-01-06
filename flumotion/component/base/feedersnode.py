# -*- Mode: Python; test-case-name: flumotion.test.test_feedcomponent010 -*-
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
Feeders tab in the component UI
"""
import gettext
import os
import time

import gtk

from flumotion.common import common
from flumotion.common import format as formatting
from flumotion.common.i18n import gettexter
from flumotion.component.base.baseadminnode import BaseAdminGtkNode
from flumotion.component.base.statewatcher import StateWatcher

_ = gettext.gettext
__version__ = "$Rev$"
T_ = gettexter()


class FeedersAdminGtkNode(BaseAdminGtkNode):
    gladeFile = os.path.join('flumotion', 'component', 'base', 'feeders.glade')

    def __init__(self, state, admin):
        BaseAdminGtkNode.__init__(self, state, admin, title=_("Feeders"))
        # tree model is a model of id, uiState, StateWatcher, type
        # tree model contains feeders and their feeder clients
        # type is a str, 'feeder' or 'client'
        self.treemodel = None
        self.treeview = None
        self.selected = None
        self.labels = {}
        self._lastConnect = 0
        self._lastDisconnect = 0

    def select(self, watcher):
        if self.selected:
            self.selected.hide()
        if watcher:
            self.selected = watcher
            self.selected.show()
        else:
            self.selected = None

    def setFeederName(self, state, value):
        self.labels['feeder-name'].set_markup(_('Feeder <b>%s</b>') % value)

    def _mungeClientId(self, clientId):
        try:
            flowName, compName, feedName = common.parseFullFeedId(clientId)
            return common.feedId(compName, feedName)
        except:
            return clientId

    def setFeederClientName(self, state, value):
        if not value:
            self.labels['eater-name'].set_markup(_('<i>select an eater</i>'))
            return
        value = self._mungeClientId(value)
        self.labels['eater-name'].set_markup(_('<b>%s</b>')
                                             % (value, ))

    def setFeederClientBytesReadCurrent(self, state, value):
        txt = value and (formatting.formatStorage(value) + _('Byte')) or ''
        self.labels['bytes-read-current'].set_text(txt)
        self.updateConnectionTime()
        self.updateDisconnectionTime()

    def setFeederClientBuffersDroppedCurrent(self, state, value):
        if value is None:
            # no support for counting dropped buffers
            value = _("Unknown")
        self.labels['buffers-dropped-current'].set_text(str(value))
        self.updateConnectionTime()
        self.updateDisconnectionTime()

    def setFeederClientBytesReadTotal(self, state, value):
        txt = value and (formatting.formatStorage(value) + _('Byte')) or ''
        self.labels['bytes-read-total'].set_text(txt)

    def setFeederClientBuffersDroppedTotal(self, state, value):
        if value is None:
            # no support for counting dropped buffers
            value = _("Unknown")
        self.labels['buffers-dropped-total'].set_text(str(value))

    def setFeederClientReconnects(self, state, value):
        self.labels['connections-total'].set_text(str(value))

    def setFeederClientLastConnect(self, state, value):
        if value:
            text = formatting.formatTimeStamp(time.localtime(value))
            self.labels['connected-since'].set_text(text)
            self._lastConnect = value
            self.updateConnectionTime()

    def setFeederClientLastDisconnect(self, state, value):
        if value:
            text = formatting.formatTimeStamp(time.localtime(value))
            self.labels['disconnected-since'].set_text(text)
            self._lastDisconnect = value
            self.updateDisconnectionTime()

    def setFeederClientLastActivity(self, state, value):
        if value:
            text = formatting.formatTimeStamp(time.localtime(value))
            self.labels['last-activity'].set_text(text)

    def setFeederClientFD(self, state, value):
        if value == None:
            # disconnected
            self._table_connected.hide()
            self._table_disconnected.show()
        else:
            self._table_disconnected.hide()
            self._table_connected.show()

    # FIXME: add a timeout to update this ?

    def updateConnectionTime(self):
        if self._lastConnect:
            text = formatting.formatTime(time.time() - self._lastConnect)
            self.labels['connection-time'].set_text(text)

    # FIXME: add a timeout to update this ?

    def updateDisconnectionTime(self):
        if self._lastDisconnect:
            text = formatting.formatTime(time.time() - self._lastDisconnect)
            self.labels['disconnection-time'].set_text(text)

    def addFeeder(self, uiState, state):
        """
        @param uiState: the component's uiState
        @param state:   the feeder's uiState
        """
        feederName = state.get('feederName')
        i = self.treemodel.append(None)
        self.treemodel.set(i, 0, feederName, 1, state)
        w = StateWatcher(state,
                         {'feederName': self.setFeederName},
                         {'clients': self.addFeederClient},
                         {'clients': self.removeFeederClient})
        self.treemodel.set(i, 2, w, 3, 'feeder')
        self.treeview.expand_all()

    # FIXME: this docstring is confusing

    def addFeederClient(self, feederState, state):
        """
        @param feederState: the component's uiState
        @param state:       the feeder client's uiState
        """

        printableClientId = self._mungeClientId(state.get('client-id'))
        for row in self.treemodel:
            if self.treemodel.get_value(row.iter, 1) == feederState:
                break
        i = self.treemodel.append(row.iter)
        self.treemodel.set(i, 0, printableClientId, 1, state)
        w = StateWatcher(state,
                         {
            'client-id': self.setFeederClientName,
            'bytes-read-current': self.setFeederClientBytesReadCurrent,
            'buffers-dropped-current':
            self.setFeederClientBuffersDroppedCurrent,
            'bytes-read-total': self.setFeederClientBytesReadTotal,
            'buffers-dropped-total': self.setFeederClientBuffersDroppedTotal,
            'reconnects': self.setFeederClientReconnects,
            'last-connect': self.setFeederClientLastConnect,
            'last-disconnect': self.setFeederClientLastDisconnect,
            'last-activity': self.setFeederClientLastActivity,
            'fd': self.setFeederClientFD,
        }, {}, {})
        self.treemodel.set(i, 2, w, 3, 'client')
        self.treeview.expand_all()

    def removeFeederClient(self, feederState, state):
        for row in self.treemodel:
            if self.treemodel.get_value(row.iter, 1) == feederState:
                break
        for row in row.iterchildren():
            if self.treemodel.get_value(row.iter, 1) == state:
                break
        state, watcher = self.treemodel.get(row.iter, 1, 2)
        if watcher == self.selected:
            self.select(None)
        watcher.unwatch()
        self.treemodel.remove(row.iter)

    def setUIState(self, state):
        # will only be called when we have a widget tree
        BaseAdminGtkNode.setUIState(self, state)
        self.widget.show_all()
        for feeder in state.get('feeders'):
            self.addFeeder(state, feeder)
        sel = self.treeview.get_selection()
        if sel is not None:
            sel.select_iter(self.treemodel.get_iter_first())

    def haveWidgetTree(self):
        self.labels = {}
        self.widget = self.wtree.get_widget('feeders-widget')
        self.treeview = self.wtree.get_widget('treeview-feeders')
        self.treemodel = gtk.TreeStore(str, object, object, str)
        self.treeview.set_model(self.treemodel)
        col = gtk.TreeViewColumn('Feeder', gtk.CellRendererText(),
                                 text=0)
        self.treeview.append_column(col)
        sel = self.treeview.get_selection()
        sel.set_mode(gtk.SELECTION_SINGLE)

        def sel_changed(sel):
            model, i = sel.get_selected()
            if not i:
                sel.select_iter(model.get_iter_first())
                return
            self.select(i and model.get_value(i, 2))
            # don't show the feeder client stuff for a feeder
            if model.get_value(i, 3) == 'feeder':
                self.setFeederClientName(model.get_value(i, 1), None)
                self._table_feedclient.hide()
            else:
                parent = model.get_value(model.iter_parent(i), 1)
                self.setFeederName(parent, parent.get('feederName'))
                self._table_feedclient.show()

        sel.connect('changed', sel_changed)

        def set_label(name):
            self.labels[name] = self.wtree.get_widget('label-' + name)
            # zeroes out all value labels
            self.labels[name].set_text('')

        for name in ('feeder-name', 'eater-name',
                     'bytes-read-current', 'buffers-dropped-current',
                     'connected-since', 'connection-time',
                     'disconnected-since', 'disconnection-time',
                     'bytes-read-total', 'buffers-dropped-total',
                     'connections-total', 'last-activity'):
            set_label(name)

        self._table_connected = self.wtree.get_widget(
            'table-current-connected')
        self._table_disconnected = self.wtree.get_widget(
            'table-current-disconnected')
        self._table_feedclient = self.wtree.get_widget('table-feedclient')
        self._table_connected.hide()
        self._table_disconnected.hide()
        self._table_feedclient.hide()
        self.wtree.get_widget('box-right').hide()

        return self.widget
