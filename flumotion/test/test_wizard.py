# -*- Mode: Python; test-case-name: flumotion.test.test_wizard -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# flumotion/test/test_wizard.py:
# regression test for flumotion.wizard
#
# Flumotion - a streaming media server
# Copyright (C) 2004 Fluendo (www.fluendo.com)

# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
# See "LICENSE.GPL" in the source distribution for more information.

# This program is also licensed under the Flumotion license.
# See "LICENSE.Flumotion" in the source distribution for more information.

import common
import gtk

from twisted.trial import unittest

from flumotion.wizard import wizard

class WizardStepTest(unittest.TestCase):
    def testLoadSteps(self):
        import flumotion.wizard.steps
        
        for step in wizard.wiz.steps:
            self.assert_(isinstance(step, wizard.WizardStep))
            self.assert_(hasattr(step, 'icon'))
            windows = [widget for widget in step.widgets
                                  if isinstance(widget, gtk.Window)]
            self.assert_(len(windows) == 1)
            window = windows[0]
            self.assert_(window.get_property('visible') == False)
            self.assert_(hasattr(step, 'icon'))
            self.assert_(hasattr(step, 'glade_file'))
            self.assert_(hasattr(step, 'step_name'))
            self.assert_(isinstance(step.get_state(), dict))
            
