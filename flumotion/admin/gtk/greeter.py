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

from flumotion.configure import configure
from flumotion.admin.gtk import wizard, connections


# A wizard run when the user first starts flumotion.


# personal note: these things duplicate to a large extent the code in
# flumotion.wizard.steps. A bit irritating to find that out after
# hacking on it for a bit.


# Page classes (see wizard.py for details)

class Initial(wizard.WizardStep):
    name = 'initial'
    title = 'Connect to Flumotion manager'
    text = 'Flumotion Admin needs to connect to a Flumotion manager.\nChoose' \
           + ' an option from the list and click "Forward" to begin.'
    connect_to_existing = None
    next_pages = ['load_connection', 'connect_to_existing']

    def on_next(self, state):
        radio_buttons = self.connect_to_existing.get_group()

        for i in range(len(radio_buttons)):
            if radio_buttons[i].get_active():
                return radio_buttons[i].get_name()
        raise AssertionError
    
    def setup(self, state, available_pages):
        radio_buttons = self.connect_to_existing.get_group()
        for w in radio_buttons:
            w.set_sensitive(w.get_name() in available_pages)
            if w.get_active() and not w.get_property('sensitive'):
                getattr(self,available_pages[0]).set_active(True)


class ConnectToExisting(wizard.WizardStep):
    name='connect_to_existing'
    title='Host information'
    text = 'Please enter the address where the manager is running.'
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


class Authenticate(wizard.WizardStep):
    name = 'authenticate'
    title = 'Authentication'
    text = 'Please select among the following authentication methods.'
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


class LoadConnection(wizard.WizardStep):
    name = 'load_connection'
    title = 'Recent connections'
    text = 'Please choose a connection from the box below.'
    connections = None
    next_pages = []

    def is_available(self):
        return self.connections.get_selected()

    def on_has_selection(self, widget, has_selection):
        self.button_next.set_sensitive(has_selection)

    def on_connection_activated(self, widget, state):
        self.button_next.emit('clicked')

    def on_next(self, state):
        state.update(self.connections.get_selected())
        return '*finished*'

    def setup(self, state, available_pages):
        self.connections.grab_focus()


class Greeter(wizard.Wizard):
    name = 'greeter'
    steps = [Initial, ConnectToExisting, Authenticate, LoadConnection]

    def __init__(self):
        wizard.Wizard.__init__(self, 'initial')
