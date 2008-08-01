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

from flumotion.wizard.basesteps import AudioEncoderStep
from flumotion.wizard.interfaces import IEncoderPlugin
from flumotion.wizard.models import AudioEncoder

__version__ = "$Rev: 6359 $"
_ = gettext.gettext


class MulawAudioEncoder(AudioEncoder):
    componentType = 'mulaw-encoder'


class MulawStep(AudioEncoderStep):
    name = 'MulawEncoder'
    title = _('Mulaw encoder')
    sidebarName = _('Mulaw')
    section = _('Conversion')
    gladeFile = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                              'wizard.glade')
    componentType = 'mulaw-encoder'

    # WizardStep

    def workerChanged(self, worker):
        self.model.worker = worker
        self.wizard.requireElements(worker, 'mulawenc')


class MulawWizardPlugin(object):
    implements(IEncoderPlugin)

    def __init__(self, wizard):
        self.wizard = wizard
        self.model = MulawAudioEncoder()

    def getConversionStep(self):
        return MulawStep(self.wizard, self.model)
