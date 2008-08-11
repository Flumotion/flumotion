# -*- Mode: Python; test-case-name: flumotion.test.test_wizard -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# Flumotion - a streaming media server
# Copyright (C) 2004,2005,2006,2007 Fluendo, S.L. (www.fluendo.com).
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

from twisted.internet import defer
from twisted.spread import jelly

from flumotion.common import worker
from flumotion.common import testsuite

from flumotion.admin import admin
from flumotion.ui.wizard import WizardStep
from flumotion.admin.gtk.configurationassistant import ConfigurationAssistant


class WizardStepTest(testsuite.TestCase):

    def setUp(self):
        self.wizard = ConfigurationAssistant()

    def testLoadSteps(self):
        for s in self.wizard.getSteps():
            self.assert_(isinstance(s, WizardStep))
            self.assert_(hasattr(s, 'icon'))
            self.assert_(hasattr(s, 'icon'))
            self.assert_(hasattr(s, 'gladeFile'))
            self.assert_(hasattr(s, 'name'))
            if s.get_name() == 'Firewire':
                s._queryCallback(dict(height=576, width=720,
                                      par=(59, 54)))
            self.assertEqual(s.name, s.get_name())

            if s.get_name() != 'Summary':
                getNextRet = s.getNext()
                self.assert_(not getNextRet or isinstance(getNextRet, str))

    def testStepComponentProperties(self):
        for s in self.wizard.getSteps():
            if s.get_name() == 'Firewire':
                s._queryCallback(dict(height=576, width=720,
                                      par=(59, 54)))
            self.assert_(isinstance(s.get_component_properties(), dict))


class TestAdmin(admin.AdminModel):

    def _makeFactory(self, username, password):
        return admin.AdminClientFactory('medium', 'user', 'pass')

    def workerRun(self, worker, module, function, *args, **kwargs):
        success = {
            ('localhost', 'flumotion.worker.checks.video', 'checkTVCard'):
            {'height': 576, 'width': 720, 'par': (59, 54)}}
        failures = {}

        key = (worker, module, function)
        if key in success:
            return defer.succeed(success[key])
        elif key in failures:
            return defer.fail(failures[key])
        else:
            assert False


class WizardSaveTest(testsuite.TestCase):

    def setUp(self):
        self.wizard = ConfigurationAssistant()
        self.wizard.admin = TestAdmin('user', 'test')
        s = worker.ManagerWorkerHeavenState()
        s.set('names', ['localhost'])
        self.workerHeavenState = jelly.unjelly(jelly.jelly(s))

    def testFirewireAudioAndVideo(self):
        source = self.wizard['Production']
        source.combobox_video.set_active('firewire-producer')
        source.combobox_audio.set_active('firewire-producer')

        self.wizard['Firewire'].run_checks()
        self.wizard.run(False, self.workerHeavenState, True)

        config = self.wizard.getConfig()
        self.assert_('video-producer' in config)
        self.assert_(not 'audio-producer' in config)
        videoProducer = config['video-producer']
        self.failUnlessEqual(videoProducer.type, 'firewire')

        self.failUnlessEqual(config['audio-encoder'].getEaters(),
            ['video-producer:audio'])
        self.failUnlessEqual(config['video-overlay'].getEaters(),
            ['video-producer:video'])
    testFirewireAudioAndVideo.skip = 'Maybe Andys generator work broke this ?'

    def testAudioTestWorkers(self):
        source = self.wizard['Production']
        source.combobox_video.set_active('webcam-producer')
        source.combobox_audio.set_active('audiotest-producer')

        self.wizard.run(False, ['first', 'second'], True)

        self.wizard['Production'].worker = 'second'
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
    testAudioTestWorkers.skip = 'Maybe Andy\'s generator work broke this ?'
