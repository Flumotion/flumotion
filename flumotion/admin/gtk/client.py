# -*- Mode: Python -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# Flumotion - a streaming media server
# Copyright (C) 2004,2005,2006,2007,2008 Fluendo, S.L. (www.fluendo.com).
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
from gtk import glade
from twisted.internet import reactor
from zope.interface import implements

from flumotion.admin.admin import AdminModel
from flumotion.admin.connections import get_recent_connections
from flumotion.admin.gtk.dialogs import AboutDialog, ErrorDialog, \
     ProgressDialog, showConnectionErrorDialog
from flumotion.admin.gtk.connections import ConnectionsDialog
from flumotion.admin.gtk.parts import getComponentLabel, ComponentsView, \
     AdminStatusbar
from flumotion.configure import configure
from flumotion.common.connection import PBConnectionInfo
from flumotion.common.errors import ConnectionRefusedError, \
     ConnectionFailedError
from flumotion.common.i18n import gettexter
from flumotion.common.log import Loggable
from flumotion.common.planet import AdminComponentState, moods
from flumotion.common.pygobject import gsignal
from flumotion.manager import admin # Register types
from flumotion.twisted.flavors import IStateListener
from flumotion.ui.trayicon import FluTrayIcon
from flumotion.wizard.models import Porter

admin # pyflakes

__version__ = "$Rev$"
_ = gettext.gettext
T_ = gettexter()

MAIN_UI = """
<ui>
  <menubar name="Menubar">
    <menu action="Connection">
      <menuitem action="OpenRecent"/>
      <menuitem action="OpenExisting"/>
      <menuitem action="ImportConfig"/>
      <menuitem action="ExportConfig"/>
      <separator name="sep-conn1"/>
      <placeholder name="Recent"/>
      <separator name="sep-conn2"/>
      <menuitem action="Quit"/>
    </menu>
    <menu action="Manage">
      <menuitem action="StartComponent"/>
      <menuitem action="StopComponent"/>
      <menuitem action="DeleteComponent"/>
      <separator name="sep-manage1"/>
      <menuitem action="StartAll"/>
      <menuitem action="StopAll"/>
      <menuitem action="ClearAll"/>
      <separator name="sep-manage2"/>
      <menuitem action="AddFormat"/>
      <separator name="sep-manage3"/>
      <menuitem action="RunConfigurationWizard"/>
    </menu>
    <menu action="Debug">
      <menuitem action="EnableDebugging"/>
      <separator name="sep-debug1"/>
      <menuitem action="StartShell"/>
      <menuitem action="DumpConfiguration"/>
    </menu>
    <menu action="Help">
      <menuitem action="About"/>
    </menu>
  </menubar>
  <toolbar name="Toolbar">
    <toolitem action="OpenRecent"/>
    <separator name="sep-toolbar1"/>
    <toolitem action="StartComponent"/>
    <toolitem action="StopComponent"/>
    <toolitem action="DeleteComponent"/>
    <separator name="sep-toolbar2"/>
    <toolitem action="RunConfigurationWizard"/>
  </toolbar>
</ui>
"""

RECENT_UI_TEMPLATE = '''<ui>
  <menubar name="Menubar">
    <menu action="Connection">
      <placeholder name="Recent">
      %s
      </placeholder>
    </menu>
  </menubar>
</ui>'''

MAX_RECENT_ITEMS = 4


