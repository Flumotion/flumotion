# -*- Mode: Python -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# Flumotion - a streaming media server
# Copyright (C) 2004,2005,2006,2007,2008 Fluendo, S.L. (www.fluendo.com).
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

from flumotion.admin.assistant.interfaces import IConsumerPlugin
from flumotion.admin.assistant.models import Consumer
from flumotion.admin.gtk.basesteps import ConsumerStep

__version__ = "$Rev$"
_ = gettext.gettext


class FGDPConsumer(Consumer):
    componentType = 'gdp-consumer'
    prefix = 'fgdp'

    def __init__(self):
        super(FGDPConsumer, self).__init__()
        self.properties.host = '127.0.0.1'
        self.properties.port = 15000
        self.properties.username = 'user'
        self.properties.password = 'test'


class FGDPStep(ConsumerStep):
    gladeFile = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                              'wizard.glade')

    def __init__(self, wizard):
        self.model = FGDPConsumer()
        ConsumerStep.__init__(self, wizard)

    # ConsumerStep

    def getConsumerModel(self):
        return self.model

    # WizardStep

    def setup(self):
        self.host.data_type = str
        self.port.data_type = int
        self.username.data_type = str
        self.password.data_type = str

        self.add_proxy(self.model.properties,
                       ['host',
                        'port',
                        'username',
                        'password'])

    def workerChanged(self, worker):
        self.model.worker = worker
        self.wizard.checkElements(worker, 'fgdpsend')


class FGDPBothStep(FGDPStep):
    name = 'FGDP streamer (audio & video)'
    title = _('FGDP Streamer (Audio and Video)')
    sidebarName = _('FGDP audio/video')
    docSection = 'help-configuration-assistant-fgdp-streaming-both'
    docAnchor = ''
    docVersion = 'local'

    # ConsumerStep

    def getConsumerType(self):
        return 'audio-video'


class FGDPAudioStep(FGDPStep):
    name = 'FGDP streamer (audio only)'
    title = _('FGDP Streamer (Audio Only)')
    sidebarName = _('FGDP Audio')
    docSection = 'help-configuration-assistant-fgdp-streaming-audio-only'
    docAnchor = ''
    docVersion = 'local'

    # ConsumerStep

    def getConsumerType(self):
        return 'audio'


class FGDPVideoStep(FGDPStep):
    name = 'FGDP streamer (video only)'
    title = _('FGDP Streamer (Video Only)')
    sidebarName = _('FGDP Video')
    docSection = 'help-configuration-assistant-fgdp-streaming-video-only'
    docAnchor = ''
    docVersion = 'local'

    # ConsumerStep

    def getConsumerType(self):
        return 'video'


class FGDPConsumerWizardPlugin(object):
    implements(IConsumerPlugin)

    def __init__(self, wizard):
        self.wizard = wizard

    def getConsumptionStep(self, type):
        if type == 'video':
            return FGDPVideoStep(self.wizard)
        elif type == 'audio':
            return FGDPAudioStep(self.wizard)
        elif type == 'audio-video':
            return FGDPBothStep(self.wizard)
