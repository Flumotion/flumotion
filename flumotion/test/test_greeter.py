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

try:
    import gobject
    import gtk
except RuntimeError:
    import os
    os._exit(0)

from flumotion.admin.gtk.greeter import *
from flumotion.admin.gtk import wizard

class WizardTest(unittest.TestCase):
    def testMakeGreeter(self):
        wiz = wizard.Wizard('greeter', 'initial')
        self.assert_(isinstance(wiz.name, str))
        self.assert_(isinstance(wiz.page, str))
        self.assert_(isinstance(wiz.page_stack, list))
        self.assert_(isinstance(wiz.page_widget, gtk.Widget))
        self.assert_(isinstance(wiz.page_widgets, dict))
        self.assert_(isinstance(wiz.state, dict))

        # check a couple names that come from libglade..
        self.assert_(isinstance(wiz.button_next, gtk.Widget))
        self.assert_(isinstance(wiz.button_prev, gtk.Widget))
        
        next = wiz.button_next
        prev = wiz.button_prev
        gobject.idle_add(lambda: next.emit('clicked'))
        gobject.idle_add(lambda: prev.emit('clicked'))
        gobject.idle_add(lambda: next.emit('clicked'))
        gobject.idle_add(lambda: next.emit('clicked'))
        gobject.idle_add(lambda: next.emit('clicked'))
        state = wiz.run()
        refstate = {'passwd': '', 'host': '', 'port': '7531',
                    'ssl_check': True, 'user': ''}
        self.assert_(state == refstate)
