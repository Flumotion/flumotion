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

from flumotion.configure import configure
from flumotion.admin.gtk import wizard


# A wizard run when the user first starts flumotion.


# personal note: these things duplicate to a large extent the code in
# flumotion.wizard.steps. A bit irritating to find that out after
# hacking on it for a bit.


# Page classes (see wizard.py for details)

class Initial(wizard.WizardStep):
    name = 'initial'
    title = 'Connect to Flumotion manager'
    text = 'Flumotion Admin needs to connect to a Flumotion manager.\nChoose' \
           + ' an option from the list and click "Forward" to begin.'
    connect_to_existing = None

    def on_next(self, state):
        radio_buttons = self.connect_to_existing.get_group()

        for i in range(len(radio_buttons)):
            if radio_buttons[i].get_active():
                return radio_buttons[i].get_name()
        raise AssertionError
    

class ConnectToExisting(wizard.WizardStep):
    name='connect_to_existing'
    title='Host information'
    text = 'Please enter the address where the manager is running.'
    host_entry = port_entry = ssl_check = None

    def setup(self, state):
        self.on_entries_changed()
        self.host_entry.grab_focus()

    def on_entries_changed(self, *args):
        if self.host_entry.get_text() and self.port_entry.get_text():
            self.button_next.set_sensitive(True)
        else:
            self.button_next.set_sensitive(False)

    def on_ssl_check_toggled(self, button):
        if button.get_active():
            self.port_entry.set_text('7531')
        else:
            self.port_entry.set_text('8642')

    def on_next(self, state):
        host = self.host_entry.get_text()
        port = self.port_entry.get_text()
        ssl_check = self.ssl_check.get_active()

        # fixme: check these values here
        state['host'] = host
        state['port'] = int(port)
        state['use_insecure'] = not ssl_check

        return 'authenticate'


class Authenticate(wizard.WizardStep):
    name = 'authenticate'
    title = 'Authentication'
    text = 'Please select among the following authentication methods.'
    auth_method_combo = user_entry = passwd_entry = None

    def setup(self, state):
        if not 'auth_method' in state:
            self.auth_method_combo.set_active(0)
        self.on_entries_changed()
        self.user_entry.grab_focus()
        self.user_entry.connect('activate',
                                lambda *x: self.passwd_entry.grab_focus())

    def on_entries_changed(self, *args):
        if self.user_entry.get_text() and self.passwd_entry.get_text():
            self.button_next.set_sensitive(True)
        else:
            self.button_next.set_sensitive(False)

    def on_next(self, state):
        user = self.user_entry.get_text()
        passwd = self.passwd_entry.get_text()

        # fixme: check these values here
        state['user'] = user
        state['passwd'] = passwd

        return '*finished*'


def parse_connection(f):
    print 'Parsing XML file: %s' % os.path.basename(f)
    tree = minidom.parse(f)
    state = {}
    for n in [x for x in tree.documentElement.childNodes
                if x.nodeType != Node.TEXT_NODE
                   and x.nodeType != Node.COMMENT_NODE]:
        state[n.nodeName] = n.childNodes[0].wholeText
    state['port'] = int(state['port'])
    state['use_insecure'] = (state['use_insecure'] != '0')
    state['manager'] = 'fixme'
    return state

MANAGER_COL = 0
HOST_STR_COL = 1
FILE_COL = 2
STATE_COL = 3

def _populate_liststore(l):
    try:
        # DSU, or as perl folks call it, a Schwartz Transform
        files = os.listdir(configure.registrydir)
        files = [os.path.join(configure.registrydir, f) for f in files]
        files = [(os.stat(f).st_mtime, f) for f in files
                                          if f.endswith('.connection')]
        files.sort()
        for f in [x[1] for x in files]:
            try:
                state = parse_connection(f)
                i = l.append()
                l.set_value(i, HOST_STR_COL,
                            '%s:%d' % (state['host'], state['port']))
                l.set_value(i, MANAGER_COL, state['manager'])
                l.set_value(i, FILE_COL, f)
                l.set_value(i, STATE_COL, state)
            except Exception, e:
                print 'Error parsing %s: %r' % (f, e)
                raise
    except OSError, e:
        print 'Error: %s: %s' % (e.strerror, e.filename)

def _clear_iter(model, i):
    os.unlink(model.get_value(i,FILE_COL))
    model.remove(i)

class LoadConnection(wizard.WizardStep):
    name = 'load_connection'
    title = 'Load connection'
    text = 'Please choose a connection from the box below.'
    treeview_connections = None

    def setup(self, state):
        l = gtk.ListStore(str, str, str, object)
        v = self.treeview_connections

        c = gtk.TreeViewColumn('Manager', gtk.CellRendererText(),
                               text=MANAGER_COL)

        v.append_column(c)
        c = gtk.TreeViewColumn('Host', gtk.CellRendererText(),
                               text=HOST_STR_COL)
        v.append_column(c)

        v.set_model(l)
        _populate_liststore(l)
        s = self.treeview_connections.get_selection()
        s.set_mode(gtk.SELECTION_SINGLE)
        if l.get_iter_first():
            s.select_path((0,))
        else:
            self.button_next.set_sensitive(False)

    def on_clear_all(self, *args):
        m = self.treeview_connections.get_model()
        i = m.get_iter_first()
        while i:
            _clear_iter(m, i)
            i = m.get_iter_first()
        self.button_next.set_sensitive(False)

    def on_clear(self, *args):
        s = self.treeview_connections.get_selection()
        model, i = s.get_selected()
        if i:
            _clear_iter(model, i)
            if model.get_iter_first():
                s.select_path((0,))
            else:
                self.button_next.set_sensitive(False)
        
    def on_next(self, state):
        s = self.treeview_connections.get_selection()
        model, i = s.get_selected()
        state.update(model.get_value(i, STATE_COL))
        state['file'] = model.get_value(i, FILE_COL)
        return '*finished*'


class Greeter:
    wiz = None
    def __init__(self):
        self.wiz = wizard.Wizard('greeter', 'initial',
                                 Initial, ConnectToExisting, Authenticate,
                                 LoadConnection)
    def run(self):
        self.wiz.show()
        return self.wiz.run()

    def destroy(self):
        return self.wiz.destroy()

    def hide(self):
        return self.wiz.hide()

    def show(self):
        return self.wiz.show()

    def set_sensitive(self, is_sensitive):
        return self.wiz.set_sensitive(is_sensitive)

