# -*- Mode: Python; test-case-name: flumotion.test.test_greeter -*-
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

from flumotion.admin.gtk.greeter import Greeter
from flumotion.common import testsuite
from flumotion.test.gtkunit import UITestCase
from flumotion.ui.simplewizard import SimpleWizard, WizardStep

attr = testsuite.attr


class FakeAdminWindow:

    def getWindow(self):
        return None


class WizardTest(UITestCase):

    slow = True

    def _prev(self):
        self.click('button_prev')

    def _next(self):
        self.click('button_next')

    def _checkPrevNext(self, can_prev, can_next):
        self.assertSensitive('button_prev', can_prev)
        self.assertSensitive('button_next', can_next)

    def testGreeter(self):
        greeter = Greeter(FakeAdminWindow())
        self.failUnless(isinstance(greeter, SimpleWizard))
        self.failUnless(isinstance(greeter.name, str))
        self.failUnless(isinstance(greeter.page, WizardStep))
        self.failUnless(isinstance(greeter.pages, dict))
        self.failUnless(isinstance(greeter.page_stack, list))
        self.failUnless(isinstance(greeter.state, dict))

        self.setWindow(greeter.window)

        self._checkPrevNext(False, True)
        self.click('connect_to_existing')
        self._next()
        self._prev()
        # FIXME: Save the last option selected instead of
        #        always selecting the first
        self.click('connect_to_existing')
        self._next()
        self._checkPrevNext(True, True)
        self.setText('host_entry', 'foolio')
        self._checkPrevNext(True, True)
        self.click('ssl_check')
        self.checkText('port_entry', '8642')
        self._next()
        self._prev()
        self._next()
        self._checkPrevNext(True, False)
        self.setText('user_entry', 'bar')
        self._checkPrevNext(True, False)
        self.setText('passwd_entry', 'baz')
        self._checkPrevNext(True, True)
        self._next()

        state = greeter.run()
        self.refreshUI()

        self.assertEquals(state.get('passwd'), 'baz')
        self.assertEquals(state.get('host'), 'foolio')
        self.assertEquals(state.get('port'), 8642)
        self.assertEquals(state.get('use_insecure'), True)
        self.assertEquals(state.get('user'), 'bar')
        self.failUnless('connectionInfo' in state)
