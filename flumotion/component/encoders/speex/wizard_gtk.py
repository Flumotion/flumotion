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

from zope.interface import implements

from flumotion.admin.assistant.interfaces import IEncoderPlugin
from flumotion.admin.assistant.models import AudioEncoder
from flumotion.admin.gtk.basesteps import AudioEncoderStep

__version__ = "$Rev$"
_ = gettext.gettext


class SpeexAudioEncoder(AudioEncoder):
    componentType = 'speex-encoder'

    def __init__(self):
        super(SpeexAudioEncoder, self).__init__()

        self.properties.bitrate = 11

    def getProperties(self):
        properties = super(SpeexAudioEncoder, self).getProperties()
        properties.bitrate *= 1000
        return properties


class SpeexStep(AudioEncoderStep):
    name = 'Speex encoder'
    title = _('Speex encoder')
    sidebarName = _('Speex')
    componentType = 'speex'
    icon = 'xiphfish.png'
    docSection = 'help-configuration-assistant-encoder-speex'
    docAnchor = ''
    docVersion = 'local'

    # WizardStep

    def setup(self):
        # Should be 2150 instead of 3 -> 3000
        self.bitrate.set_range(3, 30)
        self.bitrate.set_value(11)

        self.bitrate.data_type = int

        self.add_proxy(self.model.properties, ['bitrate'])

    def workerChanged(self, worker):
        self.model.worker = worker
        self.wizard.requireElements(worker, 'speexenc')


class SpeexWizardPlugin(object):
    implements(IEncoderPlugin)

    def __init__(self, wizard):
        self.wizard = wizard
        self.model = SpeexAudioEncoder()

    def getConversionStep(self):
        return SpeexStep(self.wizard, self.model)
