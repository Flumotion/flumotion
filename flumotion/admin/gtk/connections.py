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

"""connection widgets and dialogs"""

import os
import gettext

import gobject
import gtk
from pango import ELLIPSIZE_MIDDLE, ELLIPSIZE_END

from flumotion.admin.connections import getRecentConnections, \
     hasRecentConnections
from flumotion.common.pygobject import gsignal, gproperty
from flumotion.ui.glade import GladeWidget, GladeWindow

__version__ = "$Rev$"
_ = gettext.gettext


def format_timestamp(stamp):
    return stamp.strftime('%x')


class Connections(GladeWidget):
    gladeFile = 'connections.glade'

    gsignal('have-connection', bool)
    gsignal('connection-activated', object)
    gsignal('connections-cleared')

    def __init__(self):
        GladeWidget.__init__(self)

        self.connections_model = gtk.TreeStore(str, str, str)
        host_column = gtk.TreeViewColumn('Host')
        manager_column = gtk.TreeViewColumn('Manager')
        timestamp_column = gtk.TreeViewColumn('Timestamp')
        
        self.connections_tree.set_model(self.connections_model)
        self.connections_tree.append_column(host_column)
        self.connections_tree.append_column(manager_column)
        self.connections_tree.append_column(timestamp_column)
        self.connections_tree.set_rules_hint(True)
        for i, c in enumerate([host_column, manager_column, timestamp_column]):
            c.set_resizable(True)
            cell_renderer = gtk.CellRendererText()
            c.pack_start(cell_renderer, True)
            c.set_expand(True)
            c.add_attribute(cell_renderer, 'text', i)
        c.set_sort_column_id(i) # Sort by last column above - timestamp

        self.connection_objects = getRecentConnections()
        self.connection_objects.sort(key=lambda c: c.timestamp, reverse=True)
        for ind, c in enumerate(self.connection_objects):
            print("Inserting row: host: %s, manager: %s, timestamp: %s" % (c.host, c.manager, c.timestamp))
            self.connections_model.insert(None, ind, (c.host, c.manager, c.timestamp.strftime('%Y-%m-%d %H:%M')))
            c.model_index = ind
            c.model_index_hash = '%s%s%s' % (c.host, c.manager, c.timestamp.strftime('%Y-%m-%d %H:%M'))
        

        self.connections_tree.set_search_equal_func(self._searchEqual)
        self.connections.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        self.connections_selection = self.connections_tree.get_selection()
        self.connections_selection.set_mode(gtk.SELECTION_SINGLE)
        self.connections.set_size_request(-1, 160)
        self._updateButtons()

    def _updateButtons(self):
        canClear = hasRecentConnections()
        self.button_clear.set_sensitive(canClear)
        self.button_clear_all.set_sensitive(canClear)
        if not canClear:
            self.emit('connections-cleared')

    def _searchEqual(self, model, column, key, iter):
        connection = model.get(iter, 0)[0]
        if key in connection:
            return False

        # True means doesn't match
        return True

    def _clear_all(self):
        for conn in self.connection_objects:
            os.unlink(conn.filename)
        self.connections_model.clear()
        self.connection_objects = []

    def _clear(self, conn):
        self.connection_objects.remove(conn)
        os.unlink(conn.filename)

    # Public API

    def grab_focus(self):
        if len(self.connections):
            self.connections_selection.select_path("0")
        self.connections.grab_focus()


    def get_connection_for_row(self, row):
        connections = filter(lambda c: c.model_index_hash == ''.join(row),
            self.connection_objects)
        return connections[0] # First connection which matches...

    def get_selected(self):
        print ("Called get_selected connection!")
        model, tIter = self.connections_selection.get_selected()
        row = model.get(tIter, 0, 1, 2)
        return self.get_connection_for_row(row)

    def update(self, connection):
        os.utime(connection.filename, None)

    # Callbacks

    def on_button_clear_clicked(self, button):
        tModel, tIter = self.connections_selection.get_selected()
        if tIter:
            row = tModel.get(tIter, 0, 1, 2)
            conn = self.get_connection_for_row(row)
            tModel.remove(tIter)  # Get rid of the row
            self._clear(conn) 
        self._updateButtons()

    def on_button_clear_all_clicked(self, button):
        self._clear_all()
        self._updateButtons()

    def _on_connections_row_activated(self, *args):
        selection = self.get_selected()
        self.emit('connection-activated', selection)

    def _on_connections_selection_changed(self, connections, connection):
        self.emit('have-connection', bool(connection))

