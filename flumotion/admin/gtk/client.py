# -*- Mode: Python -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# flumotion/admin/gtk/client.py: GTK+-based admin client
#
# Flumotion - a streaming media server
# Copyright (C) 2004 Fluendo (www.fluendo.com)

# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
# See "LICENSE.GPL" in the source distribution for more information.

# This program is also licensed under the Flumotion license.
# See "LICENSE.Flumotion" in the source distribution for more information.

import os
import sys

import gobject
import gst
from gtk import gdk
import gtk
import gtk.glade
from twisted.internet import reactor

from flumotion import config
from flumotion.admin.admin import AdminModel
from flumotion.manager import admin   # Register types
from flumotion.common import errors
from flumotion.utils import log
from flumotion.utils.gstutils import gsignal
from flumotion.admin.gtk import dialogs

COL_PIXBUF = 0
COL_TEXT   = 1

RESPONSE_FETCH = 0

class PropertyChangeDialog(gtk.Dialog):
    gsignal('set', str, str, object)
    gsignal('get', str, str)
    
    def __init__(self, name, parent):
        title = "Change element property on '%s'" % name
        gtk.Dialog.__init__(self, title, parent,
                            gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT)
        self.connect('response', self.response_cb)
        self.add_button('Close', gtk.RESPONSE_CLOSE)
        self.add_button('Set', gtk.RESPONSE_APPLY)
        self.add_button('Fetch current', RESPONSE_FETCH)

        hbox = gtk.HBox()
        hbox.show()
        
        label = gtk.Label('Element')
        label.show()
        hbox.pack_start(label, False, False)
        self.element_combo = gtk.ComboBox()
        self.element_entry = gtk.Entry()
        self.element_entry.show()
        hbox.pack_start(self.element_entry, False, False)

        label = gtk.Label('Property')
        label.show()
        hbox.pack_start(label, False, False)
        self.property_entry = gtk.Entry()
        self.property_entry.show()
        hbox.pack_start(self.property_entry, False, False)
        
        label = gtk.Label('Value')
        label.show()
        hbox.pack_start(label, False, False)
        self.value_entry = gtk.Entry()
        self.value_entry.show()
        hbox.pack_start(self.value_entry, False, False)

        self.vbox.pack_start(hbox)
        
    def response_cb(self, dialog, response):
        if response == gtk.RESPONSE_APPLY:
            self.emit('set', self.element_entry.get_text(),
                      self.property_entry.get_text(),
                      self.value_entry.get_text())
        elif response == RESPONSE_FETCH:
            self.emit('get', self.element_entry.get_text(),
                      self.property_entry.get_text())
        elif response == gtk.RESPONSE_CLOSE:
            dialog.destroy()

    def update_value_entry(self, value):
        self.value_entry.set_text(str(value))
    
gobject.type_register(PropertyChangeDialog)

