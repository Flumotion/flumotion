# -*- Mode: Python -*-
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
# Streaming Server license may use this file in accordance with the
# Flumotion Advanced Streaming Server Commercial License Agreement.
# See "LICENSE.Flumotion" in the source distribution for more information.

# Headers in this file shall remain intact.

import os
import md5

import gobject
from gtk import gdk
import gtk
import gtk.glade
from twisted.internet import reactor

from flumotion.admin.admin import AdminModel
from flumotion.admin.gtk import dialogs, parts, connections
from flumotion.configure import configure
from flumotion.common import errors, log, worker, planet
from flumotion.manager import admin # Register types
from flumotion.twisted import flavors

from flumotion.common.planet import moods
from flumotion.common.pygobject import gsignal

class Window(log.Loggable, gobject.GObject):
    '''
    Creates the GtkWindow for the user interface.
    Also connects to the manager on the given host and port.
    '''

    __implements__ = flavors.IStateListener,
    
    logCategory = 'adminview'
    gsignal('connected')
    
    def __init__(self, model):
        self.__gobject_init__()
        
        self.widgets = {}
        self.debug('creating UI')
        self._create_ui()

        self._append_recent_connections()

        self.current_component = None # the component we're showing UI for
        self.current_component_state = None
        self._disconnected_dialog = None # set to a dialog if we're
                                         # disconnected

        self._planetState = None
        self._components = None # name -> default flow + atmosphere

        self.debug('setting model')
        self.admin = None
        self.wizard = None
        self._setAdminModel(model)

    def _setAdminModel(self, model):
        'set the model to which we are a view/controller'
        # it's ok if we've already been connected
        if self.admin:
            self.debug('Connecting to new model %r' % model)
            if self.wizard:
                self.wizard.destroy()

        self.admin = model

        # window gets created after model connects initially, so check
        # here
        if self.admin.isConnected():
            self.admin_connected_cb(model)

        self.admin.connect('connected', self.admin_connected_cb)
        self.admin.connect('disconnected', self.admin_disconnected_cb)
        self.admin.connect('connection-refused',
                           self.admin_connection_refused_cb)
        self.admin.connect('ui-state-changed', self.admin_ui_state_changed_cb)
        self.admin.connect('component-property-changed',
            self.property_changed_cb)
        self.admin.connect('update', self.admin_update_cb)

        # set ourselves as a view for the admin model
        self.admin.addView(self)

    # default Errback
    def _defaultErrback(self, failure):
        self.warning('Errback: unhandled failure: %s' %
            failure.getErrorMessage())
        return failure

    def _create_ui(self):
        # returns the window
        # called from __init__
        wtree = gtk.glade.XML(os.path.join(configure.gladedir, 'admin.glade'))
        wtree.signal_autoconnect(self)

        for widget in wtree.get_widget_prefix(''):
            self.widgets[widget.get_name()] = widget
        widgets = self.widgets

        window = self.window = widgets['main_window']
        iconfile = os.path.join(configure.imagedir, 'fluendo.png')
        gtk.window_set_default_icon_from_file(iconfile)
        window.set_icon_from_file(iconfile)
        
        def set_icon(proc, size, name):
            f = os.path.join(configure.imagedir, '%dx%d' % (size,size), name)
            i = gtk.Image()
            i.set_from_file(f)
            proc(i)
        
        def make_menu_proc(m): # $%^& pychecker!
            return lambda f: m.set_property('image', f)
        def menu_set_icon(m, name):
            set_icon(make_menu_proc(m), 16, name)
        
        def tool_set_icon(m, name):
            set_icon(m.set_icon_widget, 24, name)

        iconfile = os.path.join(configure.imagedir, 'fluendo.png')
        gtk.window_set_default_icon_from_file(iconfile)

        menu_set_icon(widgets['menuitem_manage_run_wizard'], 'wizard.png')
        tool_set_icon(widgets['toolbutton_wizard'], 'wizard.png')
        menu_set_icon(widgets['menuitem_manage_start_component'], 'play.png')
        tool_set_icon(widgets['toolbutton_start_component'], 'play.png')
        menu_set_icon(widgets['menuitem_manage_stop_component'], 'pause.png')
        tool_set_icon(widgets['toolbutton_stop_component'], 'pause.png')

        self.hpaned = widgets['hpaned']
 
        window.connect('delete-event', self.close)

        self.components_view = parts.ComponentsView(widgets['component_view'])
        self.components_view.connect('has-selection', 
            self._components_view_has_selection_cb)
        self.components_view.connect('activated',
            self._components_view_activated_cb)
        self.statusbar = parts.AdminStatusbar(widgets['statusbar'])
        self._set_stop_start_component_sensitive()
        self.components_view.connect('notify::can-start-any',
                                     self.start_stop_notify_cb)
        self.components_view.connect('notify::can-stop-any',
                                     self.start_stop_notify_cb)
        self.start_stop_notify_cb()
        return window

    def open_connected_cb(self, model, ids):
        map(model.disconnect, ids)
        self.window.set_sensitive(True)
        self._setAdminModel(model)
        self._append_recent_connections()

    def open_refused_cb(self, model, host, port, use_insecure, ids):
        map(model.disconnect, ids)
        self.window.set_sensitive(True)
        print '\n\nconnection refused, try again'
        print 'FIXME: make a proper errbox'

    def on_open_connection(self, config):
        model = AdminModel(config['user'], config['passwd'])
        model.connectToHost(config['host'], config['port'],
                            config['use_insecure'])

        ids = []
        ids.append(model.connect('connected',
                                 self.open_connected_cb, ids))
        ids.append(model.connect('connection-refused',
                                 self.open_refused_cb, ids))
        self.window.set_sensitive(False)

    def on_recent_activate(self, widget, state):
        self.on_open_connection(state)

    def _append_recent_connections(self):
        menu = self.widgets['connection_menu'].get_submenu()

        # first clean any old entries
        kids = menu.get_children()
        while True:
            w = kids.pop()
            if w.get_name() == 'file_quit':
                break
            else:
                menu.remove(w)

        clist = connections.Connections().get_recent_connections()
        if len(clist) < 2:
            return

        def append(i):
            i.show()
            gtk.MenuShell.append(menu, i) # $%^&* pychecker
        def append_txt(c, n):
            s = '_%d: %s:%d/%s' % (n, c['host'], c['port'], c['manager'])
            i = gtk.MenuItem(s)
            i.connect('activate', self.on_recent_activate, c)
            append(i)
            
        append(gtk.SeparatorMenuItem())
        # the first one is the current one, don't show it
        map(append_txt, clist[1:], range(1,len(clist)))

    # UI helper functions
    def show_error_dialog(self, message, parent=None, close_on_response=True):
        if not parent:
            parent = self.window
        d = dialogs.ErrorDialog(message, parent, close_on_response)
        d.show_all()
        return d

    # FIXME(wingo): use common.bundleclient
    # FIXME: this method uses a file and a methodname as entries
    # FIXME: do we want to switch to imports instead so the whole file
    # is available in its namespace ?
    def show_component(self, state, methodName, filepath, data):
        """
        Show the user interface for this component.
        Searches data for the given methodName global,
        then instantiates an object from that class,
        and calls the render() method.

        @type  state: L{flumotion.common.planet.AdminComponentState}
        @param data:  the python code to load.
        """
        # methodName has historically been GUIClass
        instance = None

        name = state.get('name')
        self.statusbar.set('main', "Loading UI for %s ..." % name)
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
            instance = klass(state, self.admin, self)
            self.debug("Created entry instance %r" % instance)
            instance.setup()
            nodes = instance.getNodes()
            notebook = gtk.Notebook()
            nodeWidgets = {}

            self.statusbar.clear('main')
            # create pages for all nodes, and just show a loading label for
            # now
            for nodeName in nodes.keys():
                self.debug("Creating node for %s" % nodeName)
                label = gtk.Label('Loading UI for %s ...' % nodeName)
                table = gtk.Table(1, 1)
                table.add(label)
                nodeWidgets[nodeName] = table

                notebook.append_page(table, gtk.Label(nodeName))
                
            # put "loading" widget in
            old = self.hpaned.get_child2()
            self.hpaned.remove(old)
            self.hpaned.add2(notebook)
            notebook.show_all()

            # trigger node rendering
            # FIXME: might be better to do these one by one, in order,
            # so the status bar can show what happens
            for nodeName in nodes.keys():
                mid = self.statusbar.push('notebook',
                    "Loading tab %s for %s ..." % (nodeName, name))
                node = nodes[nodeName]
                d = node.render()
                d.addCallback(self._nodeRenderCallback, nodeName,
                    instance, nodeWidgets, mid)
                # FIXME: errback

    def _nodeRenderCallback(self, widget, nodeName, gtkAdminInstance,
        nodeWidgets, mid):
        # used by show_component
        self.debug("Got sub widget %r" % widget)
        self.statusbar.remove('notebook', mid)

        table = nodeWidgets[nodeName]
        for w in table.get_children():
            table.remove(w)
        
        if not widget:
            self.warning(".render() did not return an object")
            widget = gtk.Label('%s does not have a UI yet' % nodeName)
        else:
            parent = widget.get_parent()
            if parent:
                parent.remove(widget)
            
        table.add(widget)
        widget.show()

        self.current_component = gtkAdminInstance

    ### IAdminView interface methods: FIXME: create interface somewhere
    ## Confusingly enough, this procedure is called by remote objects to
    ## operate on the client ui. I think. It is *not* for calling
    ## methods on the remote components. Should fix this sometime.
    def componentCall(self, componentState, methodName, *args, **kwargs):
        # FIXME: for now, we only allow calls to go through that have
        # their UI currently displayed.  In the future, maybe we want
        # to create all UI's at startup regardless and allow all messages
        # to be processed, since they're here now anyway   
        self.debug("componentCall received for %r.%s ..." % (
            componentState, methodName))
        state = self.components_view.get_selected_state()
        if not state:
            self.debug("... but no component selected")
            return
        if componentState != state:
            self.debug("... but component is not displayed")
            return
        
        name = state.get('name')
        localMethodName = "component_%s" % methodName
        if not hasattr(self.current_component, localMethodName):
            self.debug("... but does not have method %s" % localMethodName)
            self.warning("Component view %s does not implement %s" % (
                name, localMethodName))
            return
        self.debug("... and executing")
        method = getattr(self.current_component, localMethodName)

        # call the method, catching all sorts of stuff
        try:
            result = method(*args, **kwargs)
        except TypeError:
            msg = "component method %s did not accept *a %s and **kwa %s" % (
                methodName, args, kwargs)
            self.debug(msg)
            raise errors.RemoteRunError(msg)
        self.debug("component: returning result: %r to caller" % result)
        return result

    def componentCallRemoteStatus(self, state, pre, post, fail,
                                  methodName, *args, **kwargs):
        if not state:
            state = self.components_view.get_selected_state()
            if not state:
                return
        name = state.get('name')
        if not name:
            return

        mid = None
        if pre:
            mid = self.statusbar.push('main', pre % name)
        d = self.admin.componentCallRemote(state, methodName, *args, **kwargs)

        def cb(result, self, mid):
            if mid:
                self.statusbar.remove('main', mid)
            if post:
                self.statusbar.push('main', post % name)
        def eb(failure, self, mid):
            if mid:
                self.statusbar.remove('main', mid)
            self.warning("Failed to execute %s on component %s: %s"
                         % (methodName, name, failure))
            if fail:
                self.statusbar.push('main', fail % name)
            
        d.addCallback(cb, self, mid)
        d.addErrback(eb, self, mid)
  
    def componentCallRemote(self, state, methodName, *args, **kwargs):
        self.componentCallRemoteStatus(None, None, None, None,
                                       methodName, *args, **kwargs)

    def setPlanetState(self, planetState):
        self.debug('parsing planetState %r' % planetState)
        self._planetState = planetState

        # clear and rebuild list of components that interests us
        self._components = {}

        planetState.addListener(self)

        a = planetState.get('atmosphere')
        a.addListener(self)

        for c in a.get('components'):
            name = c.get('name')
            self.debug('adding atmosphere component "%s"' % name)
            self._components[name] = c
            
        for f in planetState.get('flows'):
            if f.get('name') != 'default':
                continue
            f.addListener(self)
            for c in f.get('components'):
                name = c.get('name')
                self.debug('adding default flow component "%s"' % name)
                self._components[name] = c

        self.update_components()
 
    def stateSet(self, state, key, value):
        # called by model when state of something changes
        if not isinstance(state, planet.AdminComponentState):
            return

        if key == 'message':
            self.statusbar.set('main', value)
        elif key == 'mood':
            self._set_stop_start_component_sensitive()

    def stateAppend(self, state, key, value):
        if isinstance(state, worker.AdminWorkerHeavenState):
            if key == 'names':
                self.statusbar.set('main', 'Worker %s logged in.' % value)
        elif isinstance(state, planet.AdminFlowState):
            self.debug('flow state append: key %s, value %r' % (key, value))
            if state.get('name') != 'default':
                return
            if key == 'components':
                self._components[value.get('name')] = value
                # FIXME: would be nicer to do this incrementally instead
                self.update_components()
        elif isinstance(state, planet.AdminAtmosphereState):
            if key == 'components':
                self._components[value.get('name')] = value
                # FIXME: would be nicer to do this incrementally instead
                self.update_components()
        elif isinstance(state, planet.AdminPlanetState):
            if key == 'flows':
                if value.get('name') != 'default':
                    return
                self.debug('default flow started')
                value.addListener(self)
        else:
            self.warning('stateAppend on unknown object %r' % state)

    def stateRemove(self, state, key, value):
        if isinstance(state, worker.AdminWorkerHeavenState):
            if key == 'names':
                self.statusbar.set('main', 'Worker %s logged out.' % value)
        elif isinstance(state, planet.AdminFlowState):
            if state.get('name') != 'default':
                return
            if key == 'components':
                del self._components[value.get('name')]
                # FIXME: would be nicer to do this incrementally instead
                self.update_components()
        elif isinstance(state, planet.AdminAtmosphereState):
            if key == 'components':
                del self._components[value.get('name')]
                # FIXME: would be nicer to do this incrementally instead
                self.update_components()
        else:
            self.warning('stateAppend on unknown object %r' % state)

    ### admin model callbacks
    def admin_connected_cb(self, admin):
        self.info('Connected to manager')
        if self._disconnected_dialog:
            self._disconnected_dialog.destroy()
            self._disconnected_dialog = None

        self.window.set_title('%s:%d - Flumotion Administration'
                              % (admin.host, admin.port))

        self.emit('connected')

        # get initial info we need
        self.setPlanetState(self.admin.getPlanetState())

        if not self._components:
            self.debug('no components detected, running wizard')
    
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
        
    def admin_connection_refused_later(self, host, port, use_insecure):
        message = "Connection to manager on %s:%d (%s) was refused." \
                  % (host, port, use_insecure and 'http' or 'https')
        self.info(message)
        d = dialogs.ErrorDialog(message, self)
        d.show_all()
        d.connect('response', self.close)

    def admin_connection_refused_cb(self, admin, host, port, use_insecure):
        log.debug('adminclient', "handling connection-refused")
        reactor.callLater(0, self.admin_connection_refused_later,
                          host, port, use_insecure)
        log.debug('adminclient', "handled connection-refused")

    def admin_ui_state_changed_cb(self, admin, name, state):
        # called when the admin UI for that component has changed
        current = self.components_view.get_selected_name()
        if current != name:
            return

        comp = self.current_component
        if comp:
            comp.setUIState(state)

    # FIXME: deprecated
    def property_changed_cb(self, admin, componentName, propertyName, value):
        # called when a property for that component has changed
        current = self.components_view.get_selected_name()
        if current != componentName:
            return

        comp = self.current_component
        if comp:
            comp.propertyChanged(propertyName, value)
         
    def start_stop_notify_cb(self, *args):
        can_start = self.components_view.get_property('can-start-any')
        can_stop = self.components_view.get_property('can-stop-any')
        self.widgets['menuitem_manage_stop_all'].set_sensitive(can_stop)
        self.widgets['menuitem_manage_start_all'].set_sensitive(can_start)

    def admin_update_cb(self, admin):
        self.update_components()

    def update_components(self):
        self.components_view.update(self._components)

    def _set_stop_start_component_sensitive(self):
        state = self.current_component_state
        d = self.widgets
        can_start = bool(state
                         and moods.get(state.get('mood')).name == 'sleeping')
        d['menuitem_manage_start_component'].set_sensitive(can_start)
        d['toolbutton_start_component'].set_sensitive(can_start)

        moodname = state and moods.get(state.get('mood')).name
        can_stop = bool(moodname and moodname!='sleeping' and moodname!='lost')
        d['menuitem_manage_stop_component'].set_sensitive(can_stop)
        d['toolbutton_stop_component'].set_sensitive(can_stop)

    ### ui callbacks
    def _components_view_has_selection_cb(self, view, state):
        if self.current_component_state:
            self.current_component_state.removeListener(self)
        self.current_component_state = state
        if self.current_component_state:
            self.current_component_state.addListener(self)

        self._set_stop_start_component_sensitive()

        if not state:
            return

        name = state.get('name')

        def gotEntryCallback(result):
            entryPath, filename, methodName = result

            self.statusbar.set('main', 'Showing UI for %s' % name)

            filepath = os.path.join(entryPath, filename)
            self.debug("Got the UI, lives in %s" % filepath)
            # FIXME: this is a silent assumption that the glade file
            # lives in the same directory as the entry point
            self.uidir = os.path.split(filepath)[0]
            handle = open(filepath, "r")
            data = handle.read()
            handle.close()
            # FIXME: is name (of component) needed ?
            self.debug("showing admin UI for component %s" % name)
            # callLater to avoid any errors going to our errback
            reactor.callLater(0, self.show_component,
                state, methodName, filepath, data)

        def gotEntryNoBundleErrback(failure):
            failure.trap(errors.NoBundleError)

            self.statusbar.set('main', "No UI for component %s" % name)

            # no ui, clear; FIXME: do this nicer
            old = self.hpaned.get_child2()
            self.hpaned.remove(old)
            #sub = gtk.Label('%s does not have a UI yet' % name)
            sub = gtk.Label("")
            self.hpaned.add2(sub)
            sub.show()

        def gotEntrySleepingComponentErrback(failure):
            failure.trap(errors.SleepingComponentError)

            self.statusbar.set('main', "Component %s is still sleeping" % name)

            # no ui, clear; FIXME: do this nicer
            old = self.hpaned.get_child2()
            self.hpaned.remove(old)
            #sub = gtk.Label('%s does not have a UI yet' % name)
            sub = gtk.Label("")
            self.hpaned.add2(sub)
            sub.show()
                      
        self.statusbar.set('main', "Requesting UI for %s ..." % name)

        d = self.admin.getEntry(state, 'admin/gtk')
        d.addCallback(gotEntryCallback)
        d.addErrback(gotEntryNoBundleErrback)
        d.addErrback(gotEntrySleepingComponentErrback)

    def _components_view_activated_cb(self, view, state, action):
        self.debug('action %s on component %s' % (action, state.get('name')))
        method_name = '_component_' + action
        if hasattr(self, method_name):
            getattr(self, method_name)(state)
        else:
            self.warning("No method '%s' implemented" % method_name)

    ### glade callbacks
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
        if self.wizard:
            self.wizard.present()
            return

        from flumotion.wizard import wizard

        def _wizard_finished_cb(wizard, configuration):
            wizard.destroy()
            self._logConfig(configuration)
            self.admin.loadConfiguration(configuration)
            self.show()

        def nullwizard(*args):
            self.wizard = None

        state = self.admin.getWorkerHeavenState()
        if not state.get('names'):
            self.show_error_dialog(
                'The wizard cannot be run because no workers are logged in.')
            return
        
        wiz = wizard.Wizard(self.admin)
        wiz.connect('finished', _wizard_finished_cb)
        wiz.load_steps()
        wiz.run(True, state, False)

        self.wizard = wiz
        self.wizard.connect('destroy', nullwizard)

    # component view activation functions
    def _component_modify(self, state):
        def propertyErrback(failure):
            failure.trap(errors.PropertyError)
            self.show_error_dialog("%s." % failure.getErrorMessage())
            return None

        def after_getProperty(value, dialog):
            self.debug('got value %r' % value)
            dialog.update_value_entry(value)
            
        def dialog_set_cb(dialog, element, property, value, state):
            cb = self.admin.setProperty(state, element, property, value)
            cb.addErrback(propertyErrback)
        def dialog_get_cb(dialog, element, property, state):
            cb = self.admin.getProperty(state, element, property)
            cb.addCallback(after_getProperty, dialog)
            cb.addErrback(propertyErrback)
        
        name = state.get('name')
        d = dialogs.PropertyChangeDialog(name, self.window)
        d.connect('get', dialog_get_cb, state)
        d.connect('set', dialog_set_cb, state)
        d.run()

    def _component_reload(self, state):
        name = state.get('name')
        if not name:
            return

        dialog = dialogs.ProgressDialog("Reloading",
            "Reloading component code for %s" % name, self.window)
        d = self.admin.reloadComponent(name)
        d.addCallback(lambda result, d: d.destroy(), dialog)
        # add error
        d.addErrback(lambda failure, d: d.destroy(), dialog)
        dialog.start()

    def _component_stop(self, state):
        return self._component_do(state, 'stop', 'Stopping', 'Stopped')
        
    def _component_start(self, state):
        return self._component_do(state, 'start', 'Starting', 'Started')
 
    def _component_do(self, state, action, doing, done):
        if not state:
            state = self.components_view.get_selected_state()
            if not state:
                self.statusbar.push('main', "No component selected.")
                return None

        name = state.get('name')
        if not name:
            return None

        mid = self.statusbar.push('main', "%s component %s" % (doing, name))
        d = self.admin.componentCallRemote(state, action)

        def _actionCallback(result, self, mid):
            self.statusbar.remove('main', mid)
            self.statusbar.push('main', "%s component %s" % (done, name))
        def _actionErrback(failure, self, mid):
            self.statusbar.remove('main', mid)
            self.warning("Failed to %s component %s: %s" % (
                action, name, failure))
            self.statusbar.push('main', "Failed to %s component %s" % (
                action, name))
            
        d.addCallback(_actionCallback, self, mid)
        d.addErrback(_actionErrback, self, mid)

        return d
 
 
    # menubar/toolbar callbacks
    def on_have_connection(self, d, state):
        d.destroy()
        self.on_open_connection(state)

    def file_open_cb(self, button):
        d = connections.ConnectionsDialog(self.window)
        d.show()
        d.connect('have-connection', self.on_have_connection)
    
    def file_quit_cb(self, button):
        self.close()
    
    def manage_start_component_cb(self, button):
        self._component_start(None)
        
    def manage_stop_component_cb(self, button):
        self._component_stop(None)
        
    def manage_stop_all_cb(self, button):
        self.admin.cleanComponents()
        
    def manage_run_wizard_cb(self, x):
        self.runWizard()

    def debug_reload_manager_cb(self, button):
        self.admin.reloadManager()

    def debug_reload_all_cb(self, button):
        # FIXME: move all of the reloads over to this dialog
        def _stop(dialog):
            dialog.stop()
            dialog.destroy()

        def _syntaxErrback(failure, self, progress):
            failure.trap(errors.ReloadSyntaxError)
            _stop(progress)
            self.show_error_dialog(
                "Could not reload component:\n%s." % failure.getErrorMessage())
            return None
            
        def _callLater(admin, dialog):
            deferred = self.admin.reload()
            deferred.addCallback(lambda result, d: _stop(d), dialog)
            deferred.addErrback(_syntaxErrback, self, dialog)
            deferred.addErrback(self._defaultErrback)
        
        dialog = dialogs.ProgressDialog("Reloading ...",
            "Reloading client code", self.window)
        l = lambda admin, text, dialog: dialog.message(
            "Reloading %s code" % text)
        self.admin.connect('reloading', l, dialog)
        dialog.start()
        reactor.callLater(0.2, _callLater, self.admin, dialog)
 
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

        text = 'Flumotion is a streaming media server\n\n(C) 2004-2005 Fluendo S.L.'
        authors = ('Andy Wingo',
                   'Johan Dahlin',
                   'Thomas Vander Stichele',
                   'Wim Taymans')
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

    def show(self):
        # XXX: Use show()
        self.window.show_all()
        

gobject.type_register(Window)

