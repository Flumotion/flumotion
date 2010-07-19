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

"""admin window interface, the main interface of flumotion-admin.

Here is an overview of the different parts of the admin interface::

 +--------------[ AdminWindow ]-------------+
 | Menubar                                  |
 +------------------------------------------+
 | Toolbar                                  |
 +--------------------+---------------------+
 |                    |                     |
 |                    |                     |
 |                    |                     |
 |                    |                     |
 |  ComponentList     |   ComponentView     |
 |                    |                     |
 |                    |                     |
 |                    |                     |
 |                    |                     |
 |                    |                     |
 +--------------------+---------------------+
 | AdminStatusbar                           |
 +-------------------------------------------

The main class which builds everything together is a L{AdminWindow},
which is defined in this file:

  - L{AdminWindow} creates the other UI parts internally, see the
    L{AdminWindow._createUI}.
  - Menubar and Toolbar are created by a GtkUIManager, see
    L{AdminWindow._createUI} and L{MAIN_UI}.
  - L{ComponentList<flumotion.admin.gtk.componentlist.ComponentList>}
    is a list of all components, and is created in the
    L{flumotion.admin.gtk.componentlist} module.
  - L{ComponentView<flumotion.admin.gtk.componentview.ComponentView>}
    contains a component specific view, usually a set of tabs, it is
    created in the L{flumotion.admin.gtk.componentview} module.
  - L{AdminStatus<flumotion.admin.gtk.statusbar.AdminStatus>} is a
    statusbar displaying context specific hints and is defined in the
    L{flumotion.admin.gtk.statusbar} module.

"""

import gettext
import os
import sys

import gobject
import gtk
from gtk import gdk
from gtk import keysyms
from kiwi.ui.delegates import GladeDelegate
from kiwi.ui.dialogs import yesno
from twisted.internet import defer, reactor
from zope.interface import implements

from flumotion.admin.admin import AdminModel
from flumotion.admin.assistant.models import AudioProducer, Porter, \
     VideoProducer, Muxer
from flumotion.admin.connections import getRecentConnections, \
     hasRecentConnections
from flumotion.admin.gtk.dialogs import AboutDialog, ErrorDialog, \
     ProgressDialog, showConnectionErrorDialog
from flumotion.admin.gtk.connections import ConnectionsDialog
from flumotion.admin.gtk.componentlist import getComponentLabel, ComponentList
from flumotion.admin.gtk.componentview import MultipleAdminComponentStates
from flumotion.admin.gtk.debugmarkerview import DebugMarkerDialog
from flumotion.admin.gtk.statusbar import AdminStatusbar
from flumotion.common.common import componentId
from flumotion.common.connection import PBConnectionInfo
from flumotion.common.errors import ConnectionCancelledError, \
     ConnectionRefusedError, ConnectionFailedError, BusyComponentError
from flumotion.common.i18n import N_, gettexter
from flumotion.common.log import Loggable
from flumotion.common.planet import AdminComponentState, moods
from flumotion.common.pygobject import gsignal
from flumotion.configure import configure
from flumotion.manager import admin # Register types
from flumotion.twisted.flavors import IStateListener
from flumotion.ui.trayicon import FluTrayIcon

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
      <menuitem action="AddStreamer"/>
      <separator name="sep-manage3"/>
      <menuitem action="RunConfigurationAssistant"/>
    </menu>
    <menu action="Debug">
      <menuitem action="EnableDebugging"/>
      <separator name="sep-debug1"/>
      <menuitem action="StartShell"/>
      <menuitem action="DumpConfiguration"/>
      <menuitem action="WriteDebugMarker"/>
    </menu>
    <menu action="Help">
      <menuitem action="Contents"/>
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
    <toolitem action="RunConfigurationAssistant"/>
  </toolbar>
  <popup name="ComponentContextMenu">
    <menuitem action="StartComponent"/>
    <menuitem action="StopComponent"/>
    <menuitem action="DeleteComponent"/>
    <menuitem action="KillComponent"/>
  </popup>
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


