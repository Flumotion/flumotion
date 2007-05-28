# -*- Mode: Python -*-
# -*- coding: UTF-8 -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# Flumotion - a streaming media server
# Copyright (C) 2004,2005,2006,2007 Fluendo, S.L. (www.fluendo.com).
# All rights reserved.

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
import os.path
import sys

from gettext import gettext as _

import gobject
from gtk import gdk
import gtk
import gtk.glade

from twisted.internet import reactor, defer
from twisted.python import rebuild
from zope.interface import implements

from flumotion.admin.admin import AdminModel
from flumotion.admin import connections
from flumotion.admin.gtk import dialogs, parts, message
from flumotion.admin.gtk import connections as gtkconnections
from flumotion.configure import configure
from flumotion.common import errors, log, worker, planet, common, pygobject
from flumotion.common import connection
from flumotion.manager import admin # Register types
from flumotion.twisted import flavors, reflect, pb as fpb
from flumotion.ui import icons, trayicon

from flumotion.common.planet import moods
from flumotion.common.pygobject import gsignal

from flumotion.common import messages
from flumotion.common.messages import N_
T_ = messages.gettexter('flumotion')

class Window(log.Loggable, gobject.GObject):
    '''
    Creates the GtkWindow for the user interface.
    Also connects to the manager on the given host and port.
    '''

    implements(flavors.IStateListener)
    
    logCategory = 'adminview'
    gsignal('connected')
    
    def __init__(self, model):
        self.__gobject_init__()
        
        self.widgets = {}
        self.debug('creating UI')
        self._trayicon = None

        # current component's UI;
        # L{flumotion.component.base.admin_gtk.BaseAdminGtk}
        self.current_component = None
        self.current_component_state = None # its state

        self._create_ui()

        self._append_recent_connections()

        self._disconnected_dialog = None # set to a dialog if we're
                                         # disconnected

        self._planetState = None
        self._components = None # name -> planet.AdminComponentState

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
        self.admin.connect('connection-failed',
                           self.admin_connection_failed_cb)
        self.admin.connect('component-property-changed',
            self.property_changed_cb)
        self.admin.connect('update', self.admin_update_cb)

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
        
        def set_icon(proc, size, name):
            i = gtk.Image()
            i.set_from_stock('flumotion-'+name, size)
            proc(i)
            i.show()
        
        def make_menu_proc(m): # $%^& pychecker!
            return lambda f: m.set_property('image', f)
        def menu_set_icon(m, name):
            set_icon(make_menu_proc(m), gtk.ICON_SIZE_MENU, name)
            m.show()
        
        def tool_set_icon(m, name):
            set_icon(m.set_icon_widget, gtk.ICON_SIZE_SMALL_TOOLBAR, name)

        menu_set_icon(widgets['menuitem_manage_run_wizard'], 'wizard')
        tool_set_icon(widgets['toolbutton_wizard'], 'wizard')
        menu_set_icon(widgets['menuitem_manage_start_component'], 'play')
        tool_set_icon(widgets['toolbutton_start_component'], 'play')
        menu_set_icon(widgets['menuitem_manage_stop_component'], 'pause')
        tool_set_icon(widgets['toolbutton_stop_component'], 'pause')

        self._trayicon = trayicon.FluTrayIcon(self)
        self._trayicon.set_tooltip(_('Not connected'))

        # the widget containing the component view
        self._component_view = widgets['component_view']
        self._component_view_clear()
 
        window.connect('delete-event', self.close)

        self.components_view = parts.ComponentsView(widgets['components_view'])
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

        self._messages_view = widgets['messages_view']
        self._messages_view.hide()

        return window

    def on_open_connection(self, connectionInfo):
        i = connectionInfo
        model = AdminModel()
        d = model.connectToManager(i)
        self._trayicon.set_tooltip(_("Connecting to %s:%s") %
            (i.host, i.port))

        def connected(model):
            self.window.set_sensitive(True)
            self._setAdminModel(model)
            self._append_recent_connections()

        def refused(failure):
            if failure.check(errors.ConnectionRefusedError):
                d = dialogs.connection_refused_message(i.host,
                                                       self.window)
            else:
                d = dialogs.connection_failed_message(i, str(failure),
                                                      self.window)
            d.addCallback(lambda _: self.window.set_sensitive(True))

        d.addCallbacks(connected, refused)
        self.window.set_sensitive(False)

    def on_recent_activate(self, widget, connectionInfo):
        self.on_open_connection(connectionInfo)

    def _append_recent_connections(self):
        menu = self.widgets['connection_menu'].get_submenu()

        # first clean any old entries
        kids = menu.get_children()
        while True:
            w = kids.pop()
            if w.get_name() == 'connection_quit':
                break
            else:
                menu.remove(w)

        clist = connections.get_recent_connections()
        if not clist:
            return

        def append(i):
            i.show()
            gtk.MenuShell.append(menu, i) # $%^&* pychecker
        def append_txt(c, n):
            i = gtk.MenuItem(c['name'])
            i.connect('activate', self.on_recent_activate, c['info'])
            append(i)
            
        append(gtk.SeparatorMenuItem())
        map(append_txt, clist[:4], range(1,len(clist[:4])+1))

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
    # FIXME: factor this out into a ComponentView or SidePaneView class
    # so we can reuse it
    def show_component(self, state, entryPath, fileName, methodName, data):
        """
        Show the user interface for this component.
        Searches data for the given methodName global,
        then instantiates an object from that class,
        and calls the render() method.

        @type  state:      L{flumotion.common.planet.AdminComponentState}
        @param entryPath:  absolute path to the cached base directory
        @param fileName:   path to the file with the entry point, under
                           entryPath
        @param methodName: name of the method to instantiate the
                           L{flumotion.component.base.admin_gtk.BaseAdminGtk}
                           UI view
        @param data:       the python code to load
        """
        # methodName has historically been GUIClass

        instance = None

        name = state.get('name')
        self.statusbar.set('main', _("Loading UI for %s ...") % name)

        moduleName = common.pathToModuleName(fileName)
        statement = 'import %s' % moduleName
        self.debug('running %s' % statement)
        try:
            exec(statement)
        except SyntaxError, e:
            # the syntax error can happen in the entry file, or any import
            where = getattr(e, 'filename', "<entry file>")
            lineno = getattr(e, 'lineno', 0)
            msg = "Syntax Error at %s:%d while executing %s" % (
                where, lineno, fileName)
            self.warning(msg)
            raise errors.EntrySyntaxError(msg)
        except NameError, e:
            msg = "NameError at while executing %s: %s" % (
                fileName, " ".join(e.args))
            raise
            self.warning(msg)
            raise errors.EntrySyntaxError(msg)
        except ImportError, e:
            msg = "ImportError while executing %s: %s" % (fileName,
                " ".join(e.args))
            self.warning(msg)
            raise errors.EntrySyntaxError(msg)

        # make sure we're running the latest version
        module = reflect.namedAny(moduleName)
        rebuild.rebuild(module)

        # check if we have the method
        if not hasattr(module, methodName):
            msg = 'method %s not found in file %s' % (
                methodName, fileName)
            self.warning(msg)

            m = messages.Error(T_(
                N_("This component has a UI bug.")),
                    debug=msg,
                    id=methodName)
            self._messages_view.add_message(m)

            # FIXME: something more detailed as an error ?
            raise errors.FlumotionError(msg)
        klass = getattr(module, methodName)

        # instantiate the GUIClass
        instance = klass(state, self.admin)
        self.debug("Created entry instance %r" % instance)
        self._instanceSetup(instance, klass, name)

    def _instanceSetup(self, instance, klass, name):
        self.debug('Setting up instance %r' % instance)
        msg = None
        d = None
        try:
            d = instance.setup()
        except Exception, e:
            msg = log.getExceptionMessage(e)
        self.debug('Setup instance %r' % instance)
        if not d:
            msg = "%r.setup() should return a deferred" % klass

        if msg:
            self.warning('Component UI bug: %s' % msg)
            m = messages.Error(T_(
                N_("This component has a UI bug.")),
                    debug=msg,
                    id=name)
            self._messages_view.add_message(m)
            return

        d.addCallback(self._setupCallback, name, instance)
        d.addErrback(self._setupErrback, name)

    def _setupCallback(self, result, name, instance):
        notebook = gtk.Notebook()
        nodeWidgets = {}
        nodes = instance.getNodes()
        self.statusbar.clear('main')
        # create pages for all nodes, and just show a loading label for
        # now
        for node in nodes.values():
            self.debug("Creating node for %s" % node.title)
            label = gtk.Label(_('Loading UI for %s ...') % node.title)
            table = gtk.Table(1, 1)
            table.add(label)
            nodeWidgets[node.title] = table

            notebook.append_page(table, gtk.Label(node.title))
            
        # put "loading" widget in
        self._component_view_set_widget(notebook)

        # trigger node rendering
        d = defer.Deferred()

        for node in nodes.values():
            mid = self.statusbar.push('notebook',
                _("Loading tab %s for %s ...") % (node.title, name))
            node.statusbar = self.statusbar # hack
            self.debug('adding callback for %s node.render()' % node.title)
            d.addCallback(lambda _, n: n.render(), node)
            d.addCallback(self._nodeRenderCallback, node.title,
                nodeWidgets, mid)
            d.addErrback(self._nodeRenderErrback, node.title)

        d.addCallback(self._setCurrentComponentCallback, instance)

        d.callback(None)
        return d

    def _setupErrback(self, failure, name):
        self.warning('Could not setup component %s' % name)
        msg = 'Could not setup component %s: %s' % (name,
            log.getFailureMessage(failure))
        self.debug(msg)
        m = messages.Error(T_(
                N_("This component has a UI bug.")),
                    debug=msg,
                    id=name)
        self._messages_view.add_message(m)

    # called when one node gets rendered
    def _nodeRenderCallback(self, widget, nodeName, nodeWidgets, mid):
        # used by show_component
        self.debug("Got sub widget %r" % widget)
        self.statusbar.remove('notebook', mid)

        # clear out any old node widgets with the same name
        table = nodeWidgets[nodeName]
        for w in table.get_children():
            table.remove(w)
        
        if not widget:
            self.warning(".render() did not return an object")
            widget = gtk.Label(_('%s does not have a UI yet') % nodeName)
        else:
            parent = widget.get_parent()
            if parent:
                parent.remove(widget)
            
        table.add(widget)
        widget.show()

    def _nodeRenderErrback(self, failure, nodeName):
        self.warning('Could not render node %s' % nodeName)
        debug = log.getFailureMessage(failure)
        if failure.check(errors.NoBundleError):
            debug = "Could not get bundle %s" % failure.value.args[0]
        msg = 'Could not render node %s: %s' % (nodeName, debug)
        self.debug(msg)
        m = messages.Error(T_(
                N_("This component has a UI bug in the %s tab."), nodeName),
                    debug=msg,
                    id=nodeName)
        self._messages_view.add_message(m)

    def _setCurrentComponentCallback(self, _, instance):
        self.debug('setting current_component to %r' % instance)
        self.current_component = instance

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
        def flowStateAppend(state, key, value):
            self.debug('flow state append: key %s, value %r' % (key, value))
            if key == 'components':
                self._components[value.get('name')] = value
                # FIXME: would be nicer to do this incrementally instead
                self.update_components()

        def flowStateRemove(state, key, value):
            if key == 'components':
                self._remove_component(value)

        def atmosphereStateAppend(state, key, value):
            if key == 'components':
                self._components[value.get('name')] = value
                # FIXME: would be nicer to do this incrementally instead
                self.update_components()

        def atmosphereStateRemove(state, key, value):
            if key == 'components':
                self._remove_component(value)

        def planetStateAppend(state, key, value):
            if key == 'flows':
                if value != state.get('flows')[0]:
                    self.warning('flumotion-admin can only handle one '
                                 'flow, ignoring /%s', value.get('name'))
                    return
                self.debug('%s flow started', value.get('name'))
                value.addListener(self, append=flowStateAppend,
                                  remove=flowStateRemove)
                for c in value.get('components'):
                    flowStateAppend(value, 'components', c)

        def planetStateRemove(state, key, value):
            self.debug('something got removed from the planet')

        def planetStateSetitem(state, key, subkey, value):
            if key == 'messages':
                self._messages_view.add_message(value)

        def planetStateDelitem(state, key, subkey, value):
            if key == 'messages':
                self._messages_view.clear_message(value.id)

        self.debug('parsing planetState %r' % planetState)
        self._planetState = planetState

        # clear and rebuild list of components that interests us
        self._components = {}

        planetState.addListener(self, append=planetStateAppend,
                                remove=planetStateRemove,
                                setitem=planetStateSetitem,
                                delitem=planetStateDelitem)

        a = planetState.get('atmosphere')
        a.addListener(self, append=atmosphereStateAppend,
                      remove=atmosphereStateRemove)
        for c in a.get('components'):
            atmosphereStateAppend(a, 'components', c)
            
        for f in planetState.get('flows'):
            planetStateAppend(planetState, 'flows', f)
 
        self._clearMessages()

    def _clearMessages(self):
        self._messages_view.clear()
        pstate = self._planetState
        if pstate.hasKey('messages'):
            for message in pstate.get('messages').values():
                self._messages_view.add_message(message)
        
    def stateSet(self, state, key, value):
        # called by model when state of something changes
        if not isinstance(state, planet.AdminComponentState):
            return

        if key == 'message':
            self.statusbar.set('main', value)
        elif key == 'mood':
            self._set_stop_start_component_sensitive()
            current = self.components_view.get_selected_name()
            if value == moods.sleeping.value:
                if state.get('name') == current:
                    self._clearMessages()
                    self._component_view_clear()

    def whsAppend(self, state, key, value):
        if key == 'names':
            self.statusbar.set('main', 'Worker %s logged in.' % value)

    def whsRemove(self, state, key, value):
        if key == 'names':
            self.statusbar.set('main', 'Worker %s logged out.' % value)

    def _remove_component(self, state):
        name = state.get('name')
        self.debug('removing component %s' % name)
        del self._components[name]

        # if this component was selected, clear selection
        if self.current_component_state == state:
            self.debug('removing currently selected component state')
            self.current_component = None
            self.current_component_state = None
        # FIXME: would be nicer to do this incrementally instead
        self.update_components()

        # a component being removed means our selected component could
        # have gone away
        self._set_stop_start_component_sensitive()

    ### admin model callbacks
    def admin_connected_cb(self, admin):
        if self._planetState:
            self._planetState.removeListener(self)
            self._planetState = None
        
        self.info('Connected to manager')
        if self._disconnected_dialog:
            self._disconnected_dialog.destroy()
            self._disconnected_dialog = None

        # FIXME: have a method for this
        self.window.set_title(_('%s - Flumotion Administration') %
            self.admin.adminInfoStr())
        self._trayicon.set_tooltip(self.admin.adminInfoStr())

        self.emit('connected')

        # get initial info we need
        self.setPlanetState(self.admin.planet)

        if not self._components:
            self.debug('no components detected, running wizard')
            # ensure our window is shown
            self.show()
            self.runWizard()
    
    def admin_disconnected_cb(self, admin):
        message = _("Lost connection to manager, reconnecting ...")
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
        
    def admin_connection_refused_later(self, admin):
        message = _("Connection to manager on %s was refused.") % \
            admin.connectionInfoStr()
        self._trayicon.set_tooltip(_("Connection to %s was refused") %
            self.admin.adminInfoStr())
        self.info(message)
        d = dialogs.ErrorDialog(message, self)
        d.show_all()
        d.connect('response', self.close)

    def admin_connection_refused_cb(self, admin):
        log.debug('adminclient', "handling connection-refused")
        reactor.callLater(0, self.admin_connection_refused_later, admin)
        log.debug('adminclient', "handled connection-refused")

    def admin_connection_failed_later(self, admin, reason):
        message = (_("Connection to manager on %s failed (%s).")
                   % (admin.connectionInfoStr(), reason))
        self._trayicon.set_tooltip("Connection to %s failed" %
            self.admin.adminInfoStr())
        self.info(message)
        d = dialogs.ErrorDialog(message, self.window)
        d.show_all()
        d.connect('response', self.close)

    def admin_connection_failed_cb(self, admin, reason):
        log.debug('adminclient', "handling connection-failed")
        reactor.callLater(0, self.admin_connection_failed_later, admin, reason)
        log.debug('adminclient', "handled connection-failed")

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
        # they're all in sleeping or lost
        s = self.widgets['menuitem_manage_clear_all'].set_sensitive
        s(can_start and not can_stop)

    def admin_update_cb(self, admin):
        self.update_components()

    def update_components(self):
        self.components_view.update(self._components)
        self._trayicon.update(self._components)

    def _set_stop_start_component_sensitive(self):
        state = self.current_component_state
        d = self.widgets
        can_start = bool(state
                         and moods.get(state.get('mood')).name == 'sleeping')
        d['menuitem_manage_start_component'].set_sensitive(can_start)
        d['toolbutton_start_component'].set_sensitive(can_start)

        moodname = state and moods.get(state.get('mood')).name
        can_stop = bool(moodname and moodname!='sleeping')
        can_delete = bool(state and not can_stop)
        d['menuitem_manage_stop_component'].set_sensitive(can_stop)
        d['toolbutton_stop_component'].set_sensitive(can_stop)

        d['menuitem_manage_delete_component'].set_sensitive(can_delete)
        d['toolbutton_delete_component'].set_sensitive(can_delete)
        self.debug('can start %r, can stop %r' % (can_start, can_stop))

    # clear the component view in the sidepane.  Called when the current
    # component goes sleeping
    def _component_view_clear(self):
        empty = gtk.Label("")
        self._component_view_set_widget(empty)

    # set the given widget in the component view
    def _component_view_set_widget(self, widget):
        for c in self._component_view.get_children():
            self._component_view.remove(c)
        self._component_view.add(widget)
        widget.show_all()

    ### ui callbacks
    def _components_view_has_selection_cb(self, view, state):
        def compSet(state, key, value):
            if key == 'message':
                self.statusbar.set('main', value)
            elif key == 'mood':
                self._set_stop_start_component_sensitive()
                current = self.components_view.get_selected_name()
                if value == moods.sleeping.value:
                    if state.get('name') == current:
                        self._clearMessages()
                        self._component_view_clear()

        def compAppend(state, key, value):
            name = state.get('name')
            self.debug('stateAppend on component state of %s' % name)
            if key == 'messages':
                current = self.components_view.get_selected_name()
                if name == current:
                    self._messages_view.add_message(value)

        def compRemove(state, key, value):
            name = state.get('name')
            self.debug('stateRemove on component state of %s' % name)
            if key == 'messages':
                current = self.components_view.get_selected_name()
                if name == current:
                    self._messages_view.clear_message(value.id)
            self._set_stop_start_component_sensitive()

        if self.current_component_state:
            self.current_component_state.removeListener(self)
        self.current_component_state = state
        if self.current_component_state:
            self.current_component_state.addListener(self, compSet,
                                                     compAppend,
                                                     compRemove)

        self._set_stop_start_component_sensitive()

        if not state:
            self.debug('no state, returning')
            return

        name = state.get('name')
        mood = state.get('mood')
        messages = state.get('messages')
        self._clearMessages()
        self._component_view_clear()

        if messages:
            for m in messages:
                self.debug('have message %r' % m)
                self._messages_view.add_message(m)

        if mood == moods.sad.value:
            self.debug('component %s is sad' % name)
            self.statusbar.set('main',
                _("Component %s is sad") % name)
           
            return

        def gotEntryCallback(result):
            entryPath, filename, methodName = result

            self.statusbar.set('main', _('Showing UI for %s') % name)

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
                state, entryPath, filename, methodName, data)

        def gotEntryNoBundleErrback(failure):
            failure.trap(errors.NoBundleError)
            self.debug("Making generic UI for component %s" % name)

            # make a generic ui
            from flumotion.component.base import admin_gtk
            instance = admin_gtk.BaseAdminGtk(state, self.admin)
            self._instanceSetup(instance, admin_gtk.BaseAdminGtk, name)

        def gotEntrySleepingComponentErrback(failure):
            failure.trap(errors.SleepingComponentError)

            self.statusbar.set('main',
                _("Component %s is still sleeping") % name)

        self.statusbar.set('main', _("Requesting UI for %s ...") % name)
        # if there's a current component being shown, give it a chance
        # to clean up
        if self.current_component:
            if hasattr(self.current_component, 'cleanup'):
                self.debug('Cleaning up current component view')
                self.current_component.cleanup()
        self.current_component = None

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
                _('The wizard cannot be run because no workers are logged in.'))
            return
        
        wiz = wizard.Wizard(self.window, self.admin)
        wiz.connect('finished', _wizard_finished_cb)
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
            _("Reloading component code for %s") % name, self.window)
        d = self.admin.reloadComponent(state)
        d.addCallback(lambda result, d: d.destroy(), dialog)
        # add error
        d.addErrback(lambda failure, d: d.destroy(), dialog)
        dialog.start()

    def _component_stop(self, state):
        """
        @returns: a L{twisted.internet.defer.Deferred}
        """
        return self._component_do(state, 'Stop', 'Stopping', 'Stopped')
        
    def _component_start(self, state):
        """
        @returns: a L{twisted.internet.defer.Deferred}
        """
        return self._component_do(state, 'Start', 'Starting', 'Started')
 
    def _component_restart(self, state):
        """
        @returns: a L{twisted.internet.defer.Deferred}
        """
        d = self._component_stop(state)
        d.addCallback(lambda r: self._component_start(state))
        return d
    
    def _component_delete(self, state):
        """
        @returns: a L{twisted.internet.defer.Deferred}
        """
        return self._component_do(state, '', 'Deleting', 'Deleted', 
            'deleteComponent')

    def _component_do(self, state, action, doing, done, 
        remoteMethodPrefix="component"):
        """
        @param remoteMethodName: prefix for remote method to run
        """
        if not state:
            state = self.components_view.get_selected_state()
            if not state:
                self.statusbar.push('main', _("No component selected."))
                return None

        name = state.get('name')
        if not name:
            return None

        mid = self.statusbar.push('main', "%s component %s" % (doing, name))
        d = self.admin.callRemote(remoteMethodPrefix + action, state)

        def _actionCallback(result, self, mid):
            self.statusbar.remove('main', mid)
            self.statusbar.push('main', "%s component %s" % (done, name))
        def _actionErrback(failure, self, mid):
            self.statusbar.remove('main', mid)
            self.warning("Failed to %s component %s: %s" % (
                action, name, failure))
            self.statusbar.push('main', _("Failed to %s component %s") % (
                action, name))
            
        d.addCallback(_actionCallback, self, mid)
        d.addErrback(_actionErrback, self, mid)

        return d
 
    # menubar/toolbar callbacks
    def on_have_connection(self, d, connectionInfo):
        d.destroy()
        self.on_open_connection(connectionInfo)

    def connection_open_recent_cb(self, button):
        d = gtkconnections.ConnectionsDialog(self.window)
        d.show()
        d.connect('have-connection', self.on_have_connection)

    def connection_open_existing_cb(self, button):
        def got_state(state, g):
            g.set_sensitive(False)
            authenticator = fpb.Authenticator(username=state['user'],
                                              password=state['passwd'])
            info = connection.PBConnectionInfo(state['host'], state['port'],
                                               not state['use_insecure'],
                                               authenticator)
            g.destroy()
            self.on_open_connection(info)

        from flumotion.admin.gtk import greeter
        wiz = greeter.ConnectExisting()
        d = wiz.run_async()
        d.addCallback(got_state, wiz)

    def on_import_response(self, d, response):
        if response==gtk.RESPONSE_ACCEPT:
            name = d.get_filename()
            conf_xml = open(name, 'r').read()
            self.admin.loadConfiguration(conf_xml)
        d.destroy()

    def connection_import_configuration_cb(self, button):
        d = gtk.FileChooserDialog(_("Import Configuration..."), self.window,
                                  gtk.FILE_CHOOSER_ACTION_OPEN,
                                  (gtk.STOCK_CANCEL, gtk.RESPONSE_REJECT,
                                   gtk.STOCK_OK, gtk.RESPONSE_ACCEPT))
        d.set_default_response(gtk.RESPONSE_ACCEPT)
        d.show()
        d.connect('response', self.on_import_response)
    
    def getConfiguration_cb(self, conf_xml, name, chooser):
        file_exists = True
        if os.path.exists(name):
            d = gtk.MessageDialog(self.window, gtk.DIALOG_MODAL,
                                  gtk.MESSAGE_ERROR, gtk.BUTTONS_YES_NO,
                                  _("File already exists.\nOverwrite?"))
            d.connect("response", lambda self, response: d.hide())
            if d.run() == gtk.RESPONSE_YES:
                file_exists = False
        else:
            file_exists = False

        if not file_exists:
            f = open(name, 'w')
            f.write(conf_xml)
            f.close()
            chooser.destroy()

    def on_export_response(self, d, response):
        if response==gtk.RESPONSE_ACCEPT:
            deferred = self.admin.getConfiguration()
            name = d.get_filename()
            deferred.addCallback(self.getConfiguration_cb, name, d)
        else:
            d.destroy()

    def connection_export_configuration_cb(self, button):
        d = gtk.FileChooserDialog(_("Export Configuration..."), self.window,
                                  gtk.FILE_CHOOSER_ACTION_SAVE,
                                  (gtk.STOCK_CANCEL, gtk.RESPONSE_REJECT,
                                   gtk.STOCK_OK, gtk.RESPONSE_ACCEPT))
        d.set_default_response(gtk.RESPONSE_ACCEPT)
        d.show()
        d.connect('response', self.on_export_response)
    
    def connection_quit_cb(self, button):
        self.close()
    
    def manage_start_component_cb(self, button):
        self._component_start(None)
        
    def manage_stop_component_cb(self, button):
        self._component_stop(None)

    def manage_delete_component_cb(self, button):
        self._component_delete(None)
        
    def manage_start_all_cb(self, button):
        for c in self._components.values():
            self._component_start(c)
        
    def manage_stop_all_cb(self, button):
        for c in self._components.values():
            self._component_stop(c)
        
    def manage_clear_all_cb(self, button):
        self.admin.cleanComponents()
        
    def manage_run_wizard_cb(self, x):
        self.runWizard()

    def debug_reload_manager_cb(self, button):
        self.admin.reloadManager()

    def debug_reload_admin_cb(self, button):
        self.admin.reloadAdmin()

    def debug_reload_all_cb(self, button):
        # FIXME: move all of the reloads over to this dialog
        def _stop(dialog):
            dialog.stop()
            dialog.destroy()

        def _syntaxErrback(failure, self, progress):
            failure.trap(errors.ReloadSyntaxError)
            _stop(progress)
            self.show_error_dialog(
                _("Could not reload component:\n%s.") %
                failure.getErrorMessage())
            return None
            
        def _callLater(admin, dialog):
            deferred = self.admin.reload()
            deferred.addCallback(lambda result, d: _stop(d), dialog)
            deferred.addErrback(_syntaxErrback, self, dialog)
            deferred.addErrback(self._defaultErrback)
        
        dialog = dialogs.ProgressDialog(_("Reloading ..."),
            _("Reloading client code"), self.window)
        l = lambda admin, text, dialog: dialog.message(
            _("Reloading %s code") % text)
        self.admin.connect('reloading', l, dialog)
        dialog.start()
        reactor.callLater(0.2, _callLater, self.admin, dialog)
 
    def debug_start_shell_cb(self, button):
        if sys.version_info[1] >= 4:
            from flumotion.extern import code
        else:
            import code

        vars = \
            {
                "admin": self.admin,
                "components": self._components
            }
        message = ("  Flumotion Admin Debug Shell\n"
                   "\n"
                   "Local variables are:\n"
                   "  admin      (flumotion.admin.admin.AdminModel)\n"
                   "  components (dict: name -> flumotion.common.planet.AdminComponentState)\n"
                   "\n"
                   "You can do remote component calls using:\n"
                   "  admin.componentCallRemote(components['component-name'],\n"
                   "         'methodName', arg1, arg2)\n\n")

        code.interact(local=vars, banner=message)

    def help_about_cb(self, button):
        dialog = gtk.Dialog(_('About Flumotion'), self.window,
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

        text = _('Flumotion is a streaming media server.\n\n'
            '© 2004, 2005, 2006, 2007 Fluendo S.L.')
        authors = ('Andy Wingo',
                   'Johan Dahlin',
                   'Mike Smith',
                   'Thomas Vander Stichele',
                   'Wim Taymans',
                   'Zaheer Abbas Merali',
                   'Sébastien Merle'
        )
        text += '\n\n<small>' + _('Authors') + ':\n'
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
        self.window.show()

pygobject.type_register(Window)

