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
from twisted.internet.defer import maybeDeferred
from zope.interface import implements
from xml.dom.ext import PrettyPrint
from xml.dom.ext.reader.Sax import FromXml

from flumotion.admin.admin import AdminModel
from flumotion.admin import connections
from flumotion.admin.gtk import dialogs, parts
from flumotion.admin.gtk.parts import getComponentLabel
from flumotion.admin.gtk import connections as gtkconnections
from flumotion.configure import configure
from flumotion.common import errors, log, planet, pygobject
from flumotion.common import connection, common
from flumotion.manager import admin # Register types
from flumotion.twisted import flavors, pb as fpb
from flumotion.ui import trayicon
from flumotion.common.planet import moods
from flumotion.common.pygobject import gsignal

from flumotion.common import messages

_ = gettext.gettext
T_ = messages.gettexter('flumotion')

MAIN_UI = """
<ui>
  <menubar name="menubar">
    <menu action="connection">
      <menuitem action="open-recent"/>
      <menuitem action="open-existing"/>
      <menuitem action="import-config"/>
      <menuitem action="export-config"/>
      <separator name="sep1"/>
      <placeholder name="recent"/>
      <separator name="sep2"/>
      <menuitem action="quit"/>
    </menu>
    <menu action="manage">
      <menuitem action="start-component"/>
      <menuitem action="stop-component"/>
      <menuitem action="delete-component"/>
      <separator name="sep3"/>
      <menuitem action="start-all"/>
      <menuitem action="stop-all"/>
      <menuitem action="clear-all"/>
      <separator name="sep4"/>
      <menuitem action="run-wizard"/>
    </menu>
    <menu action="debug">
      <menuitem action="reload-manager"/>
      <menuitem action="reload-admin"/>
      <menuitem action="reload-all"/>
      <menuitem action="start-shell"/>
    </menu>
    <menu action="help">
      <menuitem action="about"/>
    </menu>
  </menubar>
  <toolbar name="toolbar">
    <toolitem action="open-recent"/>
    <separator name="sep5"/>
    <toolitem action="start-component"/>
    <toolitem action="stop-component"/>
    <toolitem action="delete-component"/>
    <separator name="sep6"/>
    <toolitem action="run-wizard"/>
  </toolbar>
</ui>
"""

RECENT_UI_TEMPLATE = '''<ui>
  <menubar name="menubar">
    <menu action="connection">
      <placeholder name="recent">
      %s
      </placeholder>
    </menu>
  </menubar>
</ui>'''

MAX_RECENT_ITEMS = 4


