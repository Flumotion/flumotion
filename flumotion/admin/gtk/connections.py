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

from flumotion.configure import configure
from flumotion.common.pygobject import gsignal


class GladeWidget(gtk.VBox):
    glade_file = None

    def __init__(self):
        gtk.VBox.__init__(self)
        wtree = gtk.glade.XML(os.path.join(configure.gladedir,
                                           self.glade_file))
        win = None
        for widget in wtree.get_widget_prefix(''):
            wname = widget.get_name()
            if isinstance(widget, gtk.Window):
                assert win == None
                win = widget
                continue
            
            if hasattr(self, wname) and getattr(self, wname):
                raise AssertionError (
                    "There is already an attribute called %s in %r" %
                    (wname, self))
            setattr(self, wname, widget)

        assert win != None
        w = win.get_child()
        win.remove(w)
        self.add(w)
        win.destroy()
        wtree.signal_autoconnect(self)
gobject.type_register(GladeWidget)


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

        
class Connections(GladeWidget):
    glade_file = 'connections.glade'

    MANAGER_COL = 0
    HOST_STR_COL = 1
    FILE_COL = 2
    STATE_COL = 3

    model = None
    gsignal('has-selection', bool)

    treeview_connections = None

    def __init__(self):
        GladeWidget.__init__(self)
        print 'totally initializing dude'
        v = self.treeview_connections

        c = gtk.TreeViewColumn('Manager', gtk.CellRendererText(),
                               text=self.MANAGER_COL)

        v.append_column(c)
        c = gtk.TreeViewColumn('Host', gtk.CellRendererText(),
                               text=self.HOST_STR_COL)
        v.append_column(c)

        self._populate_liststore()
        v.set_model(self.model)

        s = self.treeview_connections.get_selection()
        s.set_mode(gtk.SELECTION_SINGLE)
        if self.model.get_iter_first():
            s.select_path((0,))
            self.emit('has-selection', True)
        else:
            self.emit('has-selection', False)
        
    def _populate_liststore(self):
        self.model = gtk.ListStore(str, str, str, object)
        try:
            # DSU, or as perl folks call it, a Schwartz Transform
            files = os.listdir(configure.registrydir)
            files = [os.path.join(configure.registrydir, f) for f in files]
            files = [(os.stat(f).st_mtime, f) for f in files
                                              if f.endswith('.connection')]
            files.sort()
            l = self.model
            for f in [x[1] for x in files]:
                try:
                    state = parse_connection(f)
                    i = l.append()
                    l.set_value(i, self.HOST_STR_COL,
                                '%s:%d' % (state['host'], state['port']))
                    l.set_value(i, self.MANAGER_COL, state['manager'])
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

    def get_selected(self):
        s = self.treeview_connections.get_selection()
        model, i = s.get_selected()
        if i:
            return model.get_value(i, self.STATE_COL)
        else:
            return None
gobject.type_register(Connections)
