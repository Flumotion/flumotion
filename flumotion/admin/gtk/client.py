# -*- Mode: Python -*-
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

import gettext
import os
import sys

import gobject
import gtk
import gtk.glade
from twisted.internet import reactor
from zope.interface import implements

from flumotion.admin.admin import AdminModel
from flumotion.admin import connections
from flumotion.admin.gtk import dialogs, parts
from flumotion.admin.gtk.parts import getComponentLabel
from flumotion.admin.gtk import connections as gtkconnections
from flumotion.configure import configure
from flumotion.common import errors, log, planet, pygobject
from flumotion.common import connection
from flumotion.manager import admin # Register types
from flumotion.twisted import flavors, pb as fpb
from flumotion.ui import trayicon

from flumotion.common.planet import moods
from flumotion.common.pygobject import gsignal

from flumotion.common import messages

_ = gettext.gettext
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
        gobject.GObject.__init__(self)


        self._trayicon = None
        self._current_component_state = None
        self._disconnected_dialog = None # set to a dialog when disconnected
        self._planetState = None
        self._components = None # name -> planet.AdminComponentState
        self._wizard = None
        self._admin = None
        self._widgets = {}
        self._window = None

        self._create_ui()
        self._append_recent_connections()
        self._set_admin_model(model)

    # Public API

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
                    self._clear_messages()

    def componentCallRemoteStatus(self, state, pre, post, fail,
                                  methodName, *args, **kwargs):
        if not state:
            state = self.components_view.get_selected_state()
            if not state:
                return

        label = getComponentLabel(state)
        if not label:
            return

        mid = None
        if pre:
            mid = self.statusbar.push('main', pre % label)
        d = self._admin.componentCallRemote(state, methodName, *args, **kwargs)

        def cb(result, self, mid):
            if mid:
                self.statusbar.remove('main', mid)
            if post:
                self.statusbar.push('main', post % label)
        def eb(failure, self, mid):
            if mid:
                self.statusbar.remove('main', mid)
            self.warning("Failed to execute %s on component %s: %s"
                         % (methodName, label, failure))
            if fail:
                self.statusbar.push('main', fail % label)

        d.addCallback(cb, self, mid)
        d.addErrback(eb, self, mid)

    def componentCallRemote(self, state, methodName, *args, **kwargs):
        self.componentCallRemoteStatus(None, None, None, None,
                                       methodName, *args, **kwargs)

    def whsAppend(self, state, key, value):
        if key == 'names':
            self.statusbar.set('main', 'Worker %s logged in.' % value)

    def whsRemove(self, state, key, value):
        if key == 'names':
            self.statusbar.set('main', 'Worker %s logged out.' % value)

    # Private

    def _create_ui(self):
        self.debug('creating UI')
        # returns the window
        # called from __init__
        wtree = gtk.glade.XML(os.path.join(configure.gladedir, 'admin.glade'))
        wtree.signal_autoconnect(self)

        for widget in wtree.get_widget_prefix(''):
            self._widgets[widget.get_name()] = widget
        widgets = self._widgets

        window = self._window = widgets['main_window']
        window.connect('delete-event', self._on_window_delete_event)

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


        self.components_view = parts.ComponentsView(widgets['components_view'])
        self.components_view.connect('has-selection',
            self._components_view_has_selection_cb)
        self.components_view.connect('activated',
            self._components_view_activated_cb)
        self.statusbar = parts.AdminStatusbar(widgets['statusbar'])
        self._set_stop_start_component_sensitive()
        self.components_view.connect(
            'notify::can-start-any',
            self._component_view_start_stop_notify_cb)
        self.components_view.connect(
            'notify::can-stop-any',
            self._component_view_start_stop_notify_cb)
        self._component_view_start_stop_notify_cb()

        self._messages_view = widgets['messages_view']
        self._messages_view.hide()

        return window

    def _append_recent_connections(self):
        menu = self._widgets['connection_menu'].get_submenu()

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
            i.connect('activate', self._on_recent_activate, c['info'])
            append(i)

        append(gtk.SeparatorMenuItem())
        map(append_txt, clist[:4], range(1,len(clist[:4])+1))

    def _set_admin_model(self, model):
        'set the model to which we are a view/controller'
        # it's ok if we've already been connected
        self.debug('setting model')

        if self._admin:
            self.debug('Connecting to new model %r' % model)
            if self._wizard:
                self._wizard.destroy()

        self._admin = model

        # window gets created after model connects initially, so check
        # here
        if self._admin.isConnected():
            self._admin_connected_cb(model)

        self._admin.connect('connected', self._admin_connected_cb)
        self._admin.connect('disconnected', self._admin_disconnected_cb)
        self._admin.connect('connection-refused',
                           self._admin_connection_refused_cb)
        self._admin.connect('connection-failed',
                           self._admin_connection_failed_cb)
        self._admin.connect('update', self._admin_update_cb)

    def _close(self, *args):
        reactor.stop()

    def _dump_config(self, configation):
        import pprint
        import cStringIO
        fd = cStringIO.StringIO()
        pprint.pprint(configation, fd)
        fd.seek(0)
        self.debug('Configuration=%s' % fd.read())

    def _run_wizard(self):
        if self._wizard:
            self._wizard.present()

        from flumotion.wizard import wizard

        def _wizard_finished_cb(wizard, configuration):
            wizard.destroy()
            self._dump_config(configuration)
            self._admin.loadConfiguration(configuration)
            self.show()

        def nullwizard(*args):
            self._wizard = None

        state = self._admin.getWorkerHeavenState()
        if not state.get('names'):
            self._show_error_dialog(
                _('The wizard cannot be run because no workers are logged in.'))
            return

        wizard = wizard.Wizard(self._window, self._admin)
        wizard.connect('finished', _wizard_finished_cb)
        wizard.run(True, state, False)

        self._wizard = wizard
        self._wizard.connect('destroy', nullwizard)

    def _open_connection(self, connectionInfo):
        i = connectionInfo
        model = AdminModel()
        d = model.connectToManager(i)

        self._trayicon.set_tooltip(_("Connecting to %(host)s:%(port)s") % {
            'host': i.host,
            'port': i.port,
        })

        def connected(model):
            self._window.set_sensitive(True)
            self._set_admin_model(model)
            self._append_recent_connections()

        def refused(failure):
            if failure.check(errors.ConnectionRefusedError):
                d = dialogs.connection_refused_message(i.host,
                                                       self._window)
            else:
                d = dialogs.connection_failed_message(i, str(failure),
                                                      self._window)
            d.addCallback(lambda _: self._window.set_sensitive(True))

        d.addCallbacks(connected, refused)
        self._window.set_sensitive(False)

    def _show_about_dialog(self):
        about = dialogs.AboutDialog(self._window)
        about.run()
        about.destroy()

    def _show_error_dialog(self, message):
        d = dialogs.ErrorDialog(message, self._window,
                                close_on_response=True)
        d.show_all()

    def _update_components(self):
        self.components_view.update(self._components)
        self._trayicon.update(self._components)

    def _set_planet_state(self, planetState):

        def flowStateAppend(state, key, value):
            self.debug('flow state append: key %s, value %r' % (key, value))
            if key == 'components':
                self._components[value.get('name')] = value
                # FIXME: would be nicer to do this incrementally instead
                self._update_components()

        def flowStateRemove(state, key, value):
            if key == 'components':
                self._remove_component(value)

        def atmosphereStateAppend(state, key, value):
            if key == 'components':
                self._components[value.get('name')] = value
                # FIXME: would be nicer to do this incrementally instead
                self._update_components()

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

        self._clear_messages()

        a = planetState.get('atmosphere')
        a.addListener(self, append=atmosphereStateAppend,
                      remove=atmosphereStateRemove)
        for c in a.get('components'):
            atmosphereStateAppend(a, 'components', c)

        for f in planetState.get('flows'):
            planetStateAppend(planetState, 'flows', f)

    # component view activation functions

    def _component_modify(self, state):
        def propertyErrback(failure):
            failure.trap(errors.PropertyError)
            self._show_error_dialog("%s." % failure.getErrorMessage())
            return None

        def after_getProperty(value, dialog):
            self.debug('got value %r' % value)
            dialog.update_value_entry(value)

        def dialog_set_cb(dialog, element, property, value, state):
            cb = self._admin.setProperty(state, element, property, value)
            cb.addErrback(propertyErrback)
        def dialog_get_cb(dialog, element, property, state):
            cb = self._admin.getProperty(state, element, property)
            cb.addCallback(after_getProperty, dialog)
            cb.addErrback(propertyErrback)

        name = state.get('name')
        d = dialogs.PropertyChangeDialog(name, self._window)
        d.connect('get', dialog_get_cb, state)
        d.connect('set', dialog_set_cb, state)
        d.run()

    def _remove_component(self, state):
        name = state.get('name')
        self.debug('removing component %s' % name)
        del self._components[name]

        # if this component was selected, clear selection
        if self._current_component_state == state:
            self.debug('removing currently selected component state')
            self._current_component_state = None
        # FIXME: would be nicer to do this incrementally instead
        self._update_components()

        # a component being removed means our selected component could
        # have gone away
        self._set_stop_start_component_sensitive()

    def _component_reload(self, state):
        name = getComponentLabel(state)

        dialog = dialogs.ProgressDialog("Reloading",
            _("Reloading component code for %s") % name, self._window)
        d = self._admin.reloadComponent(state)
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

        name = getComponentLabel(state)
        if not name:
            return None

        mid = self.statusbar.push('main', "%s component %s" % (doing, name))
        d = self._admin.callRemote(remoteMethodPrefix + action, state)

        def _actionCallback(result, self, mid):
            self.statusbar.remove('main', mid)
            self.statusbar.push('main', "%s component %s" % (done, name))
        def _actionErrback(failure, self, mid):
            self.statusbar.remove('main', mid)
            self.warning("Failed to %s component %s: %s" % (
                action.lower(), name, failure))
            self.statusbar.push('main',
                _("Failed to %(action)s component %(name)s") % {
                    'action': action.lower(),
                    'name': name,
                })

        d.addCallback(_actionCallback, self, mid)
        d.addErrback(_actionErrback, self, mid)

        return d

    def _clear_messages(self):
        self._messages_view.clear()
        pstate = self._planetState
        if pstate and pstate.hasKey('messages'):
            for message in pstate.get('messages').values():
                self._messages_view.add_message(message)

    def _set_stop_start_component_sensitive(self):
        state = self._current_component_state
        d = self._widgets
        can_start = bool(state
                         and moods.get(state.get('mood')).name == 'sleeping')
        d['menuitem_manage_start_component'].set_sensitive(can_start)
        d['toolbutton_start_component'].set_sensitive(can_start)

        moodname = state and moods.get(state.get('mood')).name
        can_stop = bool(moodname and moodname != 'sleeping')
        can_delete = bool(state and not can_stop)
        d['menuitem_manage_stop_component'].set_sensitive(can_stop)
        d['toolbutton_stop_component'].set_sensitive(can_stop)

        d['menuitem_manage_delete_component'].set_sensitive(can_delete)
        d['toolbutton_delete_component'].set_sensitive(can_delete)
        self.debug('can start %r, can stop %r' % (can_start, can_stop))

    ### admin model callbacks

    def _admin_connected_cb(self, admin):
        self.info('Connected to manager')
        if self._disconnected_dialog:
            self._disconnected_dialog.destroy()
            self._disconnected_dialog = None

        # FIXME: have a method for this
        self._window.set_title(_('%s - Flumotion Administration') %
            self._admin.adminInfoStr())
        self._trayicon.set_tooltip(self._admin.adminInfoStr())

        self.emit('connected')

        self._component_view.set_single_admin(admin)

        self._set_planet_state(self._admin.planet)

        if not self._components:
            self.debug('no components detected, running wizard')
            # ensure our window is shown
            self.show()
            self._run_wizard()

    def _admin_disconnected_cb(self, admin):
        self._components = {}
        self._update_components()
        self._clear_messages()
        if self._planetState:
            self._planetState.removeListener(self)
            self._planetState = None

        message = _("Lost connection to manager, reconnecting ...")
        d = gtk.MessageDialog(self._window, gtk.DIALOG_DESTROY_WITH_PARENT,
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
            self._admin.reconnect()

    def _admin_connection_refused_later(self, admin):
        message = _("Connection to manager on %s was refused.") % \
            admin.connectionInfoStr()
        self._trayicon.set_tooltip(_("Connection to %s was refused") %
            self._admin.adminInfoStr())
        self.info(message)
        d = dialogs.ErrorDialog(message, self)
        d.show_all()
        d.connect('response', self._close)

    def _admin_connection_refused_cb(self, admin):
        log.debug('adminclient', "handling connection-refused")
        reactor.callLater(0, self._admin_connection_refused_later, admin)
        log.debug('adminclient', "handled connection-refused")

    def _admin_connection_failed_later(self, admin, reason):
        message = (
            _("Connection to manager on %(conn)s failed (%(reason)s).") % {
                'conn': admin.connectionInfoStr(),
                'reason': reason,
            })
        self._trayicon.set_tooltip("Connection to %s failed" %
            self._admin.adminInfoStr())
        self.info(message)
        d = dialogs.ErrorDialog(message, self._window)
        d.show_all()
        d.connect('response', self._close)

    def _admin_connection_failed_cb(self, admin, reason):
        log.debug('adminclient', "handling connection-failed")
        reactor.callLater(0, self._admin_connection_failed_later,
                          admin, reason)
        log.debug('adminclient', "handled connection-failed")

    def _admin_update_cb(self, admin):
        self._update_components()

    ### ui callbacks

    def _on_recent_activate(self, widget, connectionInfo):
        self._open_connection(connectionInfo)

    def _on_window_delete_event(self, window, event):
        self._close()

    def _components_view_has_selection_cb(self, view, state):
        self.debug('component %s has selection', state)
        def compSet(state, key, value):
            if key == 'mood':
                self._set_stop_start_component_sensitive()

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

        if self._current_component_state:
            self._current_component_state.removeListener(self)
        self._current_component_state = state
        if self._current_component_state:
            self._current_component_state.addListener(
                self, compSet, compAppend, compRemove)

        self._set_stop_start_component_sensitive()
        self._component_view.show_object(state)
        self._clear_messages()

        if state:
            name = getComponentLabel(state)

            messages = state.get('messages')
            if messages:
                for m in messages:
                    self.debug('have message %r' % m)
                    self._messages_view.add_message(m)

            if state.get('mood') == moods.sad.value:
                self.debug('component %s is sad' % name)
                self.statusbar.set('main',
                    _("Component %s is sad") % name)

        # FIXME: show statusbar things
        # self.statusbar.set('main', _('Showing UI for %s') % name)
        # self.statusbar.set('main',
        #       _("Component %s is still sleeping") % name)
        # self.statusbar.set('main', _("Requesting UI for %s ...") % name)
        # self.statusbar.set('main', _("Loading UI for %s ...") % name)
        # self.statusbar.clear('main')
        # mid = self.statusbar.push('notebook',
        #         _("Loading tab %s for %s ...") % (node.title, name))
        # node.statusbar = self.statusbar # hack

    def _components_view_activated_cb(self, view, state, action):
        self.debug('action %s on component %s' % (action, state.get('name')))
        method_name = '_component_' + action
        if hasattr(self, method_name):
            getattr(self, method_name)(state)
        else:
            self.warning("No method '%s' implemented" % method_name)

    def _component_view_start_stop_notify_cb(self, *args):
        can_start = self.components_view.get_property('can-start-any')
        can_stop = self.components_view.get_property('can-stop-any')
        self._widgets['menuitem_manage_stop_all'].set_sensitive(can_stop)
        self._widgets['menuitem_manage_start_all'].set_sensitive(can_start)
        # they're all in sleeping or lost
        s = self._widgets['menuitem_manage_clear_all'].set_sensitive
        s(can_start and not can_stop)

    # menubar/toolbar callbacks

    def connection_open_recent_cb(self, button):
        d = gtkconnections.ConnectionsDialog(self._window)
        def on_have_connection(d, connectionInfo):
            d.destroy()
            self._open_connection(connectionInfo)
        d.connect('have-connection', on_have_connection)
        d.show()

    def connection_open_existing_cb(self, button):
        def got_state(state, g):
            g.set_sensitive(False)
            authenticator = fpb.Authenticator(username=state['user'],
                                              password=state['passwd'])
            info = connection.PBConnectionInfo(state['host'], state['port'],
                                               not state['use_insecure'],
                                               authenticator)
            g.destroy()
            self._open_connection(info)

        from flumotion.admin.gtk import greeter
        wiz = greeter.ConnectExisting()
        d = wiz.run_async()
        d.addCallback(got_state, wiz)

    def connection_import_configuration_cb(self, button):
        d = gtk.FileChooserDialog(_("Import Configuration..."), self._window,
                                  gtk.FILE_CHOOSER_ACTION_OPEN,
                                  (gtk.STOCK_CANCEL, gtk.RESPONSE_REJECT,
                                   gtk.STOCK_OK, gtk.RESPONSE_ACCEPT))
        d.set_default_response(gtk.RESPONSE_ACCEPT)
        def on_import_response(d, response):
            if response == gtk.RESPONSE_ACCEPT:
                name = d.get_filename()
                conf_xml = open(name, 'r').read()
                self._admin.loadConfiguration(conf_xml)
            d.destroy()
        d.connect('response', on_import_response)
        d.show()

    def connection_export_configuration_cb(self, button):
        d = gtk.FileChooserDialog(_("Export Configuration..."), self._window,
                                  gtk.FILE_CHOOSER_ACTION_SAVE,
                                  (gtk.STOCK_CANCEL, gtk.RESPONSE_REJECT,
                                   gtk.STOCK_OK, gtk.RESPONSE_ACCEPT))
        d.set_default_response(gtk.RESPONSE_ACCEPT)

        def _get_configuration_cb(conf_xml, name, chooser):
            file_exists = True
            if os.path.exists(name):
                d = gtk.MessageDialog(self._window, gtk.DIALOG_MODAL,
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

        def on_export_response(d, response):
            if response == gtk.RESPONSE_ACCEPT:
                deferred = self._admin.getConfiguration()
                name = d.get_filename()
                deferred.addCallback(_get_configuration_cb, name, d)
            else:
                d.destroy()
        d.connect('response', on_export_response)
        d.show()

    def connection_quit_cb(self, button):
        self._close()

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
        self._admin.cleanComponents()

    def manage_run_wizard_cb(self, x):
        self._run_wizard()

    def debug_reload_manager_cb(self, button):
        self._admin.reloadManager()

    def debug_reload_admin_cb(self, button):
        self._admin.reloadAdmin()

    def debug_reload_all_cb(self, button):
        dialog = dialogs.ProgressDialog(_("Reloading ..."),
            _("Reloading client code"), self._window)

        # FIXME: move all of the reloads over to this dialog
        def _stopCallback(result):
            dialog.stop()
            dialog.destroy()

        def _syntaxErrback(failure):
            failure.trap(errors.ReloadSyntaxError)
            dialog.stop()
            dialog.destroy()
            self._show_error_dialog(
                _("Could not reload component:\n%s.") %
                failure.getErrorMessage())
            return None

        def _defaultErrback(failure):
            self.warning('Errback: unhandled failure: %s' %
                failure.getErrorMessage())
            return failure

        def _callLater(admin):
            d = self._admin.reload()
            d.addCallback(_stopCallback)
            d.addErrback(_syntaxErrback)
            d.addErrback(_defaultErrback)

        def _reloadCallback(admin, text):
            dialog.message(_("Reloading %s code") % text)

        self._admin.connect('reloading', _reloadCallback)
        dialog.start()
        reactor.callLater(0.2, _callLater, self._admin)

    def debug_start_shell_cb(self, button):
        if sys.version_info >= (2, 4):
            from flumotion.extern import code
        else:
            import code

        vars = \
            {
                "admin": self._admin,
                "components": self._components
            }
        message = """Flumotion Admin Debug Shell

Local variables are:
  admin      (flumotion.admin.admin.AdminModel)
  components (dict: name -> flumotion.common.planet.AdminComponentState)

You can do remote component calls using:
  admin.componentCallRemote(components['component-name'],
         'methodName', arg1, arg2)

"""
        code.interact(local=vars, banner=message)

    def help_about_cb(self, button):
        self._show_about_dialog()

    def show(self):
        # XXX: Use show()
        self._window.show()

pygobject.type_register(Window)