gobject.type_register(Connections)


class ConnectionsDialog(GladeWindow):
    gladeFile = 'connection-dialog.glade'

    gsignal('have-connection', object)

    def on_connection_activated(self, widget, state):
        self.emit('have-connection', state)

    def on_cancel(self, button):
        self.destroy()

    def on_ok(self, button):
        self.emit('have-connection',
                  self.widgets['connections'].get_selected())

    def on_delete_event(self, dialog, event):
        self.destroy()

    def on_connections_cleared(self, widget):
        self.button_ok.set_sensitive(False)

gobject.type_register(ConnectionsDialog)


class OpenConnection(GladeWidget):
    gladeFile = 'open-connection.glade'

    gproperty(bool, 'can-activate', 'If the state of the widget is complete',
              False)

    def __init__(self):
        self.host_entry = self.port_entry = self.ssl_check = None
        GladeWidget.__init__(self)
        self.set_property('can-activate', False)
        self.on_entries_changed()
        self.connect('grab-focus', self.on_grab_focus)

    def on_grab_focus(self, *args):
        self.host_entry.grab_focus()
        return True

    def on_entries_changed(self, *args):
        old_can_act = self.get_property('can-activate')
        can_act = self.host_entry.get_text() and self.port_entry.get_text()
        # fixme: validate input
        if old_can_act != can_act:
            self.set_property('can-activate', can_act)

    def on_ssl_check_toggled(self, button):
        if button.get_active():
            self.port_entry.set_text('7531')
        else:
            self.port_entry.set_text('8642')

    def set_state(self, state):
        self.host_entry.set_text(state['host'])
        self.port_entry.set_text(str(state['port']))
        self.ssl_check.set_active(not state['use_insecure'])

    def get_state(self):
        return {'host': self.host_entry.get_text(),
                'port': int(self.port_entry.get_text()),
                'use_insecure': not self.ssl_check.get_active()}
gobject.type_register(OpenConnection)


class Authenticate(GladeWidget):
    gladeFile = 'authenticate.glade'

    gproperty(bool, 'can-activate', 'If the state of the widget is complete',
              False)

    # pychecker sacrifices
    auth_method_combo = None
    user_entry = None
    passwd_entry = None

    def __init__(self, *args):
        GladeWidget.__init__(self, *args)
        self.set_property('can-activate', False)
        self.user_entry.connect('activate',
                                lambda *x: self.passwd_entry.grab_focus())
        self.connect('grab-focus', self.on_grab_focus)

    def on_passwd_entry_activate(self, entry):
        toplevel = self.get_toplevel()
        toplevel.wizard.next()

    def on_grab_focus(self, *args):
        self.user_entry.grab_focus()

    def on_entries_changed(self, *args):
        can_act = self.user_entry.get_text() and self.passwd_entry.get_text()
        self.set_property('can-activate', can_act)

    def set_state(self, state):
        if state and 'user' in state:
            self.user_entry.set_text(state['user'])
            self.passwd_entry.set_text(state['passwd'])
        else:
            self.user_entry.set_text('')
            self.passwd_entry.set_text('')

    def get_state(self):
        return {'user': self.user_entry.get_text(),
                'passwd': self.passwd_entry.get_text()}
gobject.type_register(Authenticate)
