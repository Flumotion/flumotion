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
# Foundation, Inc., 59 Temple Street #330, Boston, MA 02111-1307, USA.

import os
import sys

import gst
from gtk import gdk
import gtk
import gtk.glade
from twisted.internet import reactor

from flumotion import config
from flumotion.gui.admininterface import AdminInterface
from flumotion.server import admin   # Register types
from flumotion.twisted import errors
from flumotion.utils import log

COL_PIXBUF = 0
COL_TEXT   = 1

class Window(log.Loggable):
    '''
    Creates the GtkWindow for the user interface.
    Also connects to the controller on the given host and port.
    '''
    def __init__(self, host, port):
        self.gladedir = config.gladedir
        self.imagedir = config.imagedir
        self.connect(host, port)
        self.create_ui()
        
    def create_ui(self):
        self.wtree = gtk.glade.XML(os.path.join(self.gladedir, 'admin.glade'))
        self.window = self.wtree.get_widget('main_window')
        iconfile = os.path.join(self.imagedir, 'fluendo.png')
        gtk.window_set_default_icon_from_file(iconfile)
        self.window.set_icon_from_file(iconfile)
        
        self.hpaned = self.wtree.get_widget('hpaned')
        self.window.connect('delete-event', self.close)
        self.window.show_all()
        
        self.component_model = gtk.ListStore(gdk.Pixbuf, str)
        self.component_view = self.wtree.get_widget('component_view')
        self.component_view.connect('row-activated', self.component_view_row_activated_cb)
        self.component_view.set_model(self.component_model)
        self.component_view.set_headers_visible(True)

        col = gtk.TreeViewColumn(' ', gtk.CellRendererPixbuf(), pixbuf=COL_PIXBUF)
        self.component_view.append_column(col)

        col = gtk.TreeViewColumn('Component', gtk.CellRendererText(), text=COL_TEXT)
        self.component_view.append_column(col)
        
        self.wtree.signal_autoconnect(self)

    def get_selected_component(self):
        selection = self.component_view.get_selection()
        sel = selection.get_selected()
        if not sel:
            return
        model, iter = sel
        return model.get(iter, COL_TEXT)[0]

    def show_component(self, name, data):
        sub = None
        if data:
            namespace = {}
            exec (data, globals(), namespace)
            klass = namespace.get('GUIClass')

            if klass:
                instance = klass(name, self.admin)
                sub = instance.render()

        old = self.hpaned.get_child2()
        self.hpaned.remove(old)
        
        if not sub:
            sub = gtk.Label('%s does not have a UI yet' % name)
            
        self.hpaned.add2(sub)
        sub.show()
        
    def component_view_row_activated_cb(self, *args):
        name = self.get_selected_component()

        if not name:
            self.warning('Select a component')
            return

        def cb_gotUI(data):
            self.show_component(name, data)
            
        cb = self.admin.getUIEntry(name)
        cb.addCallback(cb_gotUI)

    def _button_change_cb(self, button):
        name = self.get_selected_component()
        if not name:
            self.warning('Select a component')
            return

        dialog = gtk.Dialog("Change element property on '%s'" % name,
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
            def propertyErrback(failure, window):
                failure.trap(errors.PropertyError)
                window.error_dialog("%s." % failure.getErrorMessage())
                return None

            if response == gtk.RESPONSE_APPLY:
                element = element_entry.get_text()
                property = property_entry.get_text()
                value = value_entry.get_text()

                print "FIXME: applying ", name, element, property, value
                cb = self.admin.setProperty(name, element, property, value)
                cb.addErrback(propertyErrback, self)
            elif response == RESPONSE_FETCH:
                element = element_entry.get_text()
                property = property_entry.get_text()
                
                def after_getProperty(value):
                    print 'got value', value
                    value_entry.set_text(str(value))
                    
                cb = self.admin.getProperty(name, element, property)
                cb.addCallback(after_getProperty)
                cb.addErrback(propertyErrback, self)
                msg = "Controller error: %s" % failure.getErrorMessage()
                cb.addErrback(lambda failure: self.error_dialog(msg))
            elif response == gtk.RESPONSE_CLOSE:
                dialog.destroy()
                
        dialog.connect('response', response_cb)
        dialog.show_all()
        
    def connected_cb(self, admin):
        self.update(admin.clients)

    def update_cb(self, admin, clients):
        self.update(clients)

    # reload code
    def _button_reload_cb(self, button):
        cb = self.admin.reload()
 
    def error_dialog(self, message, parent = None):
        """
        Show an error message dialog.
        """
        if not parent:
            parent = self.window
        d = gtk.MessageDialog(parent, gtk.DIALOG_MODAL, gtk.MESSAGE_ERROR,
            gtk.BUTTONS_OK, message)
        d.connect("response", lambda self, response: self.destroy())
        d.show_all()


    def connection_refused_later(self, host, port):
        d = gtk.MessageDialog(self.window, gtk.DIALOG_MODAL, gtk.MESSAGE_ERROR,
            gtk.BUTTONS_OK,
            "Connection to controller on %s:%d was refused." % (host, port))
        d.run()
        self.close()

    def connection_refused_cb(self, admin, host, port):
        log.debug('adminclient', "handling connection-refused")
        reactor.callLater(0, self.connection_refused_later, host, port)
        log.debug('adminclient', "handled connection-refused")

    def update(self, orig_clients):
        model = self.component_model
        model.clear()

        # Make a copy
        clients = orig_clients[:]
        clients.sort()
        
        for client in clients:
            iter = model.append()
            #model.set(iter, 0, client.name)
            model.set(iter, 1, client.name)
            #model.set(iter, 1, client.options['pid'])
            #model.set(iter, 2, gst.element_state_get_name(client.state))
            #model.set(iter, 3, client.options['ip'])

    def connect(self, host, port):
        'connect to controller on given host and port.  Called by __init__'
        self.admin = AdminInterface()
        self.admin.connect('connected', self.connected_cb)
        self.admin.connect('update', self.update_cb)
        self.admin.connect('connection-refused', self.connection_refused_cb, host, port)
        reactor.connectTCP(host, port, self.admin.factory)
        
    def menu_quit_cb(self, button):
        self.close()

    def close(self, *args):
        reactor.stop()

def main(args):
    try:
        host = args[1]
        port = int(args[2])
    except IndexError:
        print "Please specify a host and a port number"
        sys.exit(1)

    win = Window(host, port)
    reactor.run()
    
if __name__ == '__main__':
    sys.exit(main(sys.argv))
