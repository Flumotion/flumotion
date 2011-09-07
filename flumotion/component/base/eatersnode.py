# -*- Mode: Python; test-case-name: flumotion.test.test_feedcomponent010 -*-
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

"""
Eaters tab in the component UI
"""

import gettext
import os
import time

import gtk

from flumotion.common import format as formatting
from flumotion.common.i18n import gettexter
from flumotion.component.base.baseadminnode import BaseAdminGtkNode
from flumotion.component.base.statewatcher import StateWatcher

_ = gettext.gettext
__version__ = "$Rev$"
T_ = gettexter()


class EatersAdminGtkNode(BaseAdminGtkNode):
    gladeFile = os.path.join('flumotion', 'component', 'base', 'eaters.glade')

    def __init__(self, state, admin):
        BaseAdminGtkNode.__init__(self, state, admin, title=_("Eaters"))
        # tree model is a model of id, uiState, StateWatcher
        # tree model contains eaters
        self.treemodel = None
        self.treeview = None
        self._selected = None # the watcher of the currently selected row
        self.labels = {}
        self._lastConnect = 0
        self._lastDisconnect = 0

    def select(self, watcher):
        if self._selected:
            self._selected.hide()
        if watcher:
            self._selected = watcher
            self._selected.show()
        else:
            self._selected = None

    def _setEaterFD(self, state, value):
        if value is None:
            self._table_connected.hide()
            self._table_disconnected.show()
        else:
            self._table_disconnected.hide()
            self._table_connected.show()

    def _setEaterName(self, state, value):
        self.labels['eater-name'].set_markup(_('Eater <b>%s</b>') % value)

    def _setEaterBytesReadCurrent(self, state, value):
        txt = value and (formatting.formatStorage(value) + _('Byte')) or ''
        self.labels['bytes-read-current'].set_text(txt)
        self._updateConnectionTime()
        self._updateDisconnectionTime()

    def _setEaterConnectionItem(self, state, key, value):
        if key == 'feed-id':
            self.labels['eating-from'].set_text(str(value))
        # timestamps
        elif key == 'count-timestamp-discont':
            self.labels['timestamp-discont-count-current'].set_text(str(value))
            if value > 0:
                self._expander_discont_current.show()
        elif key == 'time-timestamp-discont':
            text = formatting.formatTimeStamp(time.localtime(value))
            self.labels['timestamp-discont-time-current'].set_text(text)
            if value is not None:
                self._vbox_timestamp_discont_current.show()
        elif key == 'last-timestamp-discont':
            text = formatting.formatTime(value, fractional=9)
            self.labels['timestamp-discont-last-current'].set_text(text)
            if value > 0.0:
                self._vbox_timestamp_discont_current.show()
        elif key == 'total-timestamp-discont':
            text = formatting.formatTime(value, fractional=9)
            self.labels['timestamp-discont-total-current'].set_text(text)
            if value > 0.0:
                self._vbox_timestamp_discont_current.show()
        elif key == 'timestamp-timestamp-discont':
            if value is None:
                return
            text = formatting.formatTime(value, fractional=9)
            self.labels['timestamp-discont-timestamp-current'].set_text(text)
        # offsets
        elif key == 'count-offset-discont':
            self.labels['offset-discont-count-current'].set_text(str(value))
            if value > 0:
                self._expander_discont_current.show()
        elif key == 'time-offset-discont':
            text = formatting.formatTimeStamp(time.localtime(value))
            self.labels['offset-discont-time-current'].set_text(text)
            if value is not None:
                self._vbox_offset_discont_current.show()
        elif key == 'last-offset-discont':
            text = _("%d units") % value
            self.labels['offset-discont-last-current'].set_text(text)
            if value > 0:
                self._vbox_offset_discont_current.show()
        elif key == 'total-offset-discont':
            text = _("%d units") % value
            self.labels['offset-discont-total-current'].set_text(text)
            if value > 0:
                self._vbox_offset_discont_current.show()
        elif key == 'offset-offset-discont':
            if value is None:
                return
            text = _("%d units") % value
            self.labels['offset-discont-offset-current'].set_text(text)
            if value > 0:
                self._vbox_offset_discont_current.show()

    def _setEaterCountTimestampDiscont(self, state, value):
        if value is None:
            return
        self.labels['timestamp-discont-count-total'].set_text(str(value))
        if value > 0.0:
            self._expander_discont_total.show()

    def _setEaterTotalTimestampDiscont(self, state, value):
        if value is None:
            return
        text = formatting.formatTime(value, fractional=9)
        self.labels['timestamp-discont-total'].set_text(text)
        if value > 0.0:
            self._vbox_timestamp_discont_total.show()

    def _setEaterCountOffsetDiscont(self, state, value):
        if value is None:
            return
        self.labels['offset-discont-count-total'].set_text(str(value))
        if value != 0:
            self._expander_discont_total.show()

    def _setEaterTotalOffsetDiscont(self, state, value):
        if value is None:
            return
        text = _("%d units") % value
        self.labels['offset-discont-total'].set_text(text)
        if value != 0:
            self._vbox_offset_discont_total.show()

    def _setEaterLastConnect(self, state, value):
        if value:
            text = formatting.formatTimeStamp(time.localtime(value))
            self.labels['connected-since'].set_text(text)
            self._table_connected.show()
            self._table_disconnected.hide()
            self._lastConnect = value
            self._updateConnectionTime()

    def _setEaterTotalConnections(self, state, value):
        self.labels['connections-total'].set_text(str(value))

    # when we initially get the uiState, connection is an already set dict
    # this makes sure we handle getting that dict initially

    def _setEaterConnection(self, state, value):
        # can be called with None value due to StateWatcher
        if value is None:
            return
        for k, v in value.items():
            self._setEaterConnectionItem(state, k, v)

    # FIXME: add a timeout to update this ?

    def _updateConnectionTime(self):
        if self._lastConnect:
            text = formatting.formatTime(time.time() - self._lastConnect)
            self.labels['connection-time'].set_text(text)

    # FIXME: add a timeout to update this ?

    def _updateDisconnectionTime(self):
        if self._lastDisconnect:
            text = formatting.formatTime(time.time() - self._lastDisconnect)
            self.labels['disconnection-time'].set_text(text)

    def addEater(self, uiState, state):
        """
        @param uiState: the component's uiState
        @param state:   the eater's uiState
        """
        eaterId = state.get('eater-alias')
        i = self.treemodel.append(None)
        self.treemodel.set(i, 0, eaterId, 1, state)
        w = StateWatcher(state,
            {
                'fd': self._setEaterFD,
                'eater-alias': self._setEaterName,
                'last-connect': self._setEaterLastConnect,
                'count-timestamp-discont': self._setEaterCountTimestampDiscont,
                'total-timestamp-discont': self._setEaterTotalTimestampDiscont,
                'count-offset-discont': self._setEaterCountOffsetDiscont,
                'total-offset-discont': self._setEaterTotalOffsetDiscont,
                'total-connections': self._setEaterTotalConnections,
                # need to have a setter for connection to be able to show
                # it initially
                'connection': self._setEaterConnection,
            },
            {},
            {},
            setitemers={'connection': self._setEaterConnectionItem,
            },
            delitemers={})
        self.treemodel.set(i, 2, w)

    def setUIState(self, state):
        # will only be called when we have a widget tree
        BaseAdminGtkNode.setUIState(self, state)
        #self.widget.show_all()
        for eater in state.get('eaters'):
            self.addEater(state, eater)

    def haveWidgetTree(self):
        self.labels = {}
        self.widget = self.wtree.get_widget('eaters-widget')
        self.treeview = self.wtree.get_widget('treeview-eaters')
        # tree model is a model of id, uiState, StateWatcher
        self.treemodel = gtk.TreeStore(str, object, object)
        self.treeview.set_model(self.treemodel)
        col = gtk.TreeViewColumn('Eater', gtk.CellRendererText(),
                                 text=0)
        self.treeview.append_column(col)
        sel = self.treeview.get_selection()
        sel.set_mode(gtk.SELECTION_SINGLE)

        # get to know and set labels

        def set_label(name):
            self.labels[name] = self.wtree.get_widget('label-' + name)
            if self.labels[name] is None:
                raise KeyError(name)
            # zeroes out all value labels
            self.labels[name].set_text('')

        for name in (
            'eater-name', 'connected-since', 'connection-time',
            'eating-from', 'timestamp-discont-timestamp-current',
            'offset-discont-offset-current',
            'timestamp-discont-count-current', 'offset-discont-count-current',
            'timestamp-discont-total-current', 'offset-discont-total-current',
            'timestamp-discont-last-current', 'offset-discont-last-current',
            'timestamp-discont-time-current', 'offset-discont-time-current',
            'timestamp-discont-count-total', 'offset-discont-count-total',
            'timestamp-discont-total', 'offset-discont-total',
            'connections-total',
            ):
            set_label(name)

        # handle selection changes on the tree widget

        def sel_changed(sel):
            model, i = sel.get_selected()
            self.select(i and model.get_value(i, 2))
            self.wtree.get_widget('box-right').show()

        sel.connect('changed', sel_changed)

        # manage visibility of parts of the widget
        self._table_connected = self.wtree.get_widget(
            'table-current-connected')
        self._table_disconnected = self.wtree.get_widget(
            'table-current-disconnected')
        self._table_eater = self.wtree.get_widget('table-eater')
        self._expander_discont_current = self.wtree.get_widget(
            'expander-discont-current')
        self._vbox_timestamp_discont_current = self.wtree.get_widget(
            'vbox-timestamp-discont-current')
        self._vbox_offset_discont_current = self.wtree.get_widget(
            'vbox-offset-discont-current')

        self._expander_discont_total = self.wtree.get_widget(
            'expander-discont-total')
        self._vbox_timestamp_discont_total = self.wtree.get_widget(
            'vbox-timestamp-discont-total')
        self._vbox_offset_discont_total = self.wtree.get_widget(
            'vbox-offset-discont-total')
        #
        # show the tree view always
        self.wtree.get_widget('scrolledwindow').show_all()

        # hide the specifics of the eater
        self._expander_discont_current.hide()
        self._table_connected.hide()
        self._table_disconnected.hide()
        self._expander_discont_total.hide()

        # show the right box only when an eater is selected
        self.wtree.get_widget('box-right').hide()

        # FIXME: do not show all;
        # hide bytes fed and buffers dropped until something is selected
        # see #575
        self.widget.show()
        return self.widget
