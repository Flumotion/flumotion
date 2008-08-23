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
from flumotion.admin.assistant.models import AudioEncoder
from flumotion.admin.gtk.basesteps import AudioEncoderStep

__version__ = "$Rev$"
_ = gettext.gettext


class VorbisAudioEncoder(AudioEncoder):
    componentType = 'vorbis-encoder'

    def __init__(self):
        super(VorbisAudioEncoder, self).__init__()
        self.has_bitrate = True
        self.has_quality = False

        self.properties.bitrate = 64
        self.properties.quality = 0.5

    def getProperties(self):
        properties = super(VorbisAudioEncoder, self).getProperties()
        if self.has_bitrate:
            del properties.quality
            properties.bitrate *= 1000
        elif self.has_quality:
            del properties.bitrate
        else:
            raise AssertionError

        return properties


class VorbisStep(AudioEncoderStep):
    name = 'Vorbis encoder'
    title = _('Vorbis encoder')
    sidebarName = _('Vorbis')
    icon = 'xiphfish.png'
    gladeFile = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                              'wizard.glade')
    componentType = 'vorbis'
    docSection = 'help-configuration-assistant-encoder-vorbis'
    docAnchor = ''
    docVersion = 'local'

    # WizardStep

    def setup(self):
        self.has_bitrate.data_type = bool
        self.has_quality.data_type = bool
        self.bitrate.data_type = int
        self.quality.data_type = float

        self.add_proxy(self.model,
                       ['has_quality', 'has_bitrate'])
        self.add_proxy(self.model.properties,
                       ['bitrate', 'quality'])

    def workerChanged(self, worker):
        self.model.worker = worker

        def hasVorbis(unused, worker):
            self.wizard.runInWorker(
                worker, 'flumotion.worker.checks.encoder', 'checkVorbis')

        self.wizard.debug('running Vorbis checks')
        d = self.wizard.requireElements(worker, 'vorbisenc')
        d.addCallback(hasVorbis, worker)

    # Callbacks

    def on_radiobutton_toggled(self, button):
        # This is bound to both radiobutton_bitrate and radiobutton_quality
        self.bitrate.set_sensitive(self.has_bitrate.get_active())
        self.quality.set_sensitive(self.has_quality.get_active())


class VorbisWizardPlugin(object):
    implements(IEncoderPlugin)

    def __init__(self, wizard):
        self.wizard = wizard
        self.model = VorbisAudioEncoder()

    def getConversionStep(self):
        return VorbisStep(self.wizard, self.model)
