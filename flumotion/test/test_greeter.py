# -*- Mode: Python; test-case-name: flumotion.test.test_greeter -*-
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


from twisted.trial import unittest

from flumotion.test.gtkunit import *
import gobject
import gtk

from flumotion.admin.gtk import greeter, wizard


def click(name):
    call_inc(name, 'set_relief', gtk.RELIEF_HALF)
    call_inc(name, 'set_relief', gtk.RELIEF_NORMAL)
    call_inc(name, 'emit', 'clicked')

def set_text(name, text):
    call(name, 'grab_focus')
    call_inc(name, 'delete_text', 0, -1)
    for i in range(len(text)):
        call(name, 'set_position', i)
        call(name, 'insert_text', text[i], i)
        call_inc(name, 'set_position', i + 1)


def check_text(name, text):
    assert_call_returns(name, 'get_text', text)

def prev():
    click('button_prev')
def next():
    click('button_next')
        
def check_prev_next(can_prev, can_next):
    def assert_sensitive(name, s):
        assert_call_returns(name, 'get_property', s, 'sensitive')
    assert_sensitive('button_prev', can_prev)
    assert_sensitive('button_next', can_next)
            

class WizardTest(unittest.TestCase):
    def testMakeGreeter(self):
        wiz = greeter.Greeter()
        ass = self.assert_
        ass(isinstance(wiz, wizard.Wizard))
        ass(isinstance(wiz.name, str))
        ass(isinstance(wiz.page, wizard.WizardStep))
        ass(isinstance(wiz.pages, dict))
        ass(isinstance(wiz.page_stack, list))
        ass(isinstance(wiz.state, dict))

        set_window(wiz.window)

        check_prev_next(False, True)
        click('connect_to_existing')
        next()
        prev()
        next()
        check_prev_next(True, True)
        set_text('host_entry', 'foolio')
        check_prev_next(True, True)
        click('ssl_check')
        check_text('port_entry', '8642')
        next()
        prev()
        next()
        check_prev_next(True, False)
        assert_call_returns('auth_method_combo', 'get_active', 0)
        set_text('user_entry', 'bar')
        check_prev_next(True, False)
        set_text('passwd_entry', 'baz')
        check_prev_next(True, True)
        next()

        state = wiz.run()

        assert_not_failed()
        wiz.destroy()
        
        refstate = {'passwd': 'baz', 'host': 'foolio', 'port': 8642,
                    'use_insecure': True, 'user': 'bar'}
        assert state == refstate
