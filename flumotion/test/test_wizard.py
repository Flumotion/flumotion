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

from flumotion.wizard import enums, wizard

class WizardStepTest(unittest.TestCase):
    def setUpClass(self):
        import flumotion.wizard.steps
        self.steps = wizard.wiz.steps
        
    def testLoadSteps(self):
        for step in self.steps:
            self.assert_(isinstance(step, wizard.WizardStep))
            self.assert_(hasattr(step, 'icon'))
            windows = [widget for widget in step.widgets
                                  if isinstance(widget, gtk.Window)]
            self.assert_(len(windows) == 1)
            window = windows[0]
            self.failIfEqual(window.get_property('visible'), True)
            self.assert_(hasattr(step, 'icon'))
            self.assert_(hasattr(step, 'glade_file'))
            self.assert_(hasattr(step, 'step_name'))
            self.assert_(isinstance(step.get_state(), dict))
            self.assertIdentical(step.step_name, step.get_name())

            if step.get_name() != 'Content License':
                self.assert_(isinstance(step.get_next(), str))
                
    def testStepWidgets(self):
        widgets = [widget for step in wizard.wiz.steps
                              for widget in step.widgets]
        for widget in widgets:
            if isinstance(widget, wizard.WizardSpinButton):
                self.assert_(isinstance(widget.get_state(), float))
            elif isinstance(widget, (wizard.WizardRadioButton,
                                     wizard.WizardCheckButton)):
                self.assert_(isinstance(widget.get_state(), bool))
            elif isinstance(widget, wizard.WizardEntry):
                self.assert_(isinstance(widget.get_state(), str))
            elif isinstance(widget, wizard.WizardComboBox):
                state = widget.get_state()
                if hasattr(widget, 'enum_class'):
                    self.assert_(isinstance(state, enums.Enum))
                else:
                    self.assert_(isinstance(state, int))

    def testStepNext(self):
        for step in self.steps:
            if step.get_name() != 'Content License':
                self.assert_(isinstance(step.get_next(), str))
            else:
                self.assertIdentical(step.get_next(), None)
                
    def testStepComponentProperties(self):
        for step in self.steps:
            self.assert_(isinstance(step.get_component_properties(), dict))
