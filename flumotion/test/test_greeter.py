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

import common

from twisted.spread import jelly
from twisted.trial import unittest
from twisted.internet import reactor

try:
    import gobject
    import gtk
except RuntimeError:
    import os
    os._exit(0)

from flumotion.admin.gtk import greeter, wizard

class WizardTest(unittest.TestCase):
    _failed = False
    state = False

    def testMakeGreeter(self):
        g = greeter.Greeter()
        ass = self.assert_
        ass(isinstance(g.wiz, wizard.Wizard))
        wiz = g.wiz
        ass(isinstance(wiz.name, str))
        ass(isinstance(wiz.page, wizard.WizardStep))
        ass(isinstance(wiz.pages, dict))
        ass(isinstance(wiz.page_stack, list))
        ass(isinstance(wiz.state, dict))

        # check a couple names that come from libglade..
        ass(isinstance(wiz.button_next, gtk.Widget))
        ass(isinstance(wiz.button_prev, gtk.Widget))
        
        def ass(expr):
            if not expr:
                raise # to show the backtrace
                self._failed = True

        def sensitive(w):
            return w.get_property('sensitive')

        next = wiz.button_next
        prev = wiz.button_prev

        # makes sure proc only gets called once
        def idle_add(proc):
            def proc_star():
                proc()
                return False
            gobject.idle_add(proc_star)
        
        idle_add(lambda: next.emit('clicked'))
        idle_add(lambda: prev.emit('clicked'))
        idle_add(lambda: next.emit('clicked'))
        idle_add(lambda: ass(sensitive(next)))
        idle_add(lambda: wiz.page.host_entry.set_text('foo'))
        idle_add(lambda: ass(sensitive(next)))
        idle_add(lambda: wiz.page.ssl_check.emit('clicked'))
        idle_add(lambda: ass(wiz.page.port_entry.get_text()=='8642'))
        idle_add(lambda: next.emit('clicked'))
        idle_add(lambda: prev.emit('clicked'))
        idle_add(lambda: next.emit('clicked'))
        idle_add(lambda: ass(not sensitive(next)))
        idle_add(lambda: ass(wiz.page.auth_method_combo.get_active()==0))
        idle_add(lambda: wiz.page.user_entry.set_text('bar'))
        idle_add(lambda: ass(not sensitive(next)))
        idle_add(lambda: wiz.page.passwd_entry.set_text('baz'))
        idle_add(lambda: ass(sensitive(next)))
        idle_add(lambda: next.emit('clicked'))

        state = wiz.run()

        try:
            assert not self._failed
        finally:
            wiz.destroy()

        refstate = {'passwd': 'baz', 'host': 'foo', 'port': 8642,
                    'use_insecure': True, 'user': 'bar'}
        self.assert_(state == refstate)

WizardTest().testMakeGreeter()
