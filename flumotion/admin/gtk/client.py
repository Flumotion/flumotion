# -*- Mode: Python -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# flumotion/admin/gtk/client.py: GTK+-based admin client
#
# Flumotion - a streaming media server
# Copyright (C) 2004 Fluendo, S.L. (www.fluendo.com). All rights reserved.

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

import os

import gobject
import gst
from gtk import gdk
import gtk
import gtk.glade
from twisted.internet import reactor

from flumotion.admin.admin import AdminModel
from flumotion.admin.gtk import dialogs
from flumotion.configure import configure
from flumotion.common import errors, log
from flumotion.manager import admin # Register types
from flumotion.utils.gstutils import gsignal

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

class Window(log.Loggable, gobject.GObject):
    '''
    Creates the GtkWindow for the user interface.
    Also connects to the manager on the given host and port.
    '''

    logCategory = 'adminview'
    gsignal('connected')
    
    def __init__(self, host, port, transport, username, password):
        self.__gobject_init__()
        
        self.admin = None
        self._connectToManager(host, port, transport, username, password)

        self.create_ui()
        self.current_component = None # the component we're showing UI for
        self._disconnected_dialog = None # set to a dialog if we're
                                            # disconnected

    ### connection to manager, called from constructor
    def _connectToManager(self, host, port, transport, username, password):
        'connect to manager using given options.  Called by __init__'
        
        # FIXME: someone else should create the model and then set us as a
        # view on it
        self.admin = AdminModel(username, password)
        self.admin.connect('connected', self.admin_connected_cb)
        self.admin.connect('disconnected', self.admin_disconnected_cb)
        self.admin.connect('connection-refused',
                           self.admin_connection_refused_cb, host, port)
        self.admin.connect('ui-state-changed', self.admin_ui_state_changed_cb)
        self.admin.connect('component-property-changed',
            self.property_changed_cb)
        self.admin.connect('update', self.admin_update_cb)
        self.admin.addView(self)

        if transport == "ssl":
            from twisted.internet import ssl
            self.info('Connecting to manager %s:%d with SSL' % (host, port))
            reactor.connectSSL(host, port, self.admin.clientFactory,
                               ssl.ClientContextFactory())
        elif transport == "tcp":
            self.info('Connecting to manager %s:%d with TCP' % (host, port))
            reactor.connectTCP(host, port, self.admin.clientFactory)
        else:
            self.error("Unknown transport protocol %s" % transport)
        
    
    # default Errback
    def _defaultErrback(self, failure):
        self.warning('Errback: unhandled failure: %s' % failure.getErrorMessage())
        return failure

    def create_ui(self):
        wtree = gtk.glade.XML(os.path.join(configure.gladedir, 'admin.glade'))
        self.window = wtree.get_widget('main_window')
        iconfile = os.path.join(configure.imagedir, 'fluendo.png')
        gtk.window_set_default_icon_from_file(iconfile)
        self.window.set_icon_from_file(iconfile)
        
        self.hpaned = wtree.get_widget('hpaned')
        self.window.connect('delete-event', self.close)
        
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

    # FIXME: this method uses a file and a methodname as entries
    # FIXME: do we want to switch to imports instead so the whole file
    # is available in its namespace ?
    def show_component(self, name, methodName, filepath, data):
        """
        Show the user interface for this component.
        Searches data for the given methodName global,
        then instantiates an object from that class,
        and calls the render() method.

        @param name: name to give to the instantiated object.
        @param data: the python code to load.
        """
        # methodName has historically been GUIClass
        sub = None
        instance = None

        if data:
            # we create a temporary module that we import from so code
            # inside the module can trust its full namespace to be local
            import imp
            tempmod = imp.new_module('tempmod')
            try:
                exec data in tempmod.__dict__
                #exec(data, globals(), tempmod.__dict__)
            except SyntaxError, e:
                # the syntax error can happen in the entry file, or any import
                where = "<entry file>"
                if e.filename:
                    where = e.filename
                msg = "Syntax Error at %s:%d while executing %s" % (
                    where, e.lineno, filepath)
                self.warning(msg)
                raise errors.EntrySyntaxError(msg)
            except NameError, e:
                # the syntax error can happen in the entry file, or any import
                msg = "NameError while executing %s: %s" % (filepath,
                    " ".join(e.args))
                self.warning(msg)
                raise errors.EntrySyntaxError(msg)
            except ImportError, e:
                msg = "ImportError while executing %s: %s" % (filepath,
                    " ".join(e.args))
                self.warning(msg)
                raise errors.EntrySyntaxError(msg)

            # put it in sys.modules so we can import it
            import sys
            sys.modules['tempmod'] = tempmod

            # import it
            import tempmod

            # check if we have the method
            if not hasattr(tempmod, methodName):
                self.warning('method %s not found in file %s' % (
                    methodName, filepath))
                raise #FIXME: something appropriate
            klass = getattr(tempmod, methodName)
 
            # clean up temporary module
            #del sys.modules['tempmod']
            # FIXME: don't delete tempmod just yet, or the class doesn't
            # actually work ! clean it up when the view is changed
            #del tempmod

            # instantiate the GUIClass, giving ourself as the first argument
            # FIXME: we cheat by giving the view as second for now,
            # but let's decide for either view or model
            instance = klass(name, self.admin, self)
            self.debug("Created entry instance %r" % instance)
            instance.setup()
            nodes = instance.getNodes()

            # FIXME: we'd want to embed in a notebook with tabs
            firstNode = nodes[nodes.keys()[0]]

            # put "loading" widget in
            old = self.hpaned.get_child2()
            self.hpaned.remove(old)
            label = gtk.Label('Loading UI for %s ...' % name)
            self.hpaned.add(label)
            
            # trigger render of first node
            d = firstNode.render()
            d.addCallback(self._firstNodeRenderCallback, instance)

    def _firstNodeRenderCallback(self, widget, gtkAdminInstance):
        # used by show_component
        self.debug("Got sub widget %r" % widget)

        old = self.hpaned.get_child2()
        self.hpaned.remove(old)
        
        if not widget:
            self.warning(".render() did not return an object")
            widget = gtk.Label('%s does not have a UI yet' % name)
        else:
            parent = widget.get_parent()
            if parent:
                parent.remove(widget)
            
        self.hpaned.add2(widget)
        widget.show()

        self.current_component = gtkAdminInstance

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

    ### IAdminView interface methods: FIXME: create interface somewhere
    def componentCall(self, componentName, methodName, *args, **kwargs):
        # FIXME: for now, we only allow calls to go through that have
        # their UI currently displayed.  In the future, maybe we want
        # to create all UI's at startup regardless and allow all messages
        # to be processed, since they're here now anyway   
        self.debug("componentCall received for %s.%s ..." % (
            componentName, methodName))
        name = self.get_selected_component_name()
        if not name:
            self.debug("... but no component selected")
            return
        if componentName != name:
            self.debug("... but component is not displayed")
            return
        
        localMethodName = "component_%s" % methodName
        if not hasattr(self.current_component, localMethodName):
            self.debug("... but does not have method %s" % localMethodName)
            self.warning("Component %s does not implement %s" % localMethodName)
            return
        self.debug("... and executing")
        method = getattr(self.current_component, localMethodName)

        # call the method, catching all sorts of stuff
        try:
            result = method(*args, **kwargs)
        except TypeError:
            msg = "component method %s did not accept %s and %s" % (
                methodName, args, kwargs)
            self.debug(msg)
            raise errors.RemoteRunError(msg)
        self.debug("component: returning result: %r to caller" % result)
        return result

    ### glade callbacks
    def component_view_row_activated_cb(self, *args):
        name = self.get_selected_component_name()

        if not name:
            self.warning('Select a component')
            return

        def gotEntryCallback(result):
            entryPath, filename, methodName = result
            filepath = os.path.join(entryPath, filename)
            self.debug("Got the UI, lives in %s" % filepath)
            # FIXME: this is a silent assumption that the glade file
            # lives in the same directory as the entry point
            self.uidir = os.path.split(filepath)[0]
            handle = open(filepath, "r")
            data = handle.read()
            handle.close()
            # FIXME: is name (of component) needed ?
            self.debug("showing admin UI for component")
            self.show_component(name, methodName, filepath, data)

        def gotEntryNoBundleErrback(failure):
            failure.trap(errors.NoBundleError)
            # no ui, clear; FIXME: do this nicer
            old = self.hpaned.get_child2()
            self.hpaned.remove(old)
            sub = gtk.Label('%s does not have a UI yet' % name)
            self.hpaned.add2(sub)
            sub.show()
             
        d = self.admin.getEntry(name, 'admin/gtk')
        d.addCallback(gotEntryCallback)
        d.addErrback(gotEntryNoBundleErrback)

    def admin_connected_cb(self, admin):
        if self._disconnected_dialog:
            self._disconnected_dialog.destroy()
            self._disconnected_dialog = None

        self.update_components()
        self.emit('connected')

    def admin_disconnected_cb(self, admin):
        message = "Lost connection to manager, reconnecting ..."
        d = gtk.MessageDialog(self.window, gtk.DIALOG_DESTROY_WITH_PARENT,
            gtk.MESSAGE_WARNING, gtk.BUTTONS_NONE, message)
        # FIXME: move this somewhere
        RESPONSE_REFRESH = 1
        d.add_button(gtk.STOCK_REFRESH, RESPONSE_REFRESH)
        d.add_button(gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL)
        d.connect("response", self._dialog_disconnected_response_cb)
        d.show_all()
        self._disconnected_dialog = d

    def _dialog_disconnected_response_cb(self, dialog, id):
        if id == gtk.RESPONSE_CANCEL:
            # FIXME: notify admin of cancel
            dialog.destroy()
            return
        elif id == 1:
            self.admin.reconnect()
        
    def admin_connection_refused_later(self, host, port):
        message = "Connection to manager on %s:%d was refused." % (host, port)
        d = self.error_dialog(message, response = False)
        d.connect('response', self.close)

    def admin_connection_refused_cb(self, admin, host, port):
        log.debug('adminclient', "handling connection-refused")
        reactor.callLater(0, self.admin_connection_refused_later, host, port)
        log.debug('adminclient', "handled connection-refused")

    def admin_ui_state_changed_cb(self, admin, name, state):
        # called when the admin UI for that component has changed
        current = self.get_selected_component_name()
        if current != name:
            return

        comp = self.current_component
        if comp:
            comp.setUIState(state)

    def property_changed_cb(self, admin, componentName, propertyName, value):
        # called when a property for that component has changed
        current = self.get_selected_component_name()
        if current != componentName:
            return

        comp = self.current_component
        if comp:
            comp.propertyChanged(propertyName, value)
         
    def admin_update_cb(self, admin):
        self.update_components()

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

    def _logConfig(self, configation):
        import pprint
        import cStringIO
        fd = cStringIO.StringIO()
        pprint.pprint(configation, fd)
        fd.seek(0)
        self.debug('Configuration=%s' % fd.read())
        
    def runWizard(self):
        from flumotion.wizard import wizard
        def _wizard_finished_cb(wizard, configuration):
            wizard.hide()
            self._logConfig(configuration)
            self.admin.loadConfiguration(configuration)
            self.show()

        workers = self.admin.getWorkers()
        if not workers:
            self.error_dialog('Need at least one worker connected to run the wizard')
            return
        
        wiz = wizard.Wizard(self.admin)
        wiz.connect('finished', _wizard_finished_cb)
        wiz.load_steps()
        wiz.run(True, workers, False)

        return wiz

    # menubar/toolbar callbacksw
    def file_new_cb(self, button):
        self.runWizard()

    def file_open_cb(self, button):
        dialog = gtk.FileChooserDialog("Open..", self.window,
                                       gtk.FILE_CHOOSER_ACTION_OPEN,
                                       (gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL,
                                        gtk.STOCK_OPEN, gtk.RESPONSE_OK))
        dialog.set_default_response(gtk.RESPONSE_OK)

        directory = os.path.join(os.environ['HOME'], '.flumotion')
        if os.path.exists(directory):
            dialog.set_current_folder(directory)
             
        response = dialog.run()
        if response == gtk.RESPONSE_OK:
            filename = dialog.get_filename()
        elif response == gtk.RESPONSE_CANCEL:
            dialog.destroy()
            return
        
        dialog.hide()
        configuration = open(filename).read()
        self.admin.loadConfiguration(configuration)
        dialog.destroy()
    
    def file_save_cb(self, button):
        dialog = gtk.FileChooserDialog("Save as..", self.window,
                                       gtk.FILE_CHOOSER_ACTION_SAVE,
                                       (gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL,
                                        gtk.STOCK_SAVE, gtk.RESPONSE_OK))
        dialog.set_default_response(gtk.RESPONSE_OK)

        directory = os.path.join(os.environ['HOME'], '.flumotion')
        if os.path.exists(directory):
            dialog.set_current_folder(directory)

        response = dialog.run()
        if response == gtk.RESPONSE_OK:
            filename = dialog.get_filename()
        elif response == gtk.RESPONSE_CANCEL:
            dialog.destroy()
            return
        
        dialog.hide()

        fd = open(filename, 'w')
        fd.write(configuration)
        dialog.destroy()

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
            self.debug('got value %r' % value)
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

    def debug_start_shell_cb(self, button):
        import code
        code.interact(local=locals())

    def help_about_cb(self, button):
        dialog = gtk.Dialog('About Flumotion', self.window,
                            gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT,
                            (gtk.STOCK_CLOSE, gtk.RESPONSE_CLOSE))
        dialog.set_has_separator(False)
        dialog.set_resizable(False)
        dialog.set_border_width(12)
        dialog.vbox.set_spacing(6)
        
        image = gtk.Image()
        dialog.vbox.pack_start(image)
        image.set_from_file(os.path.join(configure.imagedir, 'fluendo.png'))
        image.show()
        
        version = gtk.Label('<span size="xx-large"><b>Flumotion %s</b></span>' % configure.version)
        version.set_selectable(True)
        dialog.vbox.pack_start(version)
        version.set_use_markup(True)
        version.show()

        text = 'Flumotion is a streaming video server\n\n(C) 2004 Fluendo S.L.'
        authors = ('Johan Dahlin &lt;johan@fluendo.com&gt;',
                   'Thomas V. Stichele &lt;thomas@fluendo.com&gt;',
                   'Wim Taymans &lt;wim@fluendo.com&gt;')
        text += '\n\n<small>Authors:\n'
        for author in authors:
            text += '  %s\n' % author
        text += '</small>'
        info = gtk.Label(text)
        dialog.vbox.pack_start(info)
        info.set_use_markup(True)
        info.set_selectable(True)
        info.set_justify(gtk.JUSTIFY_FILL)
        info.set_line_wrap(True)
        info.show()

        dialog.show()
        dialog.run()
        dialog.destroy()

    on_tool_open_clicked = file_open_cb
    on_tool_save_clicked = file_save_cb
    on_tool_quit_clicked = file_quit_cb

    def on_tool_clean_clicked(self, button):
        self.admin.cleanComponents()
        
    def show(self):
        # XXX: Use show()
        self.window.show_all()
        
gobject.type_register(Window)

