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
# Streaming Server license may use this file in accordance with th
# Flumotion Advanced Streaming Server Commercial License Agreement.
# See "LICENSE.Flumotion" in the source distribution for more information.

# Headers in this file shall remain intact.


import gobject
import gtk
import gtk.glade

import flumotion.admin.gtk.wizard


# A wizard run when the user first starts flumotion.


# Page callbacks (see wizard.py for details)

def initial_cb(page, state):
    wtree = gtk.glade.get_widget_tree(page)
    radio_buttons = wtree.get_widget('connect_to_existing').get_group()

    for i in range(len(radio_buttons)):
        if radio_buttons[i].get_active():
            return radio_buttons[i].get_name()

    assert(False)
            
def connect_to_existing_cb(page, state):
    wtree = gtk.glade.get_widget_tree(page)
    host = wtree.get_widget('host_entry').get_text()
    port = wtree.get_widget('port_entry').get_text()
    ssl_check = wtree.get_widget('ssl_check').get_active()

    # fixme: check these values here
    state['host'] = host
    state['port'] = port
    state['ssl_check'] = ssl_check

    return 'authenticate'

def authenticate_cb(page, state):
    wtree = gtk.glade.get_widget_tree(page)
    user = wtree.get_widget('user_entry').get_text()
    passwd = wtree.get_widget('passwd_entry').get_text()

    # fixme: check these values here
    state['user'] = user
    state['passwd'] = passwd
    
    return '*finished*'


def run_greeter_wizard():
    w = wizard.Wizard('greeter', 'initial')
    w.show()
    return w.run()
