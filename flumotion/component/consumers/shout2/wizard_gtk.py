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

from flumotion.admin.assistant.interfaces import IConsumerPlugin
from flumotion.admin.assistant.models import Consumer
from flumotion.admin.gtk.basesteps import ConsumerStep

__version__ = "$Rev$"
_ = gettext.gettext


class Shout2Consumer(Consumer):
    componentType = 'shout2-consumer'
    prefix = 'shout2'

    def __init__(self):
        super(Shout2Consumer, self).__init__()
        self.properties.ip = '127.0.0.1'
        self.properties.mount_point = '/'
        self.properties.description = ''
        self.properties.short_name = ''
        self.properties.url = 'http://localhost/'
        self.properties.password = ''


class Shout2Step(ConsumerStep):
    gladeFile = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                              'wizard.glade')

    def __init__(self, wizard):
        self.model = Shout2Consumer()
        ConsumerStep.__init__(self, wizard)

    # ConsumerStep

    def getConsumerModel(self):
        return self.model

    # WizardStep

    def setup(self):
        self.ip.data_type = str
        self.port.data_type = int
        self.mount_point.data_type = str
        self.password.data_type = str
        self.short_name.data_type = str
        self.description.data_type = str
        self.url.data_type = str

        self.add_proxy(self.model.properties,
                       ['ip',
                        'port',
                        'mount_point',
                        'short_name',
                        'password',
                        'description',
                        'url'])

    def workerChanged(self, worker):
        self.model.worker = worker
        self.wizard.checkElements(worker, 'shout2send')


class Shout2BothStep(Shout2Step):
    name = 'Icecast streamer (audio & video)'
    title = _('Icecast Streamer (Audio and Video)')
    sidebarName = _('Icecast audio/video')
    docSection = 'help-configuration-assistant-icecast-streaming-both'
    docAnchor = ''
    docVersion = 'local'

    # ConsumerStep

    def getConsumerType(self):
        return 'audio-video'


class Shout2AudioStep(Shout2Step):
    name = 'Icecast streamer (audio only)'
    title = _('Icecast Streamer (Audio Only)')
    sidebarName = _('Icecast Audio')
    docSection = 'help-configuration-assistant-icecast-streaming-audio-only'
    docAnchor = ''
    docVersion = 'local'

    # ConsumerStep

    def getConsumerType(self):
        return 'audio'


class Shout2VideoStep(Shout2Step):
    name = 'Icecast streamer (video only)'
    title = _('Icecast Streamer (Video Only)')
    sidebarName = _('Icecast Video')
    docSection = 'help-configuration-assistant-icecast-streaming-video-only'
    docAnchor = ''
    docVersion = 'local'

    # ConsumerStep

    def getConsumerType(self):
        return 'video'


class Shout2ConsumerWizardPlugin(object):
    implements(IConsumerPlugin)

    def __init__(self, wizard):
        self.wizard = wizard

    def getConsumptionStep(self, type):
        if type == 'video':
            return Shout2VideoStep(self.wizard)
        elif type == 'audio':
            return Shout2AudioStep(self.wizard)
        elif type == 'audio-video':
            return Shout2BothStep(self.wizard)