class AdminWindow(Loggable, GladeDelegate):
    '''Creates the GtkWindow for the user interface.
    Also connects to the manager on the given host and port.
    '''

    # GladeDelegate
    gladefile = 'admin.glade'
    toplevel_name = 'main_window'

    # Loggable
    logCategory = 'adminwindow'

    # Interfaces we implement
    implements(IStateListener)

    # Signals
    gsignal('connected')

    def __init__(self):
        GladeDelegate.__init__(self)

        self._adminModel = None
        self._currentComponentStates = None
        self._componentContextMenu = None
        self._componentList = None # ComponentList
        self._componentStates = None # name -> planet.AdminComponentState
        self._componentView = None
        self._componentNameToSelect = None
        self._debugEnabled = False
        self._debugActions = None
        self._debugEnableAction = None
        self._disconnectedDialog = None # set to a dialog when disconnected
        self._planetState = None
        self._recentMenuID = None
        self._trayicon = None
        self._configurationAssistantIsRunning = False
        self._currentDir = None
        self._managerSpawner = None

        self._createUI()
        self._appendRecentConnections()
        self.setDebugEnabled(False)

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
            self.debug('state %r has mood set to %r' % (state, value))
            self._updateComponentActions()
            current = self.components_view.getSelectedNames()
            if value == moods.sleeping.value:
                if state.get('name') in current:
                    self._messageView.clearMessage(value.id)

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
            states = self.components_view.getSelectedStates()
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
            d = self._adminModel.componentCallRemote(
                state, methodName, *args, **kwargs)
            d.addCallback(cb, self, mid)
            d.addErrback(eb, self, mid)

    def componentCallRemote(self, state, methodName, *args, **kwargs):
        self.componentCallRemoteStatus(None, None, None, None,
                                       methodName, *args, **kwargs)

    def whsAppend(self, state, key, value):
        if key == 'names':
            self._componentList.workerAppend(value)
            self._clearLastStatusbarText()
            self._setStatusbarText(_('Worker %s logged in.') % value)

    def whsRemove(self, state, key, value):
        if key == 'names':
            self._componentList.workerRemove(value)
            self._clearLastStatusbarText()
            self._setStatusbarText(_('Worker %s logged out.') % value)

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
        self._killComponentAction.set_property('visible', enabled)

    def getWindow(self):
        """Get the gtk window for the admin interface.

        @returns: window
        @rtype:   L{gtk.Window}
        """
        return self._window

    def openConnection(self, info, managerSpawner=None):
        """Connects to a manager given a connection info.

        @param info: connection info
        @type  info: L{PBConnectionInfo}
        """
        assert isinstance(info, PBConnectionInfo), info
        self._managerSpawner = managerSpawner
        return self._openConnection(info)

    # Private

    def _resize_vpaned(self, widget, minimize):
        if minimize:
            self._eat_resize_id = self._vpaned.connect(
                'button-press-event', self._eat_resize_vpaned_event)
            self._vpaned.set_position(-1)
        else:
            self._vpaned.disconnect(self._eat_resize_id)

    def _eat_resize_vpaned_event(self, *args, **kwargs):
        # Eat button-press-event not to allow resize of the vpaned
        return True

    def _createUI(self):
        self.debug('creating UI')

        # Widgets created in admin.glade
        self._window = self.toplevel
        self._componentList = ComponentList(self.component_list)
        del self.component_list
        self._componentView = self.component_view
        del self.component_view
        self._statusbar = AdminStatusbar(self.statusbar)
        del self.statusbar
        self._messageView = self.messages_view
        del self.messages_view

        self._messageView.connect('resize-event', self._resize_vpaned)
        self._vpaned = self.vpaned
        del self.vpaned
        self._eat_resize_id = self._vpaned.connect(
            'button-press-event', self._eat_resize_vpaned_event)

        self._window.set_name("AdminWindow")
        self._window.connect('delete-event',
                             self._window_delete_event_cb)
        self._window.connect('key-press-event',
                             self._window_key_press_event_cb)

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
             _('Connect to a previously used connection'),
             self._connection_open_existing_cb),
            ('ImportConfig', None, _('_Import Configuration...'), None,
             _('Import a configuration from a file'),
             self._connection_import_configuration_cb),
            ('ExportConfig', None, _('_Export Configuration...'), None,
             _('Export the current configuration to a file'),
             self._connection_export_configuration_cb),
            ('Quit', gtk.STOCK_QUIT, _('_Quit'), None,
             _('Quit the application and disconnect from the manager'),
             self._connection_quit_cb),

            # Manage
            ('Manage', None, _('_Manage')),
            ('StartComponent', gtk.STOCK_MEDIA_PLAY, _('_Start Component(s)'),
              None, _('Start the selected component(s)'),
             self._manage_start_component_cb),
            ('StopComponent', gtk.STOCK_MEDIA_STOP, _('St_op Component(s)'),
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
            ('AddFormat', gtk.STOCK_ADD, _('Add new encoding _format...'),
             None,
             _('Add a new format to the current stream'),
             self._manage_add_format_cb),
             ('AddStreamer', gtk.STOCK_ADD, _('Add new _streamer...'),
             None,
             _('Add a new streamer to the flow'),
             self._manage_add_streamer_cb),
            ('RunConfigurationAssistant', 'flumotion.admin.gtk',
             _('Run _Assistant'), None,
             _('Run the configuration assistant'),
             self._manage_run_assistant_cb),

            # Debug
            ('Debug', None, _('_Debug')),

            # Help
            ('Help', None, _('_Help')),
            ('Contents', gtk.STOCK_HELP, _('_Contents'), 'F1',
             _('Open the Flumotion manual'),
             self._help_contents_cb),
            ('About', gtk.STOCK_ABOUT, _('_About'), None,
             _('About this software'),
             self._help_about_cb),

            # Only in context menu
            ('KillComponent', None, _('_Kill Component'), None,
             _('Kills the currently selected component'),
             self._kill_component_cb),

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
             ('WriteDebugMarker', gtk.STOCK_EXECUTE,
             _('Write debug marker...'), None,
             _('Writes a debug marker to all the logs'),
             self._debug_write_debug_marker_cb)])
        uimgr.insert_action_group(self._debugActions, 0)
        self._debugActions.set_sensitive(False)

        uimgr.add_ui_from_string(MAIN_UI)
        self._window.add_accel_group(uimgr.get_accel_group())

        menubar = uimgr.get_widget('/Menubar')
        self.main_vbox.pack_start(menubar, expand=False)
        self.main_vbox.reorder_child(menubar, 0)

        toolbar = uimgr.get_widget('/Toolbar')
        toolbar.set_icon_size(gtk.ICON_SIZE_SMALL_TOOLBAR)
        toolbar.set_style(gtk.TOOLBAR_ICONS)
        self.main_vbox.pack_start(toolbar, expand=False)
        self.main_vbox.reorder_child(toolbar, 1)

        self._componentContextMenu = uimgr.get_widget('/ComponentContextMenu')
        self._componentContextMenu.show()

        menubar.show_all()

        self._actiongroup = group
        self._uimgr = uimgr
        self._openRecentAction = group.get_action("OpenRecent")
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
        self._addFormatAction.set_sensitive(False)
        self._addStreamerAction = group.get_action("AddStreamer")
        self._addStreamerAction.set_sensitive(False)
        self._runConfigurationAssistantAction = (
            group.get_action("RunConfigurationAssistant"))
        self._runConfigurationAssistantAction.set_sensitive(False)
        self._killComponentAction = group.get_action("KillComponent")
        assert self._killComponentAction

        self._trayicon = FluTrayIcon(self._window)
        self._trayicon.connect("quit", self._trayicon_quit_cb)
        self._trayicon.set_tooltip(_('Flumotion: Not connected'))

        self._componentList.connect('selection_changed',
            self._components_selection_changed_cb)
        self._componentList.connect('show-popup-menu',
                                    self._components_show_popup_menu_cb)

        self._updateComponentActions()
        self._componentList.connect(
            'notify::can-start-any',
            self._components_start_stop_notify_cb)
        self._componentList.connect(
            'notify::can-stop-any',
            self._components_start_stop_notify_cb)
        self._updateComponentActions()

        self._messageView.hide()

    def _connectActionProxy(self, action, widget):
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

    def _disconnectActionProxy(self, action, widget):
        cids = widget.get_data('pygtk-app::proxy-signal-ids')
        if not cids:
            return

        if isinstance(widget, gtk.ToolButton):
            widget = widget.child

        for cid in cids:
            widget.disconnect(cid)

    def _setAdminModel(self, model):
        'set the model to which we are a view/controller'
        # it's ok if we've already been connected
        self.debug('setting model')

        if self._adminModel is not None:
            self._adminModel.disconnectFromManager()
            self.debug('Connecting to new model %r' % model)

        self._adminModel = model

        whs = self._adminModel.getWorkerHeavenState()
        whs.addListener(self, append=self.whsAppend, remove=self.whsRemove)
        for worker in whs.get('names'):
            self._componentList.workerAppend(worker)

        # window gets created after model connects initially, so check
        # here
        if self._adminModel.isConnected():
            self._connectionOpened(model)

        self._adminModel.connect('connected',
                                 self._admin_connected_cb)
        self._adminModel.connect('disconnected',
                                 self._admin_disconnected_cb)
        self._adminModel.connect('update', self._admin_update_cb)

        self._runConfigurationAssistantAction.set_sensitive(True)

    def _openConnection(self, info):
        self._trayicon.set_tooltip(_("Flumotion: Connecting to %s:%s") % (
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

        ui = ""
        connections = getRecentConnections()[:MAX_RECENT_ITEMS]
        for conn in connections:
            name = conn.host
            ui += '<menuitem action="%s"/>' % name
            action = gtk.Action(name, name,
                                _('Connect to the manager on %s') % conn.host,
                                '')
            action.connect('activate', self._recent_action_activate_cb, conn)
            self._actiongroup.add_action(action)

        self._recentMenuID = self._uimgr.add_ui_from_string(
            RECENT_UI_TEMPLATE % ui)
        self._openRecentAction.set_sensitive(len(connections))

    def _quit(self):
        """Quitting the application in a controlled manner"""
        self._clearAdmin()

        def clearAndClose(unused):
            self._close()
        if self._managerSpawner and self._promptForShutdown():
            r = self._managerSpawner.stop(True)
            r.addCallback(clearAndClose)
        else:
            clearAndClose('')

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
        errorDialog = ErrorDialog(message, self._window,
                                  close_on_response=True)
        errorDialog.show()

    def _setStatusbarText(self, text):
        return self._statusbar.push('main', text)

    def _clearLastStatusbarText(self):
        self._statusbar.pop('main')

    def _assistantFinshed(self, assistant, configuration):
        assistant.destroy()
        self._configurationAssistantIsRunning = False
        self._dumpConfig(configuration)
        self._adminModel.loadConfiguration(configuration)
        self._clearMessages()
        self._statusbar.clear(None)
        self._updateComponentActions()
        scenario = assistant.getScenario()
        self._componentNameToSelect = scenario.getSelectComponentName()
        self.show()

    def _getComponentsBy(self, componentType):
        """
        Obtains the components according a given type.

        @param componentType: The type of the components to get
        @type  componentType: str

        @rtype : list of L{flumotion.common.component.AdminComponentState}
        """
        if componentType is None:
            raise ValueError

        componentStates = []

        for state in self._componentStates.values():
            config = state.get('config')
            if componentType and config['type'] == componentType:
                componentStates.append(state)

        return componentStates

    def _getHTTPPorters(self):
        """
        Obtains the porters currently configured on the running flow.

        @rtype : list of L{flumotion.admin.assistant.models.Porter}
        """
        porterList = []
        porterStates = self._getComponentsBy(componentType='porter')

        for porter in porterStates:
            properties = porter.get('config')['properties']
            porterModel = Porter(worker=porter.get('workerName') or
                                        porter.get('workerRequested'),
                                 port=properties['port'],
                                 username=properties['username'],
                                 password=properties['password'],
                                 socketPath=properties['socket-path'])
            porterModel.exists = True
            porterList.append(porterModel)

        return porterList

    def _setMountPoints(self, wizard):
        """
        Sets the mount points currently used on the flow so they can not
        be used for others servers or streamers.

        @param wizard : An assistant that wants to know the used mount_points
        @type  wizard : L{ConfigurationAssistant}
        """
        streamerStates = self._getComponentsBy(componentType='http-streamer')
        serverStates = self._getComponentsBy(componentType='http-server')
        porterStates = self._getComponentsBy(componentType='porter')

        for porter in porterStates:
            properties = porter.get('config')['properties']
            for streamer in streamerStates + serverStates:
                streamerProperties = streamer.get('config')['properties']
                socketPath = streamerProperties['porter-socket-path']

                if socketPath == properties['socket-path']:
                    worker = streamer.get('workerRequested')
                    port = int(properties['port'])
                    mount_point = streamerProperties['mount-point']
                    wizard.addMountPoint(worker, port, mount_point)

    def _createComponentsByAssistantType(self, componentClass, entries):

        def _getComponents():
            for componentState in self._componentStates.values():
                componentType = componentState.get('config')['type']
                for entry in entries:
                    if entry.componentType == componentType:
                        yield (componentState, entry)

        for componentState, entry in _getComponents():
            component = componentClass()
            component.componentType = entry.componentType
            component.description = entry.description
            component.exists = True
            component.name = componentState.get('name')
            config = componentState.get('config')
            for key, value in config['properties'].items():
                component.properties[key] = value
            yield component

    def _runAddNew(self, addition):
        if not self._adminModel.isConnected():
            self._error(
               _('Cannot run assistant without being connected to a manager'))
            return

        from flumotion.admin.gtk.configurationassistant import \
                ConfigurationAssistant

        configurationAssistant = ConfigurationAssistant(self._window)

        def gotWizardEntries(entries):
            entryDict = {}
            for entry in entries:
                entryDict.setdefault(entry.type, []).append(entry)

            if addition == 'format':
                audioProducers = self._createComponentsByAssistantType(
                    AudioProducer, entryDict['audio-producer'], )
                videoProducers = self._createComponentsByAssistantType(
                    VideoProducer, entryDict['video-producer'])
                scenario = configurationAssistant.getScenario()
                scenario.setAudioProducers(audioProducers)
                scenario.setVideoProducers(videoProducers)
            elif addition == 'streamer':
                muxers = self._createComponentsByAssistantType(
                    Muxer, entryDict['muxer'], )
                scenario = configurationAssistant.getScenario()
                scenario.setMuxers(muxers)

            self._runAssistant(configurationAssistant)

        def gotBundledFunction(function):
            scenario = function()
            scenario.setMode('add%s' % addition)
            scenario.addSteps(configurationAssistant)
            configurationAssistant.setScenario(scenario)
            httpPorters = self._getHTTPPorters()
            self._setMountPoints(configurationAssistant)
            if httpPorters:
                configurationAssistant.setHTTPPorters(httpPorters)

            if addition == 'format':
                return self._adminModel.getWizardEntries(
                    wizardTypes=['audio-producer', 'video-producer'])
            elif addition == 'streamer':
                return self._adminModel.getWizardEntries(
                    wizardTypes=['muxer'])

        d = self._adminModel.getBundledFunction(
            'flumotion.scenario.live.wizard_gtk',
            'LiveAssistantPlugin')

        d.addCallback(gotBundledFunction)
        d.addCallback(gotWizardEntries)

    def _runConfigurationAssistant(self):
        if not self._adminModel.isConnected():
            self._error(
               _('Cannot run assistant without being connected to a manager'))
            return

        from flumotion.admin.gtk.configurationassistant import \
             ConfigurationAssistant

        def runAssistant():
            configurationAssistant = ConfigurationAssistant(self._window)
            configurationAssistant.addInitialSteps()
            self._runAssistant(configurationAssistant)

        if not self._componentStates:
            runAssistant()
            return

        for componentState in self._componentList.getComponentStates():
            if componentState.get('mood') == moods.lost.value:
                self._error(
                    _("Cannot run the configuration assistant since there "
                      "is at least one component in the lost state"))
                return

        if yesno(_("Running the Configuration Assistant again will remove "
                   "all components from the current stream and create "
                   "a new one."),
                 parent=self._window,
                 buttons=((_("Keep the current stream"),
                           gtk.RESPONSE_NO),
                          (_("Run the Assistant anyway"),
                           gtk.RESPONSE_YES))) != gtk.RESPONSE_YES:
            return

        d = self._clearAllComponents()
        # The remote call returns a list with the results of the cleaning.
        # None if there has been an error during the processs.
        d.addCallback(lambda list: list and runAssistant())

    def _runAssistant(self, assistant):
        if self._adminModel is None:
            return

        workerHeavenState = self._adminModel.getWorkerHeavenState()
        if not workerHeavenState.get('names'):
            self._error(
                _('The assistant cannot be run because no workers are '
                  'logged in.'))
            return

        self._configurationAssistantIsRunning = True
        assistant.setExistingComponentNames(
            self._componentList.getComponentNames())
        assistant.setAdminModel(self._adminModel)
        assistant.setWorkerHeavenState(workerHeavenState)
        httpPorters = self._getHTTPPorters()
        if httpPorters:
            assistant.setHTTPPorters(httpPorters)
        assistant.connect('finished', self._assistant_finished_cb)
        assistant.connect('destroy', self.on_assistant_destroy)

        assistant.run(main=False)

    def _clearAdmin(self):
        if self._adminModel is None:
            return

        self._adminModel.disconnectByFunction(self._admin_connected_cb)
        self._adminModel.disconnectByFunction(self._admin_disconnected_cb)
        self._adminModel.disconnectByFunction(self._admin_update_cb)
        self._adminModel = None

        self._addFormatAction.set_sensitive(False)
        self._addStreamerAction.set_sensitive(False)
        self._runConfigurationAssistantAction.set_sensitive(False)

    def _updateUIStatus(self, connected):
        self._window.set_sensitive(connected)
        group = self._actiongroup
        group.get_action('ImportConfig').set_sensitive(connected)
        group.get_action('ExportConfig').set_sensitive(connected)
        group.get_action('EnableDebugging').set_sensitive(connected)

        self._clearLastStatusbarText()
        if connected:
            self._window.set_title(_('%s - Flumotion Administration') %
                                   self._adminModel.adminInfoStr())
            self._trayicon.set_tooltip(_('Flumotion: %s') % (
                self._adminModel.adminInfoStr(), ))
        else:
            self._setStatusbarText(_('Not connected'))
            self._trayicon.set_tooltip(_('Flumotion: Not connected'))

    def _updateConnectionActions(self):
        self._openRecentAction.set_sensitive(hasRecentConnections())

    def _updateComponentActions(self):
        canStart = self._componentList.canStart()
        canStop = self._componentList.canStop()
        canDelete = self._componentList.canDelete()
        self._startComponentAction.set_sensitive(canStart)
        self._stopComponentAction.set_sensitive(canStop)
        self._deleteComponentAction.set_sensitive(canDelete)
        self.debug('can start %r, can stop %r, can delete %r' % (
            canStart, canStop, canDelete))
        canStartAll = self._componentList.get_property('can-start-any')
        canStopAll = self._componentList.get_property('can-stop-any')

        # they're all in sleeping or lost
        canClearAll = canStartAll and not canStopAll
        self._stopAllAction.set_sensitive(canStopAll)
        self._startAllAction.set_sensitive(canStartAll)
        self._clearAllAction.set_sensitive(canClearAll)
        self._killComponentAction.set_sensitive(canStop)

        hasProducer = self._hasProducerComponent()
        self._addFormatAction.set_sensitive(hasProducer)
        self._addStreamerAction.set_sensitive(hasProducer)

    def _updateComponents(self):
        self._componentList.clearAndRebuild(self._componentStates,
                                            self._componentNameToSelect)
        self._trayicon.update(self._componentStates)

    def _appendComponent(self, component):
        self._componentStates[component.get('name')] = component
        self._componentList.appendComponent(component,
                                            self._componentNameToSelect)
        self._trayicon.update(self._componentStates)

    def _hasProducerComponent(self):
        for state in self._componentList.getComponentStates():
            if state is None:
                continue
            # FIXME: Not correct, should expose assistant state from
            #        the registry.
            name = state.get('name')
            if 'producer' in name:
                return True
        return False

    def _clearMessages(self):
        self._messageView.clear()
        pstate = self._planetState
        if pstate and pstate.hasKey('messages'):
            for message in pstate.get('messages').values():
                self._messageView.addMessage(message)

    def _setPlanetState(self, planetState):

        def flowStateAppend(state, key, value):
            self.debug('flow state append: key %s, value %r' % (key, value))
            if key == 'components':
                self._appendComponent(value)

        def flowStateRemove(state, key, value):
            if key == 'components':
                self._removeComponent(value)

        def atmosphereStateAppend(state, key, value):
            if key == 'components':
                self._appendComponent(value)

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

                self._componentStates.update(
                    dict((c.get('name'), c) for c in value.get('components')))
                self._updateComponents()

        def planetStateRemove(state, key, value):
            self.debug('something got removed from the planet')

        def planetStateSetitem(state, key, subkey, value):
            if key == 'messages':
                self._messageView.addMessage(value)

        def planetStateDelitem(state, key, subkey, value):
            if key == 'messages':
                self._messageView.clearMessage(value.id)

        self.debug('parsing planetState %r' % planetState)
        self._planetState = planetState

        # clear and rebuild list of components that interests us
        self._componentStates = {}

        planetState.addListener(self, append=planetStateAppend,
                                remove=planetStateRemove,
                                setitem=planetStateSetitem,
                                delitem=planetStateDelitem)

        self._clearMessages()

        a = planetState.get('atmosphere')
        a.addListener(self, append=atmosphereStateAppend,
                      remove=atmosphereStateRemove)

        self._componentStates.update(
            dict((c.get('name'), c) for c in a.get('components')))

        for f in planetState.get('flows'):
            planetStateAppend(planetState, 'flows', f)

        if not planetState.get('flows'):
            self._updateComponents()

    def _clearAllComponents(self):
        if not self._adminModel.isConnected():
            return

        d = self._adminModel.cleanComponents()

        def busyComponentError(failure):
            failure.trap(BusyComponentError)
            self._error(
                _("Some component(s) are still busy and cannot be removed.\n"
                  "Try again later."))
        d.addErrback(busyComponentError)
        return d

    # component view activation functions

    def _removeComponent(self, state):
        name = state.get('name')
        self.debug('removing component %s' % name)
        del self._componentStates[name]

        # if this component was selected, clear selection
        if self._currentComponentStates and state \
           in self._currentComponentStates:
            self._currentComponentStates.remove(state)
        self._componentList.removeComponent(state)
        # a component being removed means our selected component could
        # have gone away
        self._updateComponentActions()

    def _componentStop(self, state):
        """
        @returns: a L{twisted.internet.defer.Deferred}
        """
        self.debug('stopping component %r' % state)
        return self._componentDo(state, 'componentStop',
                                 'Stop', 'Stopping', 'Stopped')

    def _componentStart(self, state):
        """
        @returns: a L{twisted.internet.defer.Deferred}
        """
        return self._componentDo(state, 'componentStart',
                                 'Start', 'Starting', 'Started')

    def _componentDelete(self, state):
        """
        @returns: a L{twisted.internet.defer.Deferred}
        """
        return self._componentDo(state, 'deleteComponent',
                                 'Delete', 'Deleting', 'Deleted')

    def _getStatesFromState(self, state):
        # componentDo can be called on a None state, which means
        # 'look at the current selection'
        if state is None:
            states = self._componentList.getSelectedStates()
            self._componentView.activateComponent(None)
        else:
            states = [state]

        return states

    def _componentDo(self, state, methodName, action, doing, done):
        """Do something with a component and update the statusbar.

        @param state:      componentState; if not specified, will use the
                           currently selected component(s)
        @type  state:      L{AdminComponentState} or None
        @param methodName: name of the method to call
        @type  methodName: str
        @param action:     string used to explain that to do
        @type  action:     str
        @param doing:      string used to explain that the action started
        @type  doing:      str
        @param done:       string used to explain that the action was completed
        @type  done:       str

        @rtype: L{twisted.internet.defer.Deferred}
        @returns: a deferred that will fire when the action is completed.
        """
        states = self._getStatesFromState(state)

        if not states:
            return

        def callbackSingle(result, self, mid, name):
            self._statusbar.remove('main', mid)
            self._setStatusbarText(
                _("%s component %s") % (done, name))

        def errbackSingle(failure, self, mid, name):
            self._statusbar.remove('main', mid)
            self.warning("Failed to %s component %s: %s" % (
                action.lower(), name, failure))
            self._setStatusbarText(
                _("Failed to %(action)s component %(name)s.") % {
                    'action': action.lower(),
                    'name': name,
                })

        def callbackMultiple(results, self, mid):
            self._statusbar.remove('main', mid)
            self._setStatusbarText(
                _("%s components.") % (done, ))

        def errbackMultiple(failure, self, mid):
            self._statusbar.remove('main', mid)
            self.warning("Failed to %s some components: %s." % (
                action.lower(), failure))
            self._setStatusbarText(
                _("Failed to %s some components.") % (action, ))

        f = gettext.dngettext(
            configure.PACKAGE,
            # first %s is one of Stopping/Starting/Deleting
            # second %s is a component name like "audio-producer"
            N_("%s component %s"),
            # first %s is one of Stopping/Starting/Deleting
            # second %s is a list of component names, like
            # "audio-producer, video-producer"
            N_("%s components %s"), len(states))
        statusText = f % (doing,
                          ', '.join([getComponentLabel(s) for s in states]))
        mid = self._setStatusbarText(statusText)

        if len(states) == 1:
            state = states[0]
            name = getComponentLabel(state)
            d = self._adminModel.callRemote(methodName, state)
            d.addCallback(callbackSingle, self, mid, name)
            d.addErrback(errbackSingle, self, mid, name)
        else:
            deferreds = []
            for state in states:
                d = self._adminModel.callRemote(methodName, state)
                deferreds.append(d)
            d = defer.DeferredList(deferreds)
            d.addCallback(callbackMultiple, self, mid)
            d.addErrback(errbackMultiple, self, mid)
        return d

    def _killSelectedComponents(self):
        for state in self._componentList.getSelectedStates():
            workerName = state.get('workerRequested')
            avatarId = componentId(state.get('parent').get('name'),
                                   state.get('name'))
            self._adminModel.callRemote(
                'workerCallRemote', workerName, 'killJob', avatarId)

    def _componentSelectionChanged(self, states):
        self.debug('component %s has selection', states)

        def compSet(state, key, value):
            if key == 'mood':
                self.debug('state %r has mood set to %r' % (state, value))
                self._updateComponentActions()

        def compAppend(state, key, value):
            name = state.get('name')
            self.debug('stateAppend on component state of %s' % name)
            if key == 'messages':
                current = self._componentList.getSelectedNames()
                if name in current:
                    self._messageView.addMessage(value)

        def compRemove(state, key, value):
            name = state.get('name')
            self.debug('stateRemove on component state of %s' % name)
            if key == 'messages':
                current = self._componentList.getSelectedNames()
                if name in current:
                    self._messageView.clearMessage(value.id)

        if self._currentComponentStates:
            for currentComponentState in self._currentComponentStates:
                currentComponentState.removeListener(self)
        self._currentComponentStates = states
        if self._currentComponentStates:
            for currentComponentState in self._currentComponentStates:
                currentComponentState.addListener(
                self, set_=compSet, append=compAppend, remove=compRemove)

        self._updateComponentActions()
        self._clearMessages()
        state = None
        if states:
            if len(states) == 1:
                self.debug(
                    "only one component is selected on the components view")
                state = states[0]
            elif states:
                self.debug("more than one components are selected in the "
                           "components view")
                state = MultipleAdminComponentStates(states)
        self._componentView.activateComponent(state)

        statusbarMessage = " "
        for state in states:
            name = getComponentLabel(state)
            messages = state.get('messages')
            if messages:
                for m in messages:
                    self.debug('have message %r', m)
                    self.debug('message id %s', m.id)
                    self._messageView.addMessage(m)

            if state.get('mood') == moods.sad.value:
                self.debug('component %s is sad' % name)
                statusbarMessage = statusbarMessage + \
                                    _("Component %s is sad. ") % name
        if statusbarMessage != " ":
            self._setStatusbarText(statusbarMessage)


        # FIXME: show statusbar things
        # self._statusbar.set('main', _('Showing UI for %s') % name)
        # self._statusbar.set('main',
        #       _("Component %s is still sleeping") % name)
        # self._statusbar.set('main', _("Requesting UI for %s ...") % name)
        # self._statusbar.set('main', _("Loading UI for %s ...") % name)
        # self._statusbar.clear('main')
        # mid = self._statusbar.push('notebook',
        #         _("Loading tab %s for %s ...") % (node.title, name))
        # node.statusbar = self._statusbar # hack

    def _componentShowPopupMenu(self, event_button, event_time):
        self._componentContextMenu.popup(None, None, None,
                                         event_button, event_time)

    def _connectionOpened(self, admin):
        self.info('Connected to manager')
        if self._disconnectedDialog:
            self._disconnectedDialog.destroy()
            self._disconnectedDialog = None

        self._updateUIStatus(connected=True)

        self.emit('connected')

        self._componentView.setSingleAdmin(admin)

        self._setPlanetState(admin.planet)
        self._updateConnectionActions()
        self._updateComponentActions()

        if (not self._componentStates and
            not self._configurationAssistantIsRunning):
            self.debug('no components detected, running assistant')
            # ensure our window is shown
            self._componentList.clearAndRebuild(self._componentStates)
            self.show()
            self._runConfigurationAssistant()
        else:
            self.show()

    def _showConnectionLostDialog(self):
        RESPONSE_REFRESH = 1

        def response(dialog, response_id):
            if response_id == RESPONSE_REFRESH:

                def errback(failure):
                    # Swallow connection errors. We keep trying
                    failure.trap(ConnectionCancelledError,
                                 ConnectionFailedError,
                                 ConnectionRefusedError)

                d = self._adminModel.reconnect(keepTrying=True)
                d.addErrback(errback)
            else:
                self._disconnectedDialog.destroy()
                self._disconnectedDialog = None
                self._adminModel.disconnectFromManager()
                self._window.set_sensitive(True)

        dialog = ProgressDialog(
            _("Reconnecting ..."),
            _("Lost connection to manager %s. Reconnecting ...")
            % (self._adminModel.adminInfoStr(), ), self._window)

        dialog.add_button(gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL)
        dialog.add_button(gtk.STOCK_REFRESH, RESPONSE_REFRESH)
        dialog.connect("response", response)
        dialog.start()
        self._disconnectedDialog = dialog
        self._window.set_sensitive(False)

    def _connectionLost(self):
        self._componentStates = {}
        self._updateComponents()
        self._clearMessages()
        if self._planetState:
            self._planetState.removeListener(self)
            self._planetState = None

        self._showConnectionLostDialog()
        self._updateUIStatus(connected=False)

    def _openRecentConnection(self):
        d = ConnectionsDialog(parent=self._window)

        def on_have_connection(d, connectionInfo):
            d.destroy()
            if connectionInfo:
                self._openConnectionInternal(connectionInfo.info)
                connectionInfo.updateTimestamp()
            self._updateConnectionActions()

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
        dialog.set_select_multiple(True)

        ffilter = gtk.FileFilter()
        ffilter.set_name(_("Flumotion XML configuration files"))
        ffilter.add_pattern("*.xml")
        dialog.add_filter(ffilter)
        ffilter = gtk.FileFilter()
        ffilter.set_name(_("All files"))
        ffilter.add_pattern("*")
        dialog.add_filter(ffilter)

        if self._currentDir:
            dialog.set_current_folder_uri(self._currentDir)

        def response(dialog, response):
            if response == gtk.RESPONSE_ACCEPT:
                self._currentDir = dialog.get_current_folder_uri()
                for name in dialog.get_filenames():
                    conf_xml = open(name, 'r').read()
                    self._adminModel.loadConfiguration(conf_xml)
            dialog.destroy()

        dialog.connect('response', response)
        dialog.show()

    def _exportConfiguration(self):
        d = gtk.FileChooserDialog(
            _("Export Configuration..."), self._window,
            gtk.FILE_CHOOSER_ACTION_SAVE,
            (gtk.STOCK_CANCEL, gtk.RESPONSE_REJECT,
             _('Export'), gtk.RESPONSE_ACCEPT))
        d.set_modal(True)
        d.set_default_response(gtk.RESPONSE_ACCEPT)
        d.set_current_name("configuration.xml")

        if self._currentDir:
            d.set_current_folder_uri(self._currentDir)

        def getConfiguration(conf_xml, name, chooser):
            if not name.endswith('.xml'):
                name += '.xml'

            file_exists = True
            if os.path.exists(name):
                d = gtk.MessageDialog(
                    self._window, gtk.DIALOG_MODAL,
                    gtk.MESSAGE_ERROR, gtk.BUTTONS_YES_NO,
                    _("File already exists.\nOverwrite?"))
                d.connect("response", lambda self, response: d.hide())
                if d.run() == gtk.RESPONSE_YES:
                    file_exists = False
            else:
                file_exists = False

            if not file_exists:
                try:
                    f = open(name, 'w')
                    f.write(conf_xml)
                    f.close()
                    chooser.destroy()
                except IOError, e:
                    self._error(_("Could not open configuration file %s "
                        "for writing (%s)" % (name, e[1])))

        def response(d, response):
            if response == gtk.RESPONSE_ACCEPT:
                self._currentDir = d.get_current_folder_uri()
                deferred = self._adminModel.getConfiguration()
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

        ns = {"admin": self._adminModel,
              "components": self._componentStates}
        message = """Flumotion Admin Debug Shell

Local variables are:
  admin      (flumotion.admin.admin.AdminModel)
  components (dict: name -> flumotion.common.planet.AdminComponentState)

You can do remote component calls using:
  admin.componentCallRemote(components['component-name'],
         'methodName', arg1, arg2)

"""
        code.interact(local=ns, banner=message)

    def _dumpConfiguration(self):

        def gotConfiguration(xml):
            print xml
        d = self._adminModel.getConfiguration()
        d.addCallback(gotConfiguration)

    def _setDebugMarker(self):

        def setMarker(_, marker, level):
            self._adminModel.callRemote('writeFluDebugMarker', level, marker)
        debugMarkerDialog = DebugMarkerDialog()
        debugMarkerDialog.connect('set-marker', setMarker)
        debugMarkerDialog.show()

    def _about(self):
        about = AboutDialog(self._window)
        about.run()
        about.destroy()

    def _showHelp(self):
        for path in os.environ['PATH'].split(':'):
            executable = os.path.join(path, 'gnome-help')
            if os.path.exists(executable):
                break
        else:
            self._error(
                _("Cannot find a program to display the Flumotion manual."))
            return
        gobject.spawn_async([executable,
                             'ghelp:%s' % (configure.PACKAGE, )])

    def _promptForShutdown(self):
        d = gtk.MessageDialog(
                        self._window, gtk.DIALOG_MODAL,
                        gtk.MESSAGE_QUESTION, gtk.BUTTONS_YES_NO,
                        _("Do you want to shutdown manager and worker "
                         "before exiting?"))
        response = d.run()
        d.destroy()
        return response == gtk.RESPONSE_YES

    ### admin model callbacks

    def _admin_connected_cb(self, admin):
        self._connectionOpened(admin)

    def _admin_disconnected_cb(self, admin):
        self._connectionLost()

    def _admin_update_cb(self, admin):
        self._updateComponents()

    ### ui callbacks

    def _on_uimanager__connect_proxy(self, uimgr, action, widget):
        self._connectActionProxy(action, widget)

    def _on_uimanager__disconnect_proxy(self, uimgr, action, widget):
        self._disconnectActionProxy(action, widget)

    def _on_menu_item__select(self, menuitem, tooltip):
        self._setStatusbarText(tooltip)

    def _on_menu_item__deselect(self, menuitem):
        self._clearLastStatusbarText()

    def _on_tool_button__enter(self, toolbutton, tooltip):
        self._setStatusbarText(tooltip)

    def _on_tool_button__leave(self, toolbutton):
        self._clearLastStatusbarText()

    def _assistant_finished_cb(self, assistant, configuration):
        self._assistantFinshed(assistant, configuration)

    def on_assistant_destroy(self, assistant):
        self._configurationAssistantIsRunning = False

    def _window_delete_event_cb(self, window, event):
        self._quit()

    def _window_key_press_event_cb(self, window, event):
        # This should be removed if we're going to support connecting
        # to multiple managers in the same application (MDI/tabs)
        state = event.state & (gtk.gdk.MODIFIER_MASK ^ gtk.gdk.MOD2_MASK)

        if state == gdk.CONTROL_MASK and event.keyval == keysyms.w:
            self._quit()

    def _trayicon_quit_cb(self, trayicon):
        self._quit()

    def _recent_action_activate_cb(self, action, conn):
        self._openConnectionInternal(conn.info)

    def _components_show_popup_menu_cb(self, clist, event_button, event_time):
        self._componentShowPopupMenu(event_button, event_time)

    def _components_selection_changed_cb(self, clist, state):
        self._componentSelectionChanged(state)

    def _components_start_stop_notify_cb(self, clist, pspec):
        self._updateComponentActions()

    ### action callbacks

    def _debug_write_debug_marker_cb(self, action):
        self._setDebugMarker()

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
        for c in self._componentStates.values():
            self._componentStart(c)

    def _manage_stop_all_cb(self, action):
        for c in self._componentStates.values():
            self._componentStop(c)

    def _manage_clear_all_cb(self, action):
        self._clearAllComponents()

    def _manage_add_format_cb(self, action):
        self._runAddNew('format')

    def _manage_add_streamer_cb(self, action):
        self._runAddNew('streamer')

    def _manage_run_assistant_cb(self, action):
        self._runConfigurationAssistant()

    def _debug_enable_cb(self, action):
        self.setDebugEnabled(action.get_active())

    def _debug_start_shell_cb(self, action):
        self._startShell()

    def _debug_dump_configuration_cb(self, action):
        self._dumpConfiguration()

    def _help_contents_cb(self, action):
        self._showHelp()

    def _help_about_cb(self, action):
        self._about()

    def _kill_component_cb(self, action):
        self._killSelectedComponents()

gobject.type_register(AdminWindow)
