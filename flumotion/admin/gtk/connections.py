# -*- Mode: Python; fill-column: 80 -*-
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
# Streaming Server license may use this file in accordance with th
# Flumotion Advanced Streaming Server Commercial License Agreement.
# See "LICENSE.Flumotion" in the source distribution for more information.

# Headers in this file shall remain intact.


import os
from xml.dom import minidom, Node

import gtk
import gtk.glade
import gobject

from flumotion.ui.glade import GladeWidget, GladeWindow
from flumotion.configure import configure
from flumotion.common.pygobject import gsignal, gproperty


def parse_connection(f):
    tree = minidom.parse(f)
    state = {}
    for n in [x for x in tree.documentElement.childNodes
                if x.nodeType != Node.TEXT_NODE
                   and x.nodeType != Node.COMMENT_NODE]:
        state[n.nodeName] = n.childNodes[0].wholeText
    state['port'] = int(state['port'])
    state['use_insecure'] = (state['use_insecure'] != '0')
    return state

        
class Connections(GladeWidget):
    glade_file = 'connections.glade'

    STR_COL = 0
    FILE_COL = 1
    STATE_COL = 2

    model = None
    gsignal('has-selection', bool)
    gsignal('connection-activated', object)

    treeview_connections = None

    def __init__(self):
        GladeWidget.__init__(self)
        v = self.treeview_connections

        c = gtk.TreeViewColumn('Host', gtk.CellRendererText(),
                               text=self.STR_COL)
        v.append_column(c)

        self._populate_liststore()
        v.set_model(self.model)

        # Bizarre. This doesn't work at all.
        #self.scrolledwindow1.set_property('can-focus', False)

        self.connect('grab-focus', self.on_grab_focus)

        s = self.treeview_connections.get_selection()
        s.set_mode(gtk.SELECTION_SINGLE)
        if self.model.get_iter_first():
            s.select_path((0,))
            self.emit('has-selection', True)
        else:
            self.emit('has-selection', False)

    def _populate_liststore(self):
        self.model = gtk.ListStore(str, str, object)
        try:
            # DSU, or as perl folks call it, a Schwartz Transform
            files = os.listdir(configure.registrydir)
            files = [os.path.join(configure.registrydir, f) for f in files]
            files = [(os.stat(f).st_mtime, f) for f in files
                                              if f.endswith('.connection')]
            files.sort()
            files.reverse()
            l = self.model
            for f in [x[1] for x in files]:
                try:
                    state = parse_connection(f)
                    i = l.append()
                    l.set_value(i, self.STR_COL,
                                '%s:%d/%s' % (state['host'], state['port'],
                                              state['manager']))
                    l.set_value(i, self.FILE_COL, f)
                    l.set_value(i, self.STATE_COL, state)
                except Exception, e:
                    print 'Error parsing %s: %r' % (f, e)
                    raise
        except OSError, e:
            print 'Error: %s: %s' % (e.strerror, e.filename)

    def _clear_iter(self, i):
        os.unlink(self.model.get_value(i, self.FILE_COL))
        self.model.remove(i)

    def get_recent_connections(self):
        'used to get connections to add to a menu'
        connections = []
        m = self.model
        i = m.get_iter_first()
        while i:
            connections.append(m.get_value(i, self.STATE_COL))
            i = m.iter_next(i)
        return connections
        
    def on_grab_focus(self, *args):
        v = self.treeview_connections
        model, i = v.get_selection().get_selected()
        if model:
            v.set_cursor(model.get_path(i), None, False)
            self.treeview_connections.grab_focus()
        return True

    def on_clear_all(self, *args):
        m = self.model
        i = m.get_iter_first()
        while i:
            self._clear_iter(i)
            i = m.get_iter_first()
        self.emit('has-selection', False)

    def on_clear(self, *args):
        s = self.treeview_connections.get_selection()
        model, i = s.get_selected()
        if i:
            self._clear_iter(i)
            if model.get_iter_first():
                s.select_path((0,))
            else:
                self.emit('has-selection', False)

    def on_row_activated(self, *args):
        self.emit('connection-activated', self.get_selected())

    def get_selected(self):
        s = self.treeview_connections.get_selection()
        model, i = s.get_selected()
        if i:
            return model.get_value(i, self.STATE_COL)
        else:
            return None
gobject.type_register(Connections)


class ConnectionsDialog(GladeWindow):
    glade_file = 'connection-dialog.glade'

    gsignal('have-connection', object)

    def on_has_selection(self, widget, has_selection):
        self.widgets['button_ok'].set_sensitive(has_selection)

    def on_connection_activated(self, widget, state):
        self.emit('have-connection', state)

    def on_cancel(self, widget):
        self.destroy()

    def on_ok(self, x):
        self.emit('have-connection',
                  self.widgets['connections'].get_selected())
gobject.type_register(ConnectionsDialog)


class OpenConnection(GladeWidget):
    glade_file = 'open-connection.glade'

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
