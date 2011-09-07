# -*- Mode: Python -*-
# vi:si:et:sw=4:sts=4:ts=4

# Flumotion - a streaming media server
# Copyright (C) 2004,2005,2006,2007,2008,2009 Fluendo, S.L.
# Copyright (C) 2010,2011 Flumotion Services, S.A.
# All rights reserved.
#
# This file may be distributed and/or modified under the terms of
# the GNU Lesser General Public License version 2.1 as published by
# the Free Software Foundation.
# This file is distributed without any warranty; without even the implied
# warranty of merchantability or fitness for a particular purpose.
# See "LICENSE.LGPL" in the source distribution for more information.
#
# Headers in this file shall remain intact.

"""greeter interface, displayed when the user first starts flumotion.
"""

import gettext
import os
from sys import platform

import gobject
import gtk
from twisted.internet import reactor

from flumotion.admin.connections import hasRecentConnections
from flumotion.admin.gtk.dialogs import showConnectionErrorDialog
from flumotion.common.connection import parsePBConnectionInfo
from flumotion.common.errors import ConnectionFailedError, \
     ConnectionRefusedError
from flumotion.common.managerspawner import LocalManagerSpawner
from flumotion.common.netutils import tryPort
from flumotion.common.pygobject import gsignal
from flumotion.configure import configure
from flumotion.ui.simplewizard import SimpleWizard, WizardStep, \
     WizardCancelled

__version__ = "$Rev$"
_ = gettext.gettext


class Initial(WizardStep):
    name = 'initial'
    title = _('Connect to Flumotion Manager')
    text = (_('Flumotion Admin needs to connect to a Flumotion manager.\n') +
            _('Choose an option from the list and click "Forward" to begin.'))
    connect_to_existing = None
    next_pages = ['load_connection',
                  'connect_to_existing',
                  'start_new']

    def __init__(self, wizard, parent):
        super(Initial, self).__init__(wizard, parent)

        for radio in self.load_connection.get_group():
            if radio.name == 'start_new' and platform.find('win') >= 0:
                radio.hide()
            else:
                radio.connect('activate', self._on_radio__activiate)

    # WizardSteps

    def setup(self, state, available_pages):
        # the group of radio buttons is named after the first check button
        for radio in self.load_connection.get_group():
            isAvailable = radio.get_name() in available_pages
            radio.set_sensitive(isAvailable)

        hasRecent = hasRecentConnections()
        self.load_connection.set_sensitive(hasRecent)
        if hasRecent:
            self.load_connection.set_active(True)
        else:
            self.connect_to_existing.set_active(True)

        # Find which radio button should be focused:
        for radioName in available_pages:
            radio = getattr(self, radioName)
            if radio.get_active():
                break
        else:
            raise AssertionError("no button to focus")
        radio.grab_focus()

    def on_next(self, state):
        for radio in self.connect_to_existing.get_group():
            if radio.get_active():
                return radio.get_name()
        raise AssertionError

    # Callbacks

    def _on_radio__activiate(self, radio):
        if not radio.get_active():
            return
        self.button_next.clicked()


class ConnectToExisting(WizardStep):
    name = 'connect_to_existing'
    title = _('Host Information')
    text = _('Please enter the address at which the manager is running.')
    next_pages = ['authenticate']
    open_connection = None

    # WizardSteps

    def setup(self, state, available_pages):
        try:
            oc_state = [(k, state[k]) for k in (
                'host', 'port', 'use_insecure')]
            self.open_connection.set_state(dict(oc_state))
        except KeyError:
            pass
        self.open_connection.grab_focus()

    # Callbacks

    def on_can_activate(self, obj, *args):
        self.button_next.set_sensitive(obj.get_property('can-activate'))

    def on_next(self, state):
        for k, v in self.open_connection.get_state().items():
            state[k] = v
        return 'authenticate'


class Authenticate(WizardStep):
    name = 'authenticate'
    title = _('Authentication')
    text = _('Please enter your username and password.')
    auth_method_combo = user_entry = passwd_entry = None
    next_pages = []
    authenticate = None

    # WizardStep

    def setup(self, state, available_pages):
        try:
            oc_state = [(k, state[k]) for k in ('user', 'passwd')]
            self.authenticate.set_state(dict(oc_state))
        except KeyError:
            self.authenticate.set_state(None)
        self.authenticate.grab_focus()
        self.on_can_activate(self.authenticate)

    def on_next(self, state):
        for k, v in self.authenticate.get_state().items():
            state[k] = v
        state['connectionInfo'] = parsePBConnectionInfo(
            state['host'],
            username=state['user'],
            password=state['passwd'],
            port=state['port'],
            use_ssl=not state['use_insecure'])
        return '*finished*'

    # Callbacks

    def on_can_activate(self, obj, *args):
        self.button_next.set_sensitive(obj.get_property('can-activate'))


class LoadConnection(WizardStep):
    name = 'load_connection'
    title = _('Recent Connections')
    text = _('Please choose a connection from the box below.')
    connections = None
    next_pages = []

    # WizardStep

    def setup(self, state, available_pages):
        self.connections.grab_focus()
        self.button_next.set_label(gtk.STOCK_CONNECT)

    def on_next(self, state):
        connection = self.connections.get_selected()
        state['connection'] = connection
        state['connectionInfo'] = connection.info
        return '*finished*'

    # Callbacks

    def on_connection_activated(self, widget, state):
        self.button_next.emit('clicked')

    def on_connections_cleared(self, widget):
        self.button_next.set_sensitive(False)


