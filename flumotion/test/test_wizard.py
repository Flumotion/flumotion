# -*- Mode: Python; test-case-name: flumotion.test.test_wizard -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# flumotion/test/test_wizard.py:
# regression test for flumotion.wizard
#
# Flumotion - a streaming media server
# Copyright (C) 2004 Fluendo, S.L. (www.fluendo.com). All rights reserved.

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

from twisted.trial import unittest

try:
    import gtk
except RuntimeError:
    import os
    os._exit(0)

from flumotion.ui import fgtk
from flumotion.common import enum
from flumotion.wizard import enums, wizard

class WizardStepTest(unittest.TestCase):
    def setUpClass(self):
        wiz = wizard.Wizard()
        wiz.load_steps()
        self.steps = wiz.steps
        
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

            if step.get_name() != 'Summary':
                self.assert_(isinstance(step.get_next(), str))
                
    def testStepWidgets(self):
        widgets = [widget for step in self.steps
                              for widget in step.widgets]
        for widget in widgets:
            if isinstance(widget, fgtk.FSpinButton):
                self.assert_(isinstance(widget.get_state(), float))
            elif isinstance(widget, (fgtk.FRadioButton,
                                     fgtk.FCheckButton)):
                self.assert_(isinstance(widget.get_state(), bool))
            elif isinstance(widget, fgtk.FEntry):
                self.assert_(isinstance(widget.get_state(), str))
            elif isinstance(widget, fgtk.FComboBox):
                state = widget.get_state()
                if hasattr(widget, 'enum_class'):
                    self.failUnless(isinstance(state, enum.Enum))
                else:
                    # state can be None in the testsuite as well
                    self.failUnless(not state or isinstance(state, int),
                        "state %r is not an instance of int on widget %r" % (
                            state, widget))

    def testStepComponentProperties(self):
        for step in self.steps:
            self.assert_(isinstance(step.get_component_properties(), dict))


class WizardSaveTest(unittest.TestCase):
    def setUp(self):
        self.wizard = wizard.Wizard()
        self.wizard.load_steps()

    def testFirewireAudioAndVideo(self):
        source = self.wizard['Source']
        source.combobox_video.set_active(enums.VideoDevice.Firewire)
        source.combobox_audio.set_active(enums.AudioDevice.Firewire)

        self.wizard.run(False, ['localhost'], True)
        config = self.wizard.getConfig()
        self.assert_(config.has_key('video-source'))
        self.assert_(not config.has_key('audio-source'))
        videoSource = config['video-source']
        self.failUnlessEqual(videoSource.type, 'firewire')
        
        self.failUnlessEqual(config['audio-encoder'].getFeeders(), ['video-source:audio'])
        self.failUnlessEqual(config['video-overlay'].getFeeders(), ['video-source:video'])

    def testAudioTestWorkers(self):
        source = self.wizard['Source']
        source.combobox_video.set_active(enums.VideoDevice.Webcam)
        source.combobox_audio.set_active(enums.AudioDevice.Test)

        self.wizard.run(False, ['first', 'second'], True)
        
        self.wizard['Source'].worker = 'second'
        self.wizard['Webcam'].worker = 'second'
        self.wizard['Overlay'].worker = 'second'
        self.wizard['Encoding'].worker = 'second'
        self.wizard['Theora'].worker = 'second'
        self.wizard['Vorbis'].worker = 'second'
        self.wizard['HTTP Streamer (audio & video)'].worker = 'first'
        
        config = self.wizard.getConfig()
        for item in config.values():
            print item.name, item.worker
        #print self.wizard.printOut()
    testAudioTestWorkers.skip = 1

