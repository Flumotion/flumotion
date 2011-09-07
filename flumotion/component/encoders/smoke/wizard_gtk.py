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

from flumotion.admin.assistant.interfaces import IEncoderPlugin
from flumotion.admin.assistant.models import VideoEncoder
from flumotion.admin.gtk.basesteps import VideoEncoderStep
from flumotion.common.fraction import fractionAsFloat

__version__ = "$Rev$"
_ = gettext.gettext


class SmokeVideoEncoder(VideoEncoder):
    componentType = 'smoke-encoder'

    def __init__(self):
        super(SmokeVideoEncoder, self).__init__()
        self.framerate = 25.0
        self.keyframe_interval = 2.0

        self.properties.qmin = 10
        self.properties.qmax = 85
        self.properties.threshold = 3000

    def getProperties(self):
        properties = super(SmokeVideoEncoder, self).getProperties()

        properties.keyframe = int(self.framerate * self.keyframe_interval)

        return properties


class SmokeStep(VideoEncoderStep):
    name = 'SmokeEncoder'
    title = _('Smoke Encoder')
    sidebarName = _('Smoke')
    section = _('Conversion')
    gladeFile = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                              'wizard.glade')
    componentType = 'smoke'
    docSection = 'help-configuration-assistant-encoder-smoke'
    docAnchor = ''
    docVersion = 'local'

    # WizardStep

    def setup(self):
        self.qmin.data_type = int
        self.qmax.data_type = int
        self.threshold.data_type = int
        self.keyframe_interval.data_type = float

        producer = self.wizard.getScenario().getVideoProducer(self.wizard)
        self.model.framerate = fractionAsFloat(producer.getFramerate())
        self.model.keyframe_interval = 20 / self.model.framerate

        self.add_proxy(self.model.properties,
                       ['qmin', 'qmax', 'threshold'])
        self.add_proxy(self.model, ['keyframe_interval'])

        step = 1 / self.model.framerate
        page = 1.0
        self.keyframe_interval.set_increments(step, page)

    def workerChanged(self, worker):
        self.model.worker = worker
        self.wizard.requireElements(worker, 'smokeenc')


class SmokeWizardPlugin(object):
    implements(IEncoderPlugin)

    def __init__(self, wizard):
        self.wizard = wizard
        self.model = SmokeVideoEncoder()

    def getConversionStep(self):
        return SmokeStep(self.wizard, self.model)
