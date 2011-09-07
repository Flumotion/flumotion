# -*- Mode: Python -*-
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

import gettext
import os

from zope.interface import implements

from flumotion.admin.assistant.interfaces import IProducerPlugin
from flumotion.admin.assistant.models import AudioProducer
from flumotion.admin.gtk.basesteps import AudioProducerStep

__version__ = "$Rev$"
_ = gettext.gettext


class TestAudioProducer(AudioProducer):
    componentType = 'audiotest-producer'

    def __init__(self):
        super(TestAudioProducer, self).__init__()

        self.properties.samplerate = '44100'


class TestAudioProducerStep(AudioProducerStep):
    name = 'TestAudioProducer'
    title = _('Test Audio Producer')
    icon = 'soundcard.png'
    gladeFile = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                              'wizard.glade')
    docSection = 'help-configuration-assistant-producer-audio-test'
    docAnchor = ''
    docVersion = 'local'

    # WizardStep

    def setup(self):
        self.samplerate.data_type = str
        self.volume.data_type = float
        self.wave.data_type = int

        self.samplerate.prefill(['8000',
                           '16000',
                           '32000',
                           '44100'])

        self.wave.prefill([(_('Sine'), 0),
                          (_('Square'), 1),
                          (_('Saw'), 2),
                          (_('Ticks'), 8)])

        self.add_proxy(self.model.properties,
                       ['frequency', 'volume', 'samplerate', 'wave'])

        self.samplerate.set_sensitive(True)

    def workerChanged(self, worker):
        self.model.worker = worker
        self.wizard.requireElements(worker, 'audiotestsrc')

    def getNext(self):
        return None


class AudioTestWizardPlugin(object):
    implements(IProducerPlugin)

    def __init__(self, wizard):
        self.wizard = wizard
        self.model = TestAudioProducer()

    def getProductionStep(self, type):
        return TestAudioProducerStep(self.wizard, self.model)
