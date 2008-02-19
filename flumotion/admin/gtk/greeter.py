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

"""Wizard run when the user first starts flumotion.
"""
import os
import errno

import gobject

from gettext import gettext as _

from twisted.internet import reactor, protocol, defer, error

from flumotion.common.pygobject import gsignal
from flumotion.configure import configure
from flumotion.ui.simplewizard import WizardStep, SimpleWizard

__version__ = "$Rev$"


class Initial(WizardStep):
    name = 'initial'
    title = _('Connect to Flumotion manager')
    text = (_('Flumotion Admin needs to connect to a Flumotion manager.\n') +
            _('Choose an option from the list and click "Forward" to begin.'))
    connect_to_existing = None
    next_pages = ['load_connection',
                  'connect_to_existing',
                  'start_new']

    def __init__(self, wizard, parent):
        super(Initial, self).__init__(wizard, parent)

        for radio in self.load_connection.get_group():
            radio.connect('activate', self._on_radio__activiate)

    def on_next(self, state):
        for radio in self.connect_to_existing.get_group():
            if radio.get_active():
                return radio.get_name()
        raise AssertionError

    def _on_radio__activiate(self, radio):
        self.button_next.clicked()

    def setup(self, state, available_pages):
        # the group of radio buttons is named after the first check button
        for radio in self.load_connection.get_group():
            isAvailable = radio.get_name() in available_pages
            radio.set_sensitive(isAvailable)

            if radio.get_active()and not radio.props.sensitive:
                firstRadio = getattr(self, available_pages[0])
                firstRadio.set_active(True)

        # Find which radio button should be focused:
        for radioName in available_pages:
            radio = getattr(self, radioName)
            if radio.get_active():
                break
        else:
            raise AssertionError("no button to focus")
        radio.grab_focus()


class ConnectToExisting(WizardStep):
    name = 'connect_to_existing'
    title = _('Host information')
    text = _('Please enter the address where the manager is running.')
    next_pages = ['authenticate']
    open_connection = None

    def setup(self, state, available_pages):
        try:
            oc_state = [(k, state[k]) for k in ('host', 'port', 'use_insecure')]
            self.open_connection.set_state(dict(oc_state))
        except KeyError:
            pass
        self.open_connection.grab_focus()

    def on_can_activate(self, obj, *args):
        self.button_next.set_sensitive(obj.get_property('can-activate'))

    def on_next(self, state):
        for k, v in self.open_connection.get_state().items():
            state[k] = v
        return 'authenticate'


class Authenticate(WizardStep):
    name = 'authenticate'
    title = _('Authentication')
    text = _('Please select among the following authentication methods.')
    auth_method_combo = user_entry = passwd_entry = None
    next_pages = []

    authenticate = None

    def setup(self, state, available_pages):
        try:
            oc_state = [(k, state[k]) for k in ('user', 'passwd')]
            self.authenticate.set_state(dict(oc_state))
        except KeyError:
            self.authenticate.set_state(None)
        self.authenticate.grab_focus()
        self.on_can_activate(self.authenticate)

    def on_can_activate(self, obj, *args):
        self.button_next.set_sensitive(obj.get_property('can-activate'))

    def on_next(self, state):
        for k, v in self.authenticate.get_state().items():
            state[k] = v
        return '*finished*'


class LoadConnection(WizardStep):
    name = 'load_connection'
    title = _('Recent connections')
    text = _('Please choose a connection from the box below.')
    connections = None
    next_pages = []

    def is_available(self):
        return self.connections.get_selected()

    def on_has_selection(self, widget, has_selection):
        self.button_next.set_sensitive(has_selection)

    def on_connection_activated(self, widget, state):
        self.button_next.emit('clicked')

    def on_next(self, state):
        connection = self.connections.get_selected()
        info = connection.info
        for k, v in (('host', info.host),
                     ('port', info.port),
                     ('use_insecure', not info.use_ssl),
                     ('user', info.authenticator.username),
                     ('passwd', info.authenticator.password)):
            state[k] = v
        return '*finished*'

    def setup(self, state, available_pages):
        self.connections.grab_focus()


class GreeterProcessProtocol(protocol.ProcessProtocol):
    def __init__(self):
        # no parent init
        self.deferred = defer.Deferred()

    def processEnded(self, failure):
        if failure.check(error.ProcessDone):
            self.deferred.callback(None)
        else:
            self.deferred.callback(failure)


