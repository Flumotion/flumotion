# -*- Mode: Python -*-
# vi:si:et:sw=4:sts=4:ts=4

# Flumotion - a video streaming server
# Copyright (C) 2004 Fluendo
# 
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
# 
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.

import os
import sys

import gobject
import gst
import gtk
import gtk.glade

from twisted.internet import gtk2reactor
gtk2reactor.install()

from twisted.internet import reactor
from twisted.spread import pb

from flumotion.twisted import pbutil
from flumotion.server import admin   # Register types
from flumotion.utils import log

class AdminInterface(pb.Referenceable, gobject.GObject):
    __gsignals__ = {
        'connected' : (gobject.SIGNAL_RUN_FIRST, gobject.TYPE_NONE, ()),
        'update'    : (gobject.SIGNAL_RUN_FIRST, gobject.TYPE_NONE, (object,))
    }

    def __init__(self):
        self.__gobject_init__()
        self.factory = pb.PBClientFactory()
        cb = self.factory.login(pbutil.Username('admin'), client=self)
        cb.addCallback(self.gotPerspective)

    def gotPerspective(self, perspective):
        self.remote = perspective

    def msg(self, *args):
        print args
        #log.msg('adminclient', *args)
        
    def remote_log(self, category, type, message):
        print category, type, message
        
    def remote_componentAdded(self, component):
        self.msg( 'componentAdded %s' % component.getName())
        self.clients.append(component)
        self.emit('update', self.clients)
        
    def remote_componentRemoved(self, component):
        self.msg( 'componentRemoved %s' % component.getName())
        self.clients.remove(component)
        self.emit('update', self.clients)
        
    def remote_initial(self, clients):
        self.clients = clients
        self.emit('connected')

    def remote_shutdown(self):
        print 'shutdown'

    def setState(self, component, element, property, value):
        if not self.remote:
            print 'Warning, no remote'
            return
        self.remote.callRemote('setState', component, element, property, value)

    def getState(self, component, element, property):
        return self.remote.callRemote('getState', component, element, property)
    
gobject.type_register(AdminInterface)

class Window:
    def __init__(self, gladedir, host, port):
        self.gladedir = gladedir
        self.connect(host, port)
        self.create_ui()
        
    def create_ui(self):
        self.wtree = gtk.glade.XML(os.path.join(self.gladedir, 'admin.glade'))
        self.window = self.wtree.get_widget('main_window')
        self.button_change = self.wtree.get_widget('button_change')
        self.button_change.connect('clicked', self.button_change_cb)
        
        self.window.connect('delete-event', self.close)
        self.window.show_all()
        self.component_view = self.wtree.get_widget('component_view')
        self.component_model = gtk.ListStore(str, int, str, str)
        self.component_view.set_model(self.component_model)

        col = gtk.TreeViewColumn('Name', gtk.CellRendererText(), text=0)
        self.component_view.append_column(col)
        
        col = gtk.TreeViewColumn('Pid', gtk.CellRendererText(), text=1)
        self.component_view.append_column(col)

        col = gtk.TreeViewColumn('Status', gtk.CellRendererText(), text=2)
        self.component_view.append_column(col)

        col = gtk.TreeViewColumn('IP', gtk.CellRendererText(), text=3)
        self.component_view.append_column(col)

        self.wtree.signal_autoconnect(self)

    def button_change_cb(self, button):
        selection = self.component_view.get_selection()
        sel = selection.get_selected()
        if not sel:
            return
        model, iter = sel
        name = model.get(iter, 0)[0]

        dialog = gtk.Dialog("My dialog",
                            self.window,
                            gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT)

        hbox = gtk.HBox()
        
        label = gtk.Label('Element')
        hbox.pack_start(label, False, False)
        element_entry = gtk.Entry()
        hbox.pack_start(element_entry, False, False)

        label = gtk.Label('Property')
        hbox.pack_start(label, False, False)
        property_entry = gtk.Entry()
        hbox.pack_start(property_entry, False, False)
        
        label = gtk.Label('Value')
        hbox.pack_start(label, False, False)
        value_entry = gtk.Entry()
        hbox.pack_start(value_entry, False, False)

        hbox.show_all()
        
        RESPONSE_FETCH = 0
        
        dialog.vbox.pack_start(hbox)
        dialog.add_button('Close', gtk.RESPONSE_CLOSE)
        dialog.add_button('Set', gtk.RESPONSE_APPLY)
        dialog.add_button('Fetch current', RESPONSE_FETCH)

        def response_cb(dialog, response):
            if response == gtk.RESPONSE_APPLY:
                element = element_entry.get_text()
                property = property_entry.get_text()
                value = value_entry.get_text()

                print name, element, property, value
                self.admin.setState(name, element, property, value)
            elif response == RESPONSE_FETCH:
                element = element_entry.get_text()
                property = property_entry.get_text()
                def after_getState(value):
                    print 'got value', value
                    value_entry.set_text(str(value))
                cb = self.admin.getState(name, element, property)
                cb.addCallback(after_getState)
            elif response == gtk.RESPONSE_CLOSE:
                dialog.destroy()
                
        dialog.connect('response', response_cb)
        dialog.show_all()
        
    def connected_cb(self, admin):
        self.update(admin.clients)

    def update_cb(self, admin, clients):
        self.update(clients)

    def update(self, orig_clients):
        model = self.component_model
        model.clear()

        # Make a copy
        clients = orig_clients[:]
        clients.sort()
        
        for client in clients:
            iter = model.append()
            model.set(iter, 0, client.name)
            model.set(iter, 1, client.options['pid'])
            model.set(iter, 2, gst.element_state_get_name(client.state))
            model.set(iter, 3, client.options['ip'])

    def connect(self, host, port):
        self.admin = AdminInterface()
        self.admin.connect('connected', self.connected_cb)
        self.admin.connect('update', self.update_cb)
        reactor.connectTCP(host, port, self.admin.factory)
        
    def menu_quit_cb(self, button):
        self.close()

    def close(self, *args):
        reactor.stop()

def main(args, gladedir='../../data/ui'):
    log.enableLogging()
    host = args[1]
    port = int(args[2])
    win = Window(gladedir, host, port)
    reactor.run()
    
if __name__ == '__main__':
    sys.exit(main(sys.argv))
