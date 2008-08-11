# -*- Mode: Python -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# Flumotion - a streaming media server
# Copyright (C) 2008 Fluendo, S.L. (www.fluendo.com).
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

import gettext
import os

from zope.interface import implements

from flumotion.admin.assistant.interfaces import IProducerPlugin
from flumotion.admin.assistant.models import AudioProducer
from flumotion.wizard.basesteps import AudioProducerStep

__version__ = "$Rev$"
_ = gettext.gettext


class TestAudioProducer(AudioProducer):
    componentType = 'audiotest-producer'

    def __init__(self):
        super(TestAudioProducer, self).__init__()

        self.properties.rate = '44100'


class TestAudioProducerStep(AudioProducerStep):
    name = 'TestAudioProducer'
    title = _('Test Audio Producer')
    icon = 'soundcard.png'
    gladeFile = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                              'wizard.glade')

    # WizardStep

    def setup(self):
        self.rate.data_type = str
        self.volume.data_type = float

        self.rate.prefill(['8000',
                           '16000',
                           '32000',
                           '44100'])

        self.add_proxy(self.model.properties,
                       ['frequency', 'volume', 'rate'])

        self.rate.set_sensitive(True)

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
