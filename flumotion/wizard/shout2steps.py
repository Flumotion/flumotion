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

from flumotion.wizard.models import Consumer
from flumotion.wizard.basesteps import ConsumerStep

__version__ = "$Rev$"
_ = gettext.gettext


class Shout2Consumer(Consumer):
    componentType = 'shout2-consumer'

    def __init__(self):
        super(Shout2Consumer, self).__init__()
        self.properties.ip = '127.0.0.1'
        self.properties.mount_point = '/'
        self.properties.description = ''
        self.properties.short_name = ''
        self.properties.url = 'http://localhost/'
        self.properties.password = ''


class Shout2Step(ConsumerStep):
    gladeFile = 'shout2-wizard.glade'

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
    title = _('Icecast streamer (audio and video)')
    sidebarName = _('Icecast audio/video')

    # ConsumerStep

    def getConsumerType(self):
        return 'audio-video'


class Shout2AudioStep(Shout2Step):
    name = 'Icecast streamer (audio only)'
    title = _('Icecast streamer (audio only)')
    sidebarName = _('Icecast audio')

    # ConsumerStep

    def getConsumerType(self):
        return 'audio'


class Shout2VideoStep(Shout2Step):
    name = 'Icecast streamer (video only)'
    title = _('Icecast streamer (video only)')
    sidebarName = _('Icecast video')

    # ConsumerStep

    def getConsumerType(self):
        return 'video'