class StartNew(WizardStep):
    name = 'start_new'
    title = _('Start a New Manager and Worker')
    text = _("""This will start a new manager and worker for you.

The manager and worker will run under your user account.
The manager will only accept connections from the local machine.
This mode is only useful for testing Flumotion.
""")
    start_worker_check = None
    next_pages = ['start_new_error', 'start_new_success']
    gsignal('finished', str)

    _timeout_id = None

    # WizardStep

    def setup(self, state, available_pages):
        self.button_next.grab_focus()

    def on_next(self, state):
        self.label_starting.show()
        self.progressbar_starting.set_fraction(0.0)
        self.progressbar_starting.show()

        def pulse():
            self.progressbar_starting.pulse()
            return True
        self._timeout_id = gobject.timeout_add(200, pulse)

        self._startManager(state)
        self.button_prev.set_sensitive(False)
        return '*signaled*'

    # Private

    def _startManager(self, state):
        port = tryPort()
        managerSpawner = LocalManagerSpawner(port)
        managerSpawner.connect('error', self._on_spawner_error, state)
        managerSpawner.connect('description-changed',
                               self._on_spawner_description_changed)
        managerSpawner.connect('finished', self._on_spawner_finished, state)
        managerSpawner.start()

    def _on_spawner_error(self, spawner, failure, msg, args, state):
        # error should trigger going to next page with an overview
        state.update({
            'command': ' '.join(args),
            'error': msg,
            'failure': failure,
        })
        self._finished('start_new_error')

    def _on_spawner_description_changed(self, spawner, description):
        self.label_starting.set_text(description)

    def _on_spawner_finished(self, spawner, state):
        # because of the ugly call-by-reference passing of state,
        # we have to update the existing dict, not re-bind with state =
        state['connectionInfo'] = parsePBConnectionInfo(
            'localhost',
            username='user',
            password='test',
            port=spawner.getPort(),
            use_ssl=True)
        state.update(dict(confDir=spawner.getConfDir(),
                          logDir=spawner.getLogDir(),
                          runDir=spawner.getRunDir()))
        state['managerSpawner'] = spawner
        self._finished('start_new_success')

    def _finished(self, result):
        # result: start_new_error or start_new_success
        self.label_starting.hide()
        self.progressbar_starting.hide()
        gobject.source_remove(self._timeout_id)
        self.emit('finished', result)


class StartNewError(WizardStep):
    name = 'start_new_error'
    title = _('Failed to Start')
    text = ""
    start_worker_check = None
    next_pages = []

    # WizardStep

    def setup(self, state, available_pages):
        self.button_next.set_sensitive(False)
        self.message.set_text(state['error'])
        f = state['failure']
        result = ""
        if f.value.exitCode is not None:
            result = _('The command exited with an exit code of %d.' %
                f.value.exitCode)
        self.more.set_markup(_("""The command that failed was:
<i>%s</i>
%s""") % (state['command'], result))


class StartNewSuccess(WizardStep):
    name = 'start_new_success'
    title = _('Started Manager and Worker')
    start_worker_check = None
    text = ''
    next_pages = []

    # WizardStep

    def setup(self, state, available_pages):
        self.button_prev.set_sensitive(False)
        self.button_next.set_label(gtk.STOCK_CONNECT)
        executable = os.path.join(configure.sbindir, 'flumotion')
        confDir = state['confDir']
        logDir = state['logDir']
        runDir = state['runDir']
        stop = "%s -C %s -L %s -R %s stop" % (
            executable, confDir, logDir, runDir)
        self.message.set_markup(_(
"""The admin client will now connect to the manager.

Configuration files are stored in
<i>%s</i>
Log files are stored in
<i>%s</i>

You can shut down the manager and worker later with the following command:

<i>%s</i>
""") % (confDir, logDir, stop))
        self.button_next.grab_focus()

    def on_next(self, state):
        return '*finished*'


class Greeter(SimpleWizard):
    name = 'greeter'
    steps = [Initial, ConnectToExisting, Authenticate, LoadConnection,
             StartNew, StartNewError, StartNewSuccess]

    def __init__(self, adminWindow):
        self._adminWindow = adminWindow
        SimpleWizard.__init__(self, 'initial',
                              parent=adminWindow.getWindow())
        # Set the name of the toplevel window, this is used by the
        # ui unittest framework
        self.window1.set_name('Greeter')
        self.window1.set_size_request(-1, 450)

    # SimpleWizard

    def runAsync(self):
        d = SimpleWizard.runAsync(self)
        d.addCallback(self._runAsyncFinished)
        d.addErrback(self._wizardCancelledErrback)
        return d

    # Private

    def _runAsyncFinished(self, state):
        connection = state.get('connection')
        info = state['connectionInfo']

        def connected(unused):
            if connection is not None:
                connection.updateTimestamp()

        def errorMessageDisplayed(unused):
            return self.runAsync()

        def connectionFailed(failure):
            failure.trap(ConnectionFailedError, ConnectionRefusedError)
            d = showConnectionErrorDialog(failure, info,
                                          parent=self.window)
            d.addCallback(errorMessageDisplayed)
            return d

        d = self._adminWindow.openConnection(info, state.get('managerSpawner'))
        d.addCallbacks(connected, connectionFailed)
        self.set_sensitive(False)
        return d

    def _wizardCancelledErrback(self, failure):
        failure.trap(WizardCancelled)
        reactor.stop()


# This is used by the gtk admin to connect to an existing manager


class ConnectExisting(SimpleWizard):
    name = 'greeter'
    steps = [ConnectToExisting, Authenticate]

    def __init__(self, parent=None):
        SimpleWizard.__init__(self, 'connect_to_existing',
                              parent=parent)
