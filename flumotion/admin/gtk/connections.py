# -*- Mode: Python -*-
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
# Streaming Server license may use this file in accordance with th
# Flumotion Advanced Streaming Server Commercial License Agreement.
# See "LICENSE.Flumotion" in the source distribution for more information.

# Headers in this file shall remain intact.

"""connection widgets and dialogs"""

import os
import gettext

import gobject
import gtk
from kiwi.ui.objectlist import ObjectList, Column
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

    def __init__(self):
        GladeWidget.__init__(self)

        columns = [Column("host", title=_("Hostname"), searchable=True),
                   Column("timestamp", title=_("Last used"),
                          sorted=True,
                          order=gtk.SORT_DESCENDING,
                          format_func=format_timestamp),
                   ]
        self._connections = ObjectList(
            columns,
            objects=getRecentConnections(),
            mode=gtk.SELECTION_SINGLE)
        self._connections.connect(
            'row-activated',
            self._on_objectlist_row_activated)
        self._connections.connect(
            'selection-changed',
            self._on_objectlist_selection_changed)
        self._connections.set_size_request(-1, 160)
        self.page.pack_start(self._connections)
        self.page.reorder_child(self._connections, 0)
        self._connections.show()
        self._updateButtons()

    def _updateButtons(self):
        canClear = hasRecentConnections()
        self.button_clear.set_sensitive(canClear)
        self.button_clear_all.set_sensitive(canClear)

    def _clear_all(self):
        for conn in self._connections:
            os.unlink(conn.filename)
        self._connections.clear()

    def _clear(self, conn):
        self._connections.remove(conn)
        os.unlink(conn.filename)

    # Public API

    def grab_focus(self):
        if len(self._connections):
            self._connections.select(self._connections[0])
        self._connections.grab_focus()

    def get_selected(self):
        return self._connections.get_selected()

    def update(self, connection):
        os.utime(connection.filename, None)

    # Callbacks

    def on_button_clear_clicked(self, button):
        conn = self._connections.get_selected()
        if conn:
            self._clear(conn)
        self._updateButtons()

    def on_button_clear_all_clicked(self, button):
        self._clear_all()

    def _on_objectlist_row_activated(self, connections, connection):
        self.emit('connection-activated', connection)

    def _on_objectlist_selection_changed(self, connections, connection):
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