class StartNew(WizardStep):
    name = 'start_new'
    title = _('Start a new manager and worker')
    text = _("""This will start a new manager and worker for you.

The manager and worker will run under your user account.
The manager will only accept connections from the local machine.
This mode is only useful for testing Flumotion.
""")
    start_worker_check = None
    next_pages = ['start_new_error', 'start_new_success']
    gsignal('finished', str)

    _timeout_id = None

    def on_has_selection(self, widget, has_selection):
        self.button_next.set_sensitive(has_selection)

    def on_next(self, state):
        self.label_starting.show()
        self.progressbar_starting.set_fraction(0.0)
        self.progressbar_starting.show()
        # start a manager first
        import socket
        port = 7531
        def tryPort(port=0):
            # tries the given port, or a random one, and return None or port
            # number
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.debug('Binding to port %d' % port)

            try:
                s.bind(('', port))
                port = s.getsockname()[1]
            except socket.error, e:
                if e.args[0] == errno.EADDRINUSE:
                    self.debug('Port %d already in use', port)
                    port = None

            s.close()
            return port

        if tryPort(port) is None:
            port = tryPort()

        # ready to start spawning processes

        def pulse():
            self.progressbar_starting.pulse()
            return True

        self._timeout_id = gobject.timeout_add(200, pulse)

        import tempfile
        path = tempfile.mkdtemp(suffix='.flumotion')
        confDir = os.path.join(path, 'etc')
        logDir = os.path.join(path, 'var', 'log')
        runDir = os.path.join(path, 'var', 'run')

        # We need to run 4 commands in a row, and each of them can fail
        d = defer.Deferred()
        def run(result, args, description, failMessage):
            # run the given command
            # show a dialog to say what we are doing
            self.label_starting.set_text(description)
            args[0] = os.path.join(configure.sbindir, args[0])
            protocol = GreeterProcessProtocol()
            env = os.environ.copy()
            paths = env['PATH'].split(os.pathsep)
            if configure.bindir not in paths:
                paths.insert(0, configure.bindir)
            env['PATH'] = os.pathsep.join(paths)
            process = reactor.spawnProcess(protocol, args[0], args, env=env)
            def error(failure, failMessage):
                self.label_starting.set_text(_('Failed to %s') % description)
                # error should trigger going to next page with an overview
                state.update({
                    'command': ' '.join(args),
                    'error': failMessage,
                    'failure': failure,
                })
                self.finished('start_new_error')
                return failure
            protocol.deferred.addErrback(error, failMessage)
            return protocol.deferred

        def chain(args, description, failMessage):
            d.addCallback(run, args, description, failMessage)

        chain(["flumotion", "-C", confDir, "-L", logDir, "-R", runDir,
               "create", "manager", "admin", str(port)],
              _('Creating manager ...'),
              _("Could not create manager."))

        chain(["flumotion", "-C", confDir, "-L", logDir, "-R", runDir,
               "start", "manager", "admin"],
              _('Starting manager ...'),
              _("Could not start manager."))

        chain(["flumotion", "-C", confDir, "-L", logDir, "-R", runDir,
               "create", "worker", "admin", str(port)],
              _('Creating worker ...'),
              _("Could not create worker."))

        chain(["flumotion", "-C", confDir, "-L", logDir, "-R", runDir,
               "start", "worker", "admin"],
              _('Starting worker ...'),
              _("Could not start worker."))

        d.addErrback(lambda f: None)

        def done(result, state):
            # because of the ugly call-by-reference passing of state,
            # we have to update the existing dict, not re-bind with state =
            state.update({
                'host': 'localhost',
                'port': port,
                'use_insecure': False,
                'user': 'user',
                'passwd': 'test',
                'confDir': confDir,
                'logDir': logDir,
                'runDir': runDir,
            })
            self.finished('start_new_success')

        d.addCallback(done, state)

        # start chain
        d.callback(None)
        return '*signaled*'

    def finished(self, result):
        # result: start_new_error or start_new_success
        self.label_starting.hide()
        self.progressbar_starting.hide()
        gobject.source_remove(self._timeout_id)
        self.emit('finished', result)


class StartNewError(WizardStep):
    name = 'start_new_error'
    title = _('Failed to start')
    text = ""
    start_worker_check = None
    next_pages = []

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
    title = _('Started manager and worker')
    start_worker_check = None
    text = ''
    next_pages = []

    def setup(self, state, available_pages):
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

    def on_next(self, state):
        return '*finished*'


class Greeter(SimpleWizard):
    name = 'greeter'
    steps = [Initial, ConnectToExisting, Authenticate, LoadConnection,
        StartNew, StartNewError, StartNewSuccess]

    def __init__(self, parent=None):
        SimpleWizard.__init__(self, 'initial', parent=parent)


# This is used by the gtk admin to connect to an existing manager
class ConnectExisting(SimpleWizard):
    name = 'greeter'
    steps = [ConnectToExisting, Authenticate]

    def __init__(self, parent=None):
        SimpleWizard.__init__(self, 'connect_to_existing',
                              parent=parent)
