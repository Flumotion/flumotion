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

from flumotion.admin.assistant.interfaces import IEncoderPlugin
from flumotion.admin.assistant.models import VideoEncoder
from flumotion.admin.gtk.basesteps import VideoEncoderStep

__version__ = "$Rev$"
_ = gettext.gettext


class SmokeVideoEncoder(VideoEncoder):
    componentType = 'smoke-encoder'

    def __init__(self):
        super(SmokeVideoEncoder, self).__init__()
        self.properties.qmin = 10
        self.properties.qmax = 85
        self.properties.threshold = 3000
        self.properties.keyframe = 20


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
        self.keyframe.data_type = int

        self.add_proxy(self.model.properties,
                       ['qmin', 'qmax', 'threshold', 'keyframe'])

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
