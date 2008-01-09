# -*- Mode: Python -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# Flumotion - a streaming media server
# Copyright (C) 2008 Fluendo, S.L. (www.fluendo.com).
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

from flumotion.wizard.basesteps import VideoSourceStep

__version__ = "$Rev$"
_ = gettext.gettext


class TestVideoSourceStep(VideoSourceStep):
    name = _('Test Video Source')
    glade_file = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                              'videotest-wizard.glade')
    component_type = 'videotestsrc'
    icon = 'testsource.png'

    # WizardStep

    def setup(self):
        self.pattern.data_type = int
        self.format.data_type = str
        self.framerate.data_type = float

        self.pattern.prefill([
            (_('SMPTE Color bars'), 0),
            (_('Random (television snow)'), 1),
            (_('Totally black'), 2)])
        self.format.prefill([
            (_('YUV'), 'video/x-raw-yuv'),
            (_('RGB'), 'video/x-raw-rgb')])

        self.model.properties.pattern = 0
        self.model.properties.format = 'video/x-raw-yuv'

        self.add_proxy(self.model.properties,
                       ['pattern', 'width', 'height',
                        'framerate', 'format'])

    def before_show(self):
        self.wizard.require_elements(self.worker, 'videotestsrc')

    def worker_changed(self):
        self.model.worker = self.worker


class VideoTestWizardPlugin(object):
    def __init__(self, wizard):
        self.wizard = wizard

    def get_production_step(self):
        return TestVideoSourceStep