class AdminClientWindow(Loggable, gobject.GObject):
    '''Creates the GtkWindow for the user interface.
    Also connects to the manager on the given host and port.
    '''

    implements(IStateListener)

    logCategory = 'adminview'
    gsignal('connected')

    def __init__(self):
        gobject.GObject.__init__(self)

        self._trayicon = None
        self._currentComponentStates = None
        self._disconnectedDialog = None # set to a dialog when disconnected
        self._planetState = None
        self._components = None # name -> planet.AdminComponentState
        self._admin = None
        self._widgets = {}
        self._window = None
        self._recentMenuID = None
        self._debugEnabled = False
        self._debugActions = None
        self._debugEnableAction = None
        self._componentView = None
        
        self._createUI()
        self._appendRecentConnections()

    # Public API

    #FIXME: This function may not be called ever.
    # It has not been properly tested
    # with the multiselection (ticket #795).
    # A ticket for reviewing that has been opened #961

    def stateSet(self, state, key, value):
        # called by model when state of something changes
        if not isinstance(state, AdminComponentState):
            return

        if key == 'message':
            self.statusbar.set('main', value)
        elif key == 'mood':
            self._updateComponentActions()
            current = self.components_view.get_selected_names()
            if value == moods.sleeping.value:
                if state.get('name') in current:
                    self._messages_view.clear_message(value.id)

    #FIXME: This function may not be called ever.
    # It has not been properly tested
    # with the multiselection (ticket #795).
    # A ticket for reviewing that has been opened #961

    def componentCallRemoteStatus(self, state, pre, post, fail,
                                  methodName, *args, **kwargs):

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
        if not state:
            states = self.components_view.get_selected_states()
            if not states:
                return
            for state in states:
                self.componentCallRemoteStatus(state, pre, post, fail,
                                                methodName, args, kwargs)
        else:
            label = getComponentLabel(state)
            if not label:
                return

            mid = None
            if pre:
                mid = self.statusbar.push('main', pre % label)
            d = self._admin.componentCallRemote(state, methodName, *args,
                                                 **kwargs)
            d.addCallback(cb, self, mid)
            d.addErrback(eb, self, mid)

    def componentCallRemote(self, state, methodName, *args, **kwargs):
        self.componentCallRemoteStatus(None, None, None, None,
                                       methodName, *args, **kwargs)

    def whsAppend(self, state, key, value):
        if key == 'names':
            self.statusbar.set(
                'main', _('Worker %s logged in.') % value)

    def whsRemove(self, state, key, value):
        if key == 'names':
            self.statusbar.set(
                'main', _('Worker %s logged out.') % value)

    def show(self):
        self._window.show()

    def setDebugEnabled(self, enabled):
        """Set if debug should be enabled for the admin client window
        @param enable: if debug should be enabled
        """
        self._debugEnabled = enabled
        self._debugActions.set_sensitive(enabled)
        self._debugEnableAction.set_active(enabled)
        self._componentView.setDebugEnabled(enabled)

    def getWindow(self):
        """Get the gtk window for the admin interface
        @returns: window
        @rtype: gtk.Window
        """
        return self._window

    def openConnection(self, info):
        """Connects to a manager given a connection info
        @param info: connection info
        @type info: L{PBConnectionInfo}
        """
        assert isinstance(info, PBConnectionInfo), info
        return self._openConnection(info)

    # Private

    def _createUI(self):
        self.debug('creating UI')
        # returns the window
        # called from __init__
        wtree = glade.XML(os.path.join(configure.gladedir, 'admin.glade'))
        wtree.signal_autoconnect(self)

        widgets = self._widgets
        for widget in wtree.get_widget_prefix(''):
            widgets[widget.get_name()] = widget

        window = self._window = widgets['main_window']
        window.set_name("AdminWindow")
        vbox = widgets['vbox1']
        window.connect('delete-event', self._window_delete_event_cb)

        uimgr = gtk.UIManager()
        uimgr.connect('connect-proxy',
                      self._on_uimanager__connect_proxy)
        uimgr.connect('disconnect-proxy',
                      self._on_uimanager__disconnect_proxy)

        # Normal actions
        group = gtk.ActionGroup('Actions')
        group.add_actions([
            # Connection
            ('Connection', None, _("_Connection")),
            ('OpenRecent', gtk.STOCK_OPEN, _('_Open Recent Connection...'),
              None, _('Connect to a recently used connection'),
             self._connection_open_recent_cb),
            ('OpenExisting', None, _('Connect to _running manager...'), None,
             _('Connect to an previously used connection'),
             self._connection_open_existing_cb),
            ('ImportConfig', None, _('_Import Configuration...'), None,
             _('Import configuration from a file'),
             self._connection_import_configuration_cb),
            ('ExportConfig', None, _('_Export Configuration...'), None,
             _('Export current configuration to a file'),
             self._connection_export_configuration_cb),
            ('Quit', gtk.STOCK_QUIT, _('_Quit'), None,
             _('Quit the application and disconnect from the manager'),
             self._connection_quit_cb),

            # Manage
            ('Manage', None, _('_Manage')),
            ('StartComponent', 'flumotion-play', _('_Start Component(s)'),
              None, _('Start the selected component(s)'),
             self._manage_start_component_cb),
            ('StopComponent', 'flumotion-stop', _('St_op Component(s)'),
              None, _('Stop the selected component(s)'),
             self._manage_stop_component_cb),
            ('DeleteComponent', gtk.STOCK_DELETE, _('_Delete Component(s)'),
              None, _('Delete the selected component(s)'),
             self._manage_delete_component_cb),
            ('StartAll', None, _('Start _All'), None,
             _('Start all components'),
             self._manage_start_all_cb),
            ('StopAll', None, _('Stop A_ll'), None,
             _('Stop all components'),
             self._manage_stop_all_cb),
            ('ClearAll', gtk.STOCK_CLEAR, _('_Clear All'), None,
             _('Remove all components'),
             self._manage_clear_all_cb),
            ('AddFormat', gtk.STOCK_ADD, _('Add new _format..'), None,
             _('Add a new format to the current stream'),
             self._manage_add_format_cb),
            ('RunConfigurationWizard', 'flumotion-wizard', _('Run _Wizard'), None,
             _('Run the configuration wizard'),
             self._manage_run_wizard_cb),

            # Debug
            ('Debug', None, _('_Debug')),

            # Help
            ('Help', None, _('_Help')),
            ('About', gtk.STOCK_ABOUT, _('_About'), None,
             _('Displays an about dialog'),
             self._help_about_cb),
            ])
        group.add_toggle_actions([
            ('EnableDebugging', None, _('Enable _Debugging'), None,
             _('Enable debugging in the admin interface'),
             self._debug_enable_cb),
            ])
        self._debugEnableAction = group.get_action('EnableDebugging')
        uimgr.insert_action_group(group, 0)

        # Debug actions
        self._debugActions = gtk.ActionGroup('Actions')
        self._debugActions.add_actions([
            # Debug
            ('StartShell', gtk.STOCK_EXECUTE, _('Start _Shell'), None,
             _('Start an interactive debugging shell'),
             self._debug_start_shell_cb),
            ('DumpConfiguration', gtk.STOCK_EXECUTE,
	     _('Dump configuration'), None,
             _('Dumps the current manager configuration'),
             self._debug_dump_configuration_cb),
            ])
        uimgr.insert_action_group(self._debugActions, 0)
        self._debugActions.set_sensitive(False)

        uimgr.add_ui_from_string(MAIN_UI)
        window.add_accel_group(uimgr.get_accel_group())

        menubar = uimgr.get_widget('/Menubar')
        vbox.pack_start(menubar, expand=False)
        vbox.reorder_child(menubar, 0)

        toolbar = uimgr.get_widget('/Toolbar')
        toolbar.set_icon_size(gtk.ICON_SIZE_SMALL_TOOLBAR)
        toolbar.set_style(gtk.TOOLBAR_ICONS)
        vbox.pack_start(toolbar, expand=False)
        vbox.reorder_child(toolbar, 1)

        menubar.show_all()

        self._actiongroup = group
        self._uimgr = uimgr
        self._startComponentAction = group.get_action("StartComponent")
        self._stopComponentAction = group.get_action("StopComponent")
        self._deleteComponentAction = group.get_action("DeleteComponent")
        self._stopAllAction = group.get_action("StopAll")
        assert self._stopAllAction
        self._startAllAction = group.get_action("StartAll")
        assert self._startAllAction
        self._clearAllAction = group.get_action("ClearAll")
        assert self._clearAllAction
        self._addFormatAction = group.get_action("AddFormat")
        assert self._addFormatAction

        self._trayicon = FluTrayIcon(window)
        self._trayicon.connect("quit", self._trayicon_quit_cb)
        self._trayicon.set_tooltip(_('Not connected'))

        # the widget containing the component view
        self._componentView = widgets['component_view']

        self.components_view = ComponentsView(widgets['components_view'])
        self.components_view.connect('selection_changed',
            self._components_view_selection_changed_cb)
        self.components_view.connect('activated',
            self._components_view_activated_cb)
        self.statusbar = AdminStatusbar(widgets['statusbar'])
        self._updateComponentActions()
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

    def _on_uimanager__connect_proxy(self, uimgr, action, widget):
        tooltip = action.get_property('tooltip')
        if not tooltip:
            return

        if isinstance(widget, gtk.MenuItem):
            cid = widget.connect('select', self._on_menu_item__select,
                                 tooltip)
            cid2 = widget.connect('deselect', self._on_menu_item__deselect)
            widget.set_data('pygtk-app::proxy-signal-ids', (cid, cid2))
        elif isinstance(widget, gtk.ToolButton):
            cid = widget.child.connect('enter', self._on_tool_button__enter,
                                       tooltip)
            cid2 = widget.child.connect('leave', self._on_tool_button__leave)
            widget.set_data('pygtk-app::proxy-signal-ids', (cid, cid2))

    def _on_uimanager__disconnect_proxy(self, uimgr, action, widget):
        cids = widget.get_data('pygtk-app::proxy-signal-ids')
        if not cids:
            return

        if isinstance(widget, gtk.ToolButton):
            widget = widget.child

        for name, cid in cids:
            widget.disconnect(cid)

    def _on_menu_item__select(self, menuitem, tooltip):
        self.statusbar.push('main', tooltip)

    def _on_menu_item__deselect(self, menuitem):
        self.statusbar.pop('main')

    def _on_tool_button__enter(self, toolbutton, tooltip):
        self.statusbar.push('main', tooltip)

    def _on_tool_button__leave(self, toolbutton):
        self.statusbar.pop('main')

    def _setAdminModel(self, model):
        'set the model to which we are a view/controller'
        # it's ok if we've already been connected
        self.debug('setting model')

        if self._admin:
            self.debug('Connecting to new model %r' % model)

        self._admin = model

        # window gets created after model connects initially, so check
        # here
        if self._admin.isConnected():
            self._connectionOpened(model)

        self._admin.connect('connected', self._admin_connected_cb)
        self._admin.connect('disconnected', self._admin_disconnected_cb)
        self._admin.connect('connection-refused',
                           self._admin_connection_refused_cb)
        self._admin.connect('connection-failed',
                           self._admin_connection_failed_cb)
        self._admin.connect('update', self._admin_update_cb)

    def _openConnection(self, info):
        self._trayicon.set_tooltip(_("Connecting to %s:%s") % (
            info.host, info.port))

        def connected(model):
            self._setAdminModel(model)
            self._appendRecentConnections()

        model = AdminModel()
        d = model.connectToManager(info)
        d.addCallback(connected)
        return d

    def _openConnectionInternal(self, info):
        d = self._openConnection(info)

        def errorMessageDisplayed(unused):
            self._window.set_sensitive(True)

        def connected(model):
            self._window.set_sensitive(True)

        def errbackConnectionRefusedError(failure):
            failure.trap(ConnectionRefusedError)
            d = showConnectionErrorDialog(failure, info, parent=self._window)
            d.addCallback(errorMessageDisplayed)

        def errbackConnectionFailedError(failure):
            failure.trap(ConnectionFailedError)
            d = showConnectionErrorDialog(failure, info, parent=self._window)
            d.addCallback(errorMessageDisplayed)
            return d

        d.addCallback(connected)
        d.addErrback(errbackConnectionRefusedError)
        d.addErrback(errbackConnectionFailedError)
        self._window.set_sensitive(False)
        return d

    def _appendRecentConnections(self):
        if self._recentMenuID:
            self._uimgr.remove_ui(self._recentMenuID)
            self._uimgr.ensure_update()

        def recent_activate(action, conn):
            self._openConnectionInternal(conn.info)

        ui = ""
        for conn in get_recent_connections()[:MAX_RECENT_ITEMS]:
            name = conn.host
            ui += '<menuitem action="%s"/>' % name
            action = gtk.Action(name, name,
                                _('Connect to the manager on %s') % conn.host,
                                '')
            action.connect('activate', recent_activate, conn)
            self._actiongroup.add_action(action)

        self._recentMenuID = self._uimgr.add_ui_from_string(
            RECENT_UI_TEMPLATE % ui)

    def _quit(self):
        """Quitting the application in a controlled manner"""
        self._clear_admin()
        self._close()

    def _close(self, *args):
        reactor.stop()

    def _dumpConfig(self, configation):
        import pprint
        import cStringIO
        fd = cStringIO.StringIO()
        pprint.pprint(configation, fd)
        fd.seek(0)
        self.debug('Configuration=%s' % fd.read())

    def _error(self, message):
        d = ErrorDialog(message, self._window,
                        close_on_response=True)
        d.show_all()

    def _fatal_error(self, message, tray=None):
        if tray:
            self._trayicon.set_tooltip(tray)

        self.info(message)
        d = ErrorDialog(message, self._window)
        d.show_all()
        d.connect('response', self._close)

    def _wizardFinshed(self, wizard, configuration):
        wizard.destroy()
        self._dumpConfig(configuration)
        self._admin.loadConfiguration(configuration)

        self._updateComponentActions()
        self.show()

    def _getHTTPPorter(self):
        porters = []
        for state in self.components_view.getComponentStates():
            config = state.get('config')
            if config['type'] == 'porter':
                porters.append(config)

        if len(porters) != 1:
            return
        config = porters[0]
        properties = config['properties']
        porter = Porter(worker=None,
                        port=properties['port'],
                        username=properties['username'],
                        password=properties['password'],
                        socketPath=properties['socket-path'])
        porter.exists = True
        return porter
    
    def _runAddNewFormatWizard(self):
        from flumotion.admin.gtk.addformatwizard import AddFormatWizard
        wizard = AddFormatWizard(self._window)
        for state in self.components_view.getComponentStates():
            componentName = state.get('name')
            # FIXME: This is not completely correct, we should instead:
            #        Provide a new wizard page which allows the user to select
            #        the producers he wants to use when adding a new format
            if componentName == 'producer-audio':
                component = wizard.setAudioProducer(componentName,
                                                    state.get('type'))
            elif componentName == 'producer-video':
                component = wizard.setVideoProducer(componentName,
                                                    state.get('type'))
            else:
                continue
            
            # Move over the properties from the configuration dict.
            config = state.get('config')
            for key, value in config['properties'].items():
                component.properties[key] = value
        self._runWizard(wizard)

    def _runConfigurationWizard(self):
        from flumotion.wizard.configurationwizard import ConfigurationWizard
        wizard = ConfigurationWizard(self._window)
        self._runWizard(wizard)

    def _runWizard(self, wizard):
        workerHeavenState = self._admin.getWorkerHeavenState()
        if not workerHeavenState.get('names'):
            self._error(
                _('The wizard cannot be run because no workers are'
                  'logged in.'))
            return

        wizard.setExistingComponentNames(
            self.components_view.getComponentNames())
        wizard.setAdminModel(self._admin)
        wizard.setWorkerHeavenState(workerHeavenState)
        httpPorter = self._getHTTPPorter()
        if httpPorter:
            wizard.setHTTPPorter(httpPorter)
        wizard.connect('finished', self._wizard_finished_cb)
        wizard.run(main=False)

    def _clear_admin(self):
        if not self._admin:
            return

        self._admin.disconnect_by_func(self._admin_connected_cb)
        self._admin.disconnect_by_func(self._admin_disconnected_cb)
        self._admin.disconnect_by_func(self._admin_connection_refused_cb)
        self._admin.disconnect_by_func(self._admin_connection_failed_cb)
        self._admin.disconnect_by_func(self._admin_update_cb)
        self._admin = None

    def _updateComponentActions(self):
        canStart = self.components_view.can_start()
        canStop = self.components_view.can_stop()
        canDelete = bool(self._currentComponentStates and canStart)
        self._startComponentAction.set_sensitive(canStart)
        self._stopComponentAction.set_sensitive(canStop)
        self._deleteComponentAction.set_sensitive(canDelete)
        self.debug('can start %r, can stop %r' % (canStart, canStop))
        canStartAll = self.components_view.get_property('can-start-any')
        canStopAll = self.components_view.get_property('can-stop-any')

        # they're all in sleeping or lost
        canClearAll = canStartAll and not canStopAll
        self._stopAllAction.set_sensitive(canStopAll)
        self._startAllAction.set_sensitive(canStartAll)
        self._clearAllAction.set_sensitive(canClearAll)

        hasProducer = self._hasProducerComponent()
        self._addFormatAction.set_sensitive(hasProducer)

    def _updateComponents(self):
        self.components_view.update(self._components)
        self._trayicon.update(self._components)

    def _hasProducerComponent(self):
        for state in self.components_view.getComponentStates():
            if state is None:
                continue
            # FIXME: Not correct, should expose wizard state from
            #        the registry.
            name = state.get('name')
            if 'producer' in name:
                return True
        return False

    def _clearMessages(self):
        self._messages_view.clear()
        pstate = self._planetState
        if pstate and pstate.hasKey('messages'):
            for message in pstate.get('messages').values():
                self._messages_view.addmessage(message)

    def _setPlanetState(self, planetState):

        def flowStateAppend(state, key, value):
            self.debug('flow state append: key %s, value %r' % (key, value))
            if key == 'components':
                self._components[value.get('name')] = value
                # FIXME: would be nicer to do this incrementally instead
                self._updateComponents()

        def flowStateRemove(state, key, value):
            if key == 'components':
                self._removeComponent(value)

        def atmosphereStateAppend(state, key, value):
            if key == 'components':
                self._components[value.get('name')] = value
                # FIXME: would be nicer to do this incrementally instead
                self._updateComponents()

        def atmosphereStateRemove(state, key, value):
            if key == 'components':
                self._removeComponent(value)

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

        self._clearMessages()

        a = planetState.get('atmosphere')
        a.addListener(self, append=atmosphereStateAppend,
                      remove=atmosphereStateRemove)
        for c in a.get('components'):
            atmosphereStateAppend(a, 'components', c)

        for f in planetState.get('flows'):
            planetStateAppend(planetState, 'flows', f)

    # component view activation functions

    def _removeComponent(self, state):
        name = state.get('name')
        self.debug('removing component %s' % name)
        del self._components[name]

        # if this component was selected, clear selection
        if self._currentComponentStates and state \
           in self._currentComponentStates:
            self._currentComponentStates.remove(state)
        # FIXME: would be nicer to do this incrementally instead
        self._updateComponents()
        # a component being removed means our selected component could
        # have gone away
        self._updateComponentActions()

    def _componentStop(self, state):
        """
        @returns: a L{twisted.internet.defer.Deferred}
        """
        return self._componentDo(state, 'Stop', 'Stopping', 'Stopped')

    def _componentStart(self, state):
        """
        @returns: a L{twisted.internet.defer.Deferred}
        """
        return self._componentDo(state, 'Start', 'Starting', 'Started')

    def _componentDelete(self, state):
        """
        @returns: a L{twisted.internet.defer.Deferred}
        """
        return self._componentDo(state, '', 'Deleting', 'Deleted',
            'deleteComponent')

    def _componentDo(self, state, action, doing, done,
        remoteMethodPrefix="component"):
        """
        @param remoteMethodPrefix: prefix for remote method to run
        """
        if not state:
            self.debug(" Trying to apply %s to a non component" %action +\
                       " that may mean that the signal comes from the menu ")
            selected_states = self.components_view.get_selected_states()
            self.debug(" selected states %r when %s ", \
                       selected_states, action)
            for selectedState in self.components_view.get_selected_states():
                self._componentDo(selectedState, action, doing, done,
                                  remoteMethodPrefix)
            return
        name = getComponentLabel(state)
        if not name:
            return None

        mid = self.statusbar.push('main',
                                  _("%s component %s") % (doing, name))
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

    def _componentActivate(self, states, action):
        self.debug('action %s on components %r' % (action, states))
        method_name = '_component_' + action
        if hasattr(self, method_name):
            for state in states:
                getattr(self, method_name)(state)
        else:
            self.warning("No method '%s' implemented" % method_name)

    def _componentSelectionChanged(self, states):
        self.debug('component %s has selection', states)

        def compSet(state, key, value):
            if key == 'mood':
                self._updateComponentActions()

        def compAppend(state, key, value):
            name = state.get('name')
            self.debug('stateAppend on component state of %s' % name)
            if key == 'messages':
                current = self.components_view.get_selected_names()
                if name in current:
                    self._messages_view.add_message(value)
                self._messages_view.add_message(value)

        def compRemove(state, key, value):
            name = state.get('name')
            self.debug('stateRemove on component state of %s' % name)
            if key == 'messages':
                current = self.components_view.get_selected_names()
                if name in current:
                    self._messages_view.clear_message(value.id)

        if self._currentComponentStates:
            for current_componentState in self._currentComponentStates:
                current_componentState.removeListener(self)
        self._currentComponentStates = states
        if self._currentComponentStates:
            for current_componentState in self._currentComponentStates:
                current_componentState.addListener(
                self, compSet, compAppend, compRemove)

        self._updateComponentActions()
        self._clearMessages()
        if not states:
            return

        statusbar_message = " "
        if len(states) == 1:
            self.debug("only one component is selected on the components view")
            self._componentView.show_object(states[0])
        else:
            self._componentView.show_object(None)
            self.debug("zero or more than one components are selected on the"+\
                        " components view")
        for state in states:
            name = getComponentLabel(state)
            messages = state.get('messages')
            if messages:
                for m in messages:
                    self.debug('have message %r' % m)
                    self.debug('message id %s' % m.id)
                    self._messages_view.add_message(m)

            if state.get('mood') == moods.sad.value:
                self.debug('component %s is sad' % name)
                statusbar_message = statusbar_message +\
                                    _("Component %s is sad. ") % name
        if statusbar_message:
            self.statusbar.set('main',
                               statusbar_message)


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

    def _connectionOpened(self, admin):
        self.info('Connected to manager')
        if self._disconnectedDialog:
            self._disconnectedDialog.destroy()
            self._disconnectedDialog = None

        # FIXME: have a method for this
        self._window.set_title(_('%s - Flumotion Administration') %
            self._admin.adminInfoStr())
        self._trayicon.set_tooltip(self._admin.adminInfoStr())

        self.emit('connected')

        self._componentView.set_single_admin(admin)

        self._setPlanetState(admin.planet)
        self._updateComponentActions()

        if not self._components:
            self.debug('no components detected, running wizard')
            # ensure our window is shown
            self.show()
            self._runConfigurationWizard()
        else:
            self.show()

    def _show_connectionLost_dialog(self):
        RESPONSE_REFRESH = 1

        def response(dialog, response_id):
            if response_id == RESPONSE_REFRESH:
                self._admin.reconnect()
            else:
                # FIXME: notify admin of cancel
                dialog.stop()
                dialog.destroy()
                return

        dialog = ProgressDialog(
            _("Reconnecting ..."),
            _("Lost connection to manager %s, reconnecting ...")
            % (self._admin.adminInfoStr(), ), self._window)

        dialog.add_button(gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL)
        dialog.add_button(gtk.STOCK_REFRESH, RESPONSE_REFRESH)
        dialog.connect("response", response)
        dialog.start()
        self._disconnectedDialog = dialog

    def _connectionLost(self):
        self._components = {}
        self._updateComponents()
        self._clearMessages()
        if self._planetState:
            self._planetState.removeListener(self)
            self._planetState = None

        self._show_connectionLost_dialog()

    def _connectionRefused(self):

        def refused_later():
            self._fatal_error(
                _("Connection to manager on %s was refused.") % (
                self._admin.connectionInfoStr()),
                _("Connection to %s was refused") % self._admin.adminInfoStr())

        self.debug("handling connection-refused")
        reactor.callLater(0, refused_later)
        self.debug("handled connection-refused")

    def _connectionFailed(self, reason):
        return self._fatal_error(
            _("Connection to manager on %s failed (%s).") % (
            self._admin.connectionInfoStr(), reason),
            _("Connection to %s failed") % self._admin.adminInfoStr())

    def _openRecentConnection(self):
        d = ConnectionsDialog(parent=self._window)

        def on_have_connection(d, connectionInfo):
            d.destroy()
            self._openConnectionInternal(connectionInfo.info)
            connectionInfo.updateTimestamp()

        d.connect('have-connection', on_have_connection)
        d.show()

    def _openExistingConnection(self):
        from flumotion.admin.gtk.greeter import ConnectExisting
        from flumotion.ui.simplewizard import WizardCancelled
        wiz = ConnectExisting(parent=self._window)

        def got_state(state, g):
            g.set_sensitive(False)
            g.destroy()
            self._openConnectionInternal(state['connectionInfo'])

        def cancel(failure):
            failure.trap(WizardCancelled)
            wiz.stop()

        d = wiz.runAsync()
        d.addCallback(got_state, wiz)
        d.addErrback(cancel)

    def _importConfiguration(self):
        dialog = gtk.FileChooserDialog(
            _("Import Configuration..."), self._window,
            gtk.FILE_CHOOSER_ACTION_OPEN,
            (gtk.STOCK_CANCEL, gtk.RESPONSE_REJECT,
             _('Import'), gtk.RESPONSE_ACCEPT))
        dialog.set_modal(True)
        dialog.set_default_response(gtk.RESPONSE_ACCEPT)
        ffilter = gtk.FileFilter()
        ffilter.set_name(_("Flumotion XML Configuration files"))
        ffilter.add_pattern("*.xml")
        dialog.add_filter(ffilter)
        ffilter = gtk.FileFilter()
        ffilter.set_name(_("All files"))
        ffilter.add_pattern("*")
        dialog.add_filter(ffilter)

        def response(dialog, response):
            if response == gtk.RESPONSE_ACCEPT:
                name = dialog.get_filename()
                conf_xml = open(name, 'r').read()
                self._admin.loadConfiguration(conf_xml)
            dialog.destroy()

        dialog.connect('response', response)
        dialog.show()

    def _exportConfiguration(self):
        d = gtk.FileChooserDialog(_("Export Configuration..."), self._window,
                                  gtk.FILE_CHOOSER_ACTION_SAVE,
                                  (gtk.STOCK_CANCEL, gtk.RESPONSE_REJECT,
                                   _('Export'), gtk.RESPONSE_ACCEPT))
        d.set_modal(True)
        d.set_default_response(gtk.RESPONSE_ACCEPT)
        d.set_current_name("configuration.xml")
        
        def getConfiguration(conf_xml, name, chooser):
            if not name.endswith('.xml'):
                name += '.xml'
                
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

        def response(d, response):
            if response == gtk.RESPONSE_ACCEPT:
                deferred = self._admin.getConfiguration()
                name = d.get_filename()
                deferred.addCallback(getConfiguration, name, d)
            else:
                d.destroy()

        d.connect('response', response)
        d.show()

    def _startShell(self):
        if sys.version_info >= (2, 4):
            from flumotion.extern import code
            code # pyflakes
        else:
            import code

        vars = \
            {"admin": self._admin, "components": self._components}
        message = """Flumotion Admin Debug Shell

Local variables are:
  admin      (flumotion.admin.admin.AdminModel)
  components (dict: name -> flumotion.common.planet.AdminComponentState)

You can do remote component calls using:
  admin.componentCallRemote(components['component-name'],
         'methodName', arg1, arg2)

"""
        code.interact(local=vars, banner=message)

    def _dumpConfiguration(self):
        def gotConfiguration(xml):
            print xml
        d = self._admin.getConfiguration()
        d.addCallback(gotConfiguration)

    def _about(self):
        about = AboutDialog(self._window)
        about.run()
        about.destroy()

    ### admin model callbacks

    def _admin_connected_cb(self, admin):
        self._connectionOpened(admin)

    def _admin_disconnected_cb(self, admin):
        self._connectionLost()

    def _admin_connection_refused_cb(self, admin):
        self._connectionRefused()

    def _admin_connection_failed_cb(self, admin, reason):
        self._connectionFailed(reason)

    def _admin_update_cb(self, admin):
        self._updateComponents()

    ### ui callbacks

    def _wizard_finished_cb(self, wizard, configuration):
        self._wizardFinshed(wizard, configuration)

    def _window_delete_event_cb(self, window, event):
        self._quit()

    def _trayicon_quit_cb(self, trayicon):
        self._quit()

    def _components_view_selection_changed_cb(self, view, state):
        self._componentSelectionChanged(state)

    def _components_view_activated_cb(self, view, states, action):
        self._componentActivate(states, action)

    def _component_view_start_stop_notify_cb(self, *args):
        self._updateComponentActions()

    ### action callbacks

    def _connection_open_recent_cb(self, action):
        self._openRecentConnection()

    def _connection_open_existing_cb(self, action):
        self._openExistingConnection()

    def _connection_import_configuration_cb(self, action):
        self._importConfiguration()

    def _connection_export_configuration_cb(self, action):
        self._exportConfiguration()

    def _connection_quit_cb(self, action):
        self._quit()

    def _manage_start_component_cb(self, action):
        self._componentStart(None)

    def _manage_stop_component_cb(self, action):
        self._componentStop(None)

    def _manage_delete_component_cb(self, action):
        self._componentDelete(None)

    def _manage_start_all_cb(self, action):
        for c in self._components.values():
            self._componentStart(c)

    def _manage_stop_all_cb(self, action):
        for c in self._components.values():
            self._componentStop(c)

    def _manage_clear_all_cb(self, action):
        self._admin.cleanComponents()

    def _manage_add_format_cb(self, action):
        self._runAddNewFormatWizard()
        
    def _manage_run_wizard_cb(self, action):
        self._runConfigurationWizard()

    def _debug_enable_cb(self, action):
        self.setDebugEnabled(action.get_active())

    def _debug_start_shell_cb(self, action):
        self._startShell()

    def _debug_dump_configuration_cb(self, action):
        self._dumpConfiguration()
	
    def _help_about_cb(self, action):
        self._about()

gobject.type_register(AdminClientWindow)