class Window(log.Loggable):
    '''
    Creates the GtkWindow for the user interface.
    Also connects to the manager on the given host and port.
    '''

    logCategory = 'adminview'

    def __init__(self, host, port):
        self.gladedir = config.gladedir
        self.imagedir = config.imagedir
        self.connect(host, port)
        self.create_ui()
        self.current_component = None # the component we're showing UI for
        
    # default Errback
    def _defaultErrback(self, failure):
        self.warning('Errback: unhandled failure: %s' % failure.getErrorMessage())
        return failure

    def create_ui(self):
        wtree = gtk.glade.XML(os.path.join(self.gladedir, 'admin.glade'))
        self.window = wtree.get_widget('main_window')
        iconfile = os.path.join(self.imagedir, 'fluendo.png')
        gtk.window_set_default_icon_from_file(iconfile)
        self.window.set_icon_from_file(iconfile)
        
        self.hpaned = wtree.get_widget('hpaned')
        self.window.connect('delete-event', self.close)
        self.window.show_all()
        
        self.component_model = gtk.ListStore(gdk.Pixbuf, str)
        self.component_view = wtree.get_widget('component_view')
        self.component_view.connect('row-activated',
                                    self.component_view_row_activated_cb)
        self.component_view.set_model(self.component_model)
        self.component_view.set_headers_visible(True)

        col = gtk.TreeViewColumn(' ', gtk.CellRendererPixbuf(),
                                 pixbuf=COL_PIXBUF)
        self.component_view.append_column(col)

        col = gtk.TreeViewColumn('Component', gtk.CellRendererText(),
                                 text=COL_TEXT)
        self.component_view.append_column(col)
        
        wtree.signal_autoconnect(self)

        self.icon_playing = self.window.render_icon(gtk.STOCK_YES,
                                                    gtk.ICON_SIZE_MENU)
        self.icon_stopped = self.window.render_icon(gtk.STOCK_NO,
                                                    gtk.ICON_SIZE_MENU)

    def get_selected_component_name(self):
        selection = self.component_view.get_selection()
        sel = selection.get_selected()
        if not sel:
            return
        model, iter = sel
        if not iter:
            return
        
        return model.get(iter, COL_TEXT)[0]

    def show_component(self, name, data):
        """
        Show the user interface for this component.
        Searches data for the GUIClass global, then instantiates an object
        from that class, and calls the render() method.

        @param name: name to give to the instantiated object.
        @param data: the python code to load.
        """
        sub = None
        instance = None
        if data:
            namespace = {}
            exec (data, globals(), namespace)
            klass = namespace.get('GUIClass')

            if klass:
                # instantiate the GUIClass, giving ourself as the first argument
                # FIXME: we cheat by giving the view as second for now,
                # but let's decide for either view or model
                instance = klass(name, self.admin, self)
                sub = instance.render()

        old = self.hpaned.get_child2()
        self.hpaned.remove(old)
        
        if not sub:
            sub = gtk.Label('%s does not have a UI yet' % name)
        else:
            parent = sub.get_parent()
            if parent:
                parent.remove(sub)
                
            
        self.hpaned.add2(sub)
        sub.show()

        self.current_component = instance
        

    def error_dialog(self, message, parent=None, response=True):
        """
        Show an error message dialog.

        @param message the message to display.
        @param parent the gtk.Window parent window.
        @param response whether the error dialog should go away after response.

        returns: the error dialog.
        """
        if not parent:
            parent = self.window
        d = gtk.MessageDialog(parent, gtk.DIALOG_MODAL, gtk.MESSAGE_ERROR,
            gtk.BUTTONS_OK, message)
        if response:
            d.connect("response", lambda self, response: self.destroy())
        d.show_all()
        return d

    ### glade callbacks

    def component_view_row_activated_cb(self, *args):
        name = self.get_selected_component_name()

        if not name:
            self.warning('Select a component')
            return

        def cb_gotUI(dir):
            self.debug("Got the UI, lives in %s" % dir)
            self.uidir = dir
            path = os.path.join(dir, 'gtk.py')
            handle = open(path, "r")
            data = handle.read()
            handle.close()
            self.show_component(name, data)
            
        # FIXME: old code, looking for replacement with bundles
        #cb = self.admin.getUIEntry(name)
        #cb.addCallback(cb_gotUI)
        d = self.admin.getUI(name, 'gtk')
        d.addCallback(cb_gotUI)

    def admin_connected_cb(self, admin):
        self.update_components()

    def admin_connection_refused_later(self, host, port):
        message = "Connection to manager on %s:%d was refused." % (host, port)
        d = self.error_dialog(message, response = False)
        d.connect('response', self.close)

    def admin_connection_refused_cb(self, admin, host, port):
        log.debug('adminclient', "handling connection-refused")
        reactor.callLater(0, self.admin_connection_refused_later, host, port)
        log.debug('adminclient', "handled connection-refused")

    def admin_ui_state_changed_cb(self, admin, name, state):
        current = self.get_selected_component_name()
        if current != name:
            return

        comp = self.current_component
        if comp:
            comp.setUIState(state)
        
    def admin_update_cb(self, admin):
        self.update_components()

    ### functions

    def connect(self, host, port):
        'connect to manager on given host and port.  Called by __init__'
        self.admin = AdminModel()
        self.admin.connect('connected', self.admin_connected_cb)
        self.admin.connect('connection-refused',
                           self.admin_connection_refused_cb, host, port)
        self.admin.connect('ui-state-changed', self.admin_ui_state_changed_cb)
        self.admin.connect('update', self.admin_update_cb)
        reactor.connectTCP(host, port, self.admin.clientFactory)
        
    def update_components(self):
        model = self.component_model
        model.clear()

        # get a dictionary of components
        components = self.admin.get_components()
        names = components.keys()
        names.sort()

        # FIXME: this part should have abstractions so you can get state
        # of components from admin instead of directly
        for name in names:
            component = components[name]
            iter = model.append()
            if component.state == gst.STATE_PLAYING:
                pixbuf = self.icon_playing
            else:
                pixbuf = self.icon_stopped
            model.set(iter, COL_PIXBUF, pixbuf)
            model.set(iter, COL_TEXT, component.name)

    def close(self, *args):
        reactor.stop()

    # menubar/toolbar callbacks
    def file_open_cb(self, button):
        raise NotImplementedError
    
    def file_save_cb(self, button):
        raise NotImplementedError

    def file_quit_cb(self, button):
        self.close()

    def edit_properties_cb(self, button):
        raise NotImplementedError

    def debug_reload_manager_cb(self, button):
        deferred = self.admin.reloadManager()

    def debug_reload_component_cb(self, button):
        name = self.get_selected_component_name()
        if name:
            deferred = self.admin.reloadComponent(name)

    def debug_reload_all_cb(self, button):
        # FIXME: move all of the reloads over to this dialog
        def _stop(dialog):
            dialog.stop()
            dialog.destroy()

        def _syntaxErrback(failure, self, progress):
            failure.trap(errors.ReloadSyntaxError)
            _stop(progress)
            self.error_dialog("Could not reload component:\n%s." % failure.getErrorMessage())
            return None
            
        def _callLater(admin, dialog):
            deferred = self.admin.reload()
            deferred.addCallback(lambda result: _stop(dialog))
            deferred.addErrback(_syntaxErrback, self, dialog)
            deferred.addErrback(self._defaultErrback)
        
        dialog = dialogs.ProgressDialog("Reloading ...", "Reloading client code", self.window)
        l = lambda admin, text, dialog: dialog.message("Reloading %s code" % text)
        self.admin.connect('reloading', l, dialog)
        dialog.start()
        reactor.callLater(0.2, _callLater, self.admin, dialog)
 
    def debug_modify_cb(self, button):
        name = self.get_selected_component_name()
        if not name:
            self.warning('Select a component')
            return

        def propertyErrback(failure):
            failure.trap(errors.PropertyError)
            self.error_dialog("%s." % failure.getErrorMessage())
            return None

        def after_getProperty(value, dialog):
            print 'got value', value
            dialog.update_value_entry(value)
            
        def dialog_set_cb(dialog, element, property, value):
            cb = self.admin.setProperty(name, element, property, value)
            cb.addErrback(propertyErrback)
        def dialog_get_cb(dialog, element, property):
            cb = self.admin.getProperty(name, element, property)
            cb.addCallback(after_getProperty, dialog)
            cb.addErrback(propertyErrback)
        
        d = PropertyChangeDialog(name, self.window)
        d.connect('get', dialog_get_cb)
        d.connect('set', dialog_set_cb)
        d.run()

    def help_about_cb(self, button):
        raise NotImplementedError
    
def main(args):
    # FIXME: use real options
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
