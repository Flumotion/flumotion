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

from flumotion.wizard.models import Consumer
from flumotion.wizard.workerstep import WorkerWizardStep

__version__ = "$Rev$"
_ = gettext.gettext


class Shout2Consumer(Consumer):
    component_type = 'shout2-consumer'
    def __init__(self):
        super(Shout2Consumer, self).__init__()


class Shout2Step(WorkerWizardStep):
    glade_file = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                              'shout2-wizard.glade')
    section = _('Consumption')
    component_type = 'shout2'

    def __init__(self, wizard):
        self.model = Shout2Consumer()
        WorkerWizardStep.__init__(self, wizard)

    # Public API

    def getShout2Model(self):
        return self.model

    # WizardStep

    def setup(self):
        self.mount_point.data_type = str
        self.short_name.data_type = str
        self.description.data_type = str
        self.url.data_type = str
        self.port.data_type = int

        self.add_proxy(self.model.properties,
                       ['mount_point',
                        'short_name',
                        'description',
                        'url',
                        'port'])

    def worker_changed(self, worker):
        self.wizard.check_elements(worker, 'shout2send')

    def get_next(self):
        return self.wizard.get_step('Consumption').get_next(self)


class Shout2BothStep(Shout2Step):
    name = _('Icecast streamer (audio & video)')
    sidebar_name = _('Icecast audio/video')


class Shout2AudioStep(Shout2Step):
    name = _('Icecast streamer (audio only)')
    sidebar_name = _('Icecast audio')


class Shout2VideoStep(Shout2Step):
    name = _('Icecast streamer (video only)')
    sidebar_name = _('Icecast video')


