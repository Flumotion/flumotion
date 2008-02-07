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

from flumotion.wizard.basesteps import VideoEncoderStep
from flumotion.wizard.models import VideoEncoder

__version__ = "$Rev$"
_ = gettext.gettext


class TheoraVideoEncoder(VideoEncoder):
    component_type = 'theora-encoder'
    def __init__(self):
        super(TheoraVideoEncoder, self).__init__()
        self.has_quality = True
        self.has_bitrate = False

        self.properties.noise_sensitivity = 0
        self.properties.keyframe_maxdistance = 64
        self.properties.bitrate = 400
        self.properties.quality = 16
        self.properties.sharpness = 0

    def getProperties(self):
        properties = super(TheoraVideoEncoder, self).getProperties()
        if self.has_bitrate:
            del properties['quality']
            properties['bitrate'] *= 1000
        elif self.has_quality:
            del properties['bitrate']
        else:
            raise AssertionError

        properties['noise-sensitivity'] = max(
            int(properties['noise-sensitivity'] * (32768 / 100.)),  1)

        return properties


class TheoraStep(VideoEncoderStep):
    name = _('Theora encoder')
    sidebar_name = _('Theora')
    glade_file = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                              'theora-wizard.glade')
    component_type = 'theora'
    icon = 'xiphfish.png'

    # WizardStep

    def setup(self):
        self.bitrate.data_type = int
        self.quality.data_type = int
        self.noise_sensitivity.data_type = int
        self.keyframe_maxdistance.data_type = int
        self.sharpness.data_type = int
        self.has_quality.data_type = bool
        self.has_bitrate.data_type = bool

        self.add_proxy(self.model,
                       ['has_quality', 'has_bitrate'])
        self.add_proxy(self.model.properties,
                       ['bitrate', 'quality', 'keyframe_maxdistance',
                        'noise_sensitivity', 'sharpness'])

    def get_next(self):
        return self.wizard.get_step('Encoding').get_audio_page()

    def worker_changed(self, worker):
        self.model.worker = worker

        def hasTheora(unused, worker):
            self.wizard.run_in_worker(
                worker, 'flumotion.worker.checks.encoder', 'checkTheora')

        self.wizard.debug('running Theora checks')
        d = self.wizard.require_elements(worker, 'theoraenc')
        d.addCallback(hasTheora, worker)

    # Callbacks

    def on_radiobutton_toggled(self, button):
        # This is bound to both radiobutton_bitrate and radiobutton_quality
        self.bitrate.set_sensitive(self.has_bitrate.get_active())
        self.quality.set_sensitive(self.has_quality.get_active())


class TheoraWizardPlugin(object):
    def __init__(self, wizard):
        self.wizard = wizard
        self.model = TheoraVideoEncoder()

    def getConversionStep(self):
        return TheoraStep(self.wizard, self.model)