class Window(log.Loggable, gobject.GObject):
    '''
    Creates the GtkWindow for the user interface.
    Also connects to the manager on the given host and port.
    '''

    implements(flavors.IStateListener)

    logCategory = 'adminview'
    gsignal('connected')

    def __init__(self):
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
        self._recent_menu_uid = None

        self._create_ui()
        self._append_recent_connections()

    # Public API

    def stateSet(self, state, key, value):
        # called by model when state of something changes
        if not isinstance(state, planet.AdminComponentState):
            return

        if key == 'message':
            self.statusbar.set('main', value)
        elif key == 'mood':
            self._update_component_actions()
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

    def show(self):
        self._window.show()

    def setAdminModel(self, model):
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

    # Private

    def _create_ui(self):
        self.debug('creating UI')
        # returns the window
        # called from __init__
        wtree = gtk.glade.XML(os.path.join(configure.gladedir, 'admin.glade'))
        wtree.signal_autoconnect(self)

        widgets = self._widgets
        for widget in wtree.get_widget_prefix(''):
            widgets[widget.get_name()] = widget

        window = self._window = widgets['main_window']
        vbox = widgets['vbox1']
        window.connect('delete-event', self._window_delete_event_cb)

        actions = [
            # Connection
            ('connection', None, _("_Connection")),
            ('open-recent', gtk.STOCK_OPEN, _('_Open Recent Connection...'), None,
             None, self._connection_open_recent_cb),
            ('open-existing', None, _('Open _Existing Connection...'), None,
             None, self._connection_open_existing_cb),
            ('import-config', None, _('_Import Configuration...'), None,
             None, self._connection_import_configuration_cb),
            ('export-config', None, _('_Export Configuration...'), None,
             None, self._connection_export_configuration_cb),
            ('quit', gtk.STOCK_QUIT, _('_Quit'), None,
             None, self._connection_quit_cb),

            # Manage
            ('manage', None, _('_Manage')),
            ('start-component', 'flumotion-play', _('_S_tart Component'), None,
             None, self._manage_start_component_cb),
            ('stop-component', 'flumotion-pause', _('St_op Component'), None,
             None, self._manage_stop_component_cb),
            ('delete-component', gtk.STOCK_DELETE, _('_Delete Component'), None,
             None, self._manage_delete_component_cb),
            ('start-all', None, _('Start _All'), None,
             None, self._manage_start_all_cb),
            ('stop-all', None, _('Stop A_ll'), None,
             None, self._manage_stop_all_cb),
            ('clear-all', gtk.STOCK_CLEAR, _('_Clear All'), None,
             None, self._manage_clear_all_cb),
            ('run-wizard', 'flumotion-wizard', _('Run _Wizard'), None,
             None, self._manage_run_wizard_cb),

            # Debug
            ('debug', None, _('_Debug')),
            ('reload-manager', gtk.STOCK_REFRESH, _('Reload _Manager'), None,
             None, self._debug_reload_manager_cb),
            ('reload-admin', gtk.STOCK_REFRESH, _('Reload _Admin'), None,
             None, self._debug_reload_admin_cb),
            ('reload-all', gtk.STOCK_REFRESH, _('Reload A_ll'), None,
             None, self._debug_reload_all_cb),
            ('start-shell', gtk.STOCK_EXECUTE, _('Start _Shell'), None,
             None, self._debug_start_shell_cb),

            # Help
            ('help', None, _('_Help')),
            ('about', gtk.STOCK_ABOUT, _('_About'), None,
             None, self._help_about_cb),
            ]
        uimgr = gtk.UIManager()
        group = gtk.ActionGroup('actions')
        group.add_actions(actions)
        uimgr.insert_action_group(group, 0)
        uimgr.add_ui_from_string(MAIN_UI)
        window.add_accel_group(uimgr.get_accel_group())
        menubar = uimgr.get_widget('/menubar')
        vbox.pack_start(menubar, expand=False)
        vbox.reorder_child(menubar, 0)

        toolbar = uimgr.get_widget('/toolbar')
        toolbar.set_icon_size(gtk.ICON_SIZE_SMALL_TOOLBAR)
        toolbar.set_style(gtk.TOOLBAR_ICONS)
        vbox.pack_start(toolbar, expand=False)
        vbox.reorder_child(toolbar, 1)

        menubar.show_all()

        self._actiongroup = group
        self._uimgr = uimgr
        self._start_component_action = group.get_action("start-component")
        self._stop_component_action = group.get_action("stop-component")
        self._delete_component_action = group.get_action("delete-component")
        self._stop_all_action = group.get_action("stop-all")
        self._start_all_action = group.get_action("start-all")
        self._clear_all_action = group.get_action("clear-all")

        self._trayicon = trayicon.FluTrayIcon(window)
        self._trayicon.connect("quit", self._trayicon_quit_cb)
        self._trayicon.set_tooltip(_('Not connected'))

        # the widget containing the component view
        self._component_view = widgets['component_view']

        self.components_view = parts.ComponentsView(widgets['components_view'])
        self.components_view.connect('selection_changed',
            self._components_view_selection_changed_cb)
        self.components_view.connect('activated',
            self._components_view_activated_cb)
        self.statusbar = parts.AdminStatusbar(widgets['statusbar'])
        self._update_component_actions()
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
        if self._recent_menu_uid:
            self._uimgr.remove_ui(self._recent_menu_uid)
            self._uimgr.ensure_update()

        def recent_activate(action, conn):
            self._open_connection(conn['info'])

        ui = ""
        for conn in connections.get_recent_connections()[:MAX_RECENT_ITEMS]:
            name = conn['name']
            ui += '<menuitem action="%s"/>' % name
            action = gtk.Action(name, name, '', '')
            action.connect('activate', recent_activate, conn)
            self._actiongroup.add_action(action)

        self._recent_menu_uid = self._uimgr.add_ui_from_string(
            RECENT_UI_TEMPLATE % ui)

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

        def _wizard_finished_cb(wizard, configuration):
            wizard.destroy()
            self._dump_config(configuration)
            self._admin.loadConfiguration(configuration)
            self.show()

        def nullwizard(*args):
            self._wizard = None

        state = self._admin.getWorkerHeavenState()
        if not state.get('names'):
            self._error(
                _('The wizard cannot be run because no workers are logged in.'))
            return

        from flumotion.wizard.configurationwizard import ConfigurationWizard
        wizard = ConfigurationWizard(self._window, self._admin)
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
            self.setAdminModel(model)
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

    def _update_component_actions(self):
        state = self._current_component_state
        if state:
            moodname = moods.get(state.get('mood')).name
            can_start = moodname == 'sleeping'
            can_stop = moodname != 'sleeping'
        else:
            can_start = False
            can_stop = False
        can_delete = bool(state and not can_stop)
        can_start_all = self.components_view.get_property('can-start-any')
        can_stop_all = self.components_view.get_property('can-stop-any')
        # they're all in sleeping or lost
        can_clear_all = can_start_all and not can_stop_all

        self._stop_all_action.set_sensitive(can_stop_all)
        self._start_all_action.set_sensitive(can_start_all)
        self._clear_all_action.set_sensitive(can_clear_all)
        self._start_component_action.set_sensitive(can_start)
        self._stop_component_action.set_sensitive(can_stop)
        self._delete_component_action.set_sensitive(can_delete)
        self.debug('can start %r, can stop %r' % (can_start, can_stop))

    def _update_components(self):
        self.components_view.update(self._components)
        self._trayicon.update(self._components)

    def _clear_messages(self):
        self._messages_view.clear()
        pstate = self._planetState
        if pstate and pstate.hasKey('messages'):
            for message in pstate.get('messages').values():
                self._messages_view.add_message(message)

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
            self._error("%s." % failure.getErrorMessage())
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
        self._update_component_actions()

    def _component_reload(self, state):
        name = getComponentLabel(state)

        dialog = dialogs.ProgressDialog("Reloading",
            _("Reloading component code for %s") % name, self._window)
        d = self._admin.callRemote('reloadComponent', state)
        d.addCallback(lambda result, dlg: dlg.destroy(), dialog)
        # FIXME: better error handling
        d.addErrback(lambda failure, dlg: dlg.destroy(), dialog)
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

    def _component_kill(self, state):
        workerName = state.get('workerRequested')
        avatarId = common.componentId(state.get('parent').get('name'),
                                      state.get('name'))
        self._admin.callRemote('workerCallRemote', workerName, 'killJob',
                               avatarId)

    def _component_do(self, state, action, doing, done,
        remoteMethodPrefix="component"):
        """
        @param remoteMethodPrefix: prefix for remote method to run
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

    def _component_activate(self, state, action):
        self.debug('action %s on component %s' % (action,
                                                  state.get('name')))
        method_name = '_component_' + action
        if hasattr(self, method_name):
            getattr(self, method_name)(state)
        else:
            self.warning("No method '%s' implemented" % method_name)

    def _component_selection_changed(self, state):
        self.debug('component %s has selection', state)
        def compSet(state, key, value):
            if key == 'mood':
                self._update_component_actions()

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

        self._update_component_actions()
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

    def _connection_opened(self, admin):
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

        self._set_planet_state(admin.planet)

        if not self._components:
            self.debug('no components detected, running wizard')
            # ensure our window is shown
            self.show()
            self._run_wizard()

    def _connection_lost(self):
        self._components = {}
        self._update_components()
        self._clear_messages()
        if self._planetState:
            self._planetState.removeListener(self)
            self._planetState = None

        def response(dialog, id):
            if id == gtk.RESPONSE_CANCEL:
                # FIXME: notify admin of cancel
                dialog.destroy()
                return
            elif id == 1:
                self._admin.reconnect()

        message = _("Lost connection to manager, reconnecting ...")
        d = gtk.MessageDialog(self._window, gtk.DIALOG_DESTROY_WITH_PARENT,
            gtk.MESSAGE_WARNING, gtk.BUTTONS_NONE, message)
        # FIXME: move this somewhere
        RESPONSE_REFRESH = 1
        d.add_button(gtk.STOCK_REFRESH, RESPONSE_REFRESH)
        d.add_button(gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL)
        d.connect("response", response)
        d.show_all()
        self._disconnected_dialog = d

    def _connection_refused(self):
        def refused_later():
            message = _("Connection to manager on %s was refused.") % \
                self._admin.connectionInfoStr()
            self._trayicon.set_tooltip(_("Connection to %s was refused") %
                self._admin.adminInfoStr())
            self.info(message)
            d = dialogs.ErrorDialog(message, self)
            d.show_all()
            d.connect('response', self._close)

        log.debug('adminclient', "handling connection-refused")
        reactor.callLater(0, refused_later)
        log.debug('adminclient', "handled connection-refused")

    def _connection_failed(self, reason):
        def failed_later():
            message = (
                _("Connection to manager on %(conn)s failed (%(reason)s).") % {
                    'conn': self._admin.connectionInfoStr(),
                    'reason': reason,
                })
            self._trayicon.set_tooltip("Connection to %s failed" %
                self._admin.adminInfoStr())
            self.info(message)
            d = dialogs.ErrorDialog(message, self._window)
            d.show_all()
            d.connect('response', self._close)

        log.debug('adminclient', "handling connection-failed")
        reactor.callLater(0, failed_later)
        log.debug('adminclient', "handled connection-failed")

    def _error(self, message):
        d = dialogs.ErrorDialog(message, self._window,
                                close_on_response=True)
        d.show_all()

    def _open_recent_connection(self):
        d = gtkconnections.ConnectionsDialog(self._window)

        def on_have_connection(d, connectionInfo):
            d.destroy()
            self._open_connection(connectionInfo)

        d.connect('have-connection', on_have_connection)
        d.show()

    def _open_existing_connection(self):
        from flumotion.admin.gtk import greeter
        from flumotion.admin.gtk.wizard import WizardCancelled
        wiz = greeter.ConnectExisting()

        def got_state(state, g):
            g.set_sensitive(False)
            authenticator = fpb.Authenticator(username=state['user'],
                                              password=state['passwd'])
            info = connection.PBConnectionInfo(state['host'], state['port'],
                                               not state['use_insecure'],
                                               authenticator)
            g.destroy()
            self._open_connection(info)

        def cancel(failure):
            failure.trap(WizardCancelled)
            wiz.stop()

        d = wiz.run_async()
        d.addCallback(got_state, wiz)
        d.addErrback(cancel)

    def _import_configuration(self):
        d = gtk.FileChooserDialog(_("Import Configuration..."), self._window,
                                  gtk.FILE_CHOOSER_ACTION_OPEN,
                                  (gtk.STOCK_CANCEL, gtk.RESPONSE_REJECT,
                                   gtk.STOCK_OK, gtk.RESPONSE_ACCEPT))
        d.set_default_response(gtk.RESPONSE_ACCEPT)

        def response(d, response):
            if response == gtk.RESPONSE_ACCEPT:
                name = d.get_filename()
                conf_xml = open(name, 'r').read()
                self._admin.loadConfiguration(conf_xml)
            d.destroy()

        d.connect('response', response)
        d.show()

    def _export_configuration(self):
        d = gtk.FileChooserDialog(_("Export Configuration..."), self._window,
                                  gtk.FILE_CHOOSER_ACTION_SAVE,
                                  (gtk.STOCK_CANCEL, gtk.RESPONSE_REJECT,
                                   gtk.STOCK_OK, gtk.RESPONSE_ACCEPT))
        d.set_default_response(gtk.RESPONSE_ACCEPT)

        def get_configuration(conf_xml, name, chooser):
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
                doc = FromXml(conf_xml.encode("utf-16"))
                PrettyPrint(doc, f)
                f.close()
                chooser.destroy()

        def response(d, response):
            if response == gtk.RESPONSE_ACCEPT:
                deferred = self._admin.getConfiguration()
                name = d.get_filename()
                deferred.addCallback(get_configuration, name, d)
            else:
                d.destroy()

        d.connect('response', response)
        d.show()

    def _reload_manager(self):
        return self._admin.callRemote('reloadManager')

    def _reload_admin(self):
        self.info('Reloading admin code')
        from flumotion.common.reload import reload as freload
        freload()
        self.info('Reloaded admin code')

    def _reload_all(self):
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
            self._error(
                _("Could not reload component:\n%s.") %
                failure.getErrorMessage())
            return None

        def _defaultErrback(failure):
            self.warning('Errback: unhandled failure: %s' %
                failure.getErrorMessage())
            return failure

        def _callLater():
            d = maybeDeferred(self._reload_admin)
            d.addCallback(lambda _: self._reload_manager())
            # stack callbacks so that a new one only gets sent after the
            # previous one has completed
            for c in self._components.values():
                # FIXME: race condition if components log in or out.
                d.addCallback(lambda _, c: self._component_reload(c), c)
            d.addCallback(_stopCallback)
            d.addErrback(_syntaxErrback)
            d.addErrback(_defaultErrback)
            # FIXME: errback to close the reloading dialog?

        def _reloadCallback(admin, text):
            dialog.message(_("Reloading %s code") % text)

        self._admin.connect('reloading', _reloadCallback)
        dialog.start()
        reactor.callLater(0.2, _callLater)

    def _start_shell(self):
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

    def _about(self):
        about = dialogs.AboutDialog(self._window)
        about.run()
        about.destroy()

    ### admin model callbacks

    def _admin_connected_cb(self, admin):
        self._connection_opened(admin)

    def _admin_disconnected_cb(self, admin):
        self._connection_lost()

    def _admin_connection_refused_cb(self, admin):
        self._connection_refused()

    def _admin_connection_failed_cb(self, admin, reason):
        self._connection_failed(admin, reason)

    def _admin_update_cb(self, admin):
        self._update_components()

    ### ui callbacks

    def _window_delete_event_cb(self, window, event):
        self._close()

    def _trayicon_quit_cb(self, trayicon):
        self._close()

    def _components_view_selection_changed_cb(self, view, state):
        self._component_selection_changed(state)

    def _components_view_activated_cb(self, view, state, action):
        self._component_activate(state, action)

    def _component_view_start_stop_notify_cb(self, *args):
        self._update_component_actions()

    ### action callbacks

    def _connection_open_recent_cb(self, action):
        self._open_recent_connection()

    def _connection_open_existing_cb(self, action):
        self._open_existing_connection()

    def _connection_import_configuration_cb(self, action):
        self._import_configuration()

    def _connection_export_configuration_cb(self, action):
        self._export_configuration()

    def _connection_quit_cb(self, action):
        self._close()

    def _manage_start_component_cb(self, action):
        self._component_start(None)

    def _manage_stop_component_cb(self, action):
        self._component_stop(None)

    def _manage_delete_component_cb(self, action):
        self._component_delete(None)

    def _manage_start_all_cb(self, action):
        for c in self._components.values():
            self._component_start(c)

    def _manage_stop_all_cb(self, action):
        for c in self._components.values():
            self._component_stop(c)

    def _manage_clear_all_cb(self, action):
        self._admin.cleanComponents()

    def _manage_run_wizard_cb(self, action):
        self._run_wizard()

    def _debug_reload_manager_cb(self, action):
        self._reload_manager()

    def _debug_reload_admin_cb(self, action):
        self._reload_admin()

    def _debug_reload_all_cb(self, action):
        self._reload_all()

    def _debug_start_shell_cb(self, action):
        self._start_shell()

    def _help_about_cb(self, action):
        self._about()

pygobject.type_register(Window)

__version__ = "$Rev$"
