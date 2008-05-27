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

from flumotion.wizard.models import AudioProducer, VideoProducer
from flumotion.wizard.configurationwizard import ConfigurationWizard, \
     ConversionStep, ConsumptionStep, SummaryStep


class AddFormatWizard(ConfigurationWizard):
    def __init__(self, parent=None):
        ConfigurationWizard.__init__(self, parent)
        self._audioProducer = None
        self._videoProducer = None

    # ConfigurationWizard
    
    def addSteps(self):
        self.addStepSection(ConversionStep)
        self.addStepSection(ConsumptionStep)
        self.addStepSection(SummaryStep)

    def setAudioProducer(self, name, componentType):
        self._audioProducer = AudioProducer()
        self._audioProducer.exists = True
        self._audioProducer.name = name
        self._audioProducer.componentType = componentType
        return self._audioProducer

    def setVideoProducer(self, name, componentType):
        self._videoProducer = VideoProducer()
        self._videoProducer.exists = True
        self._videoProducer.name = name
        self._videoProducer.componentType = componentType
        return self._videoProducer

    def hasAudio(self):
        return bool(self._audioProducer)
    
    def hasVideo(self):
        return bool(self._videoProducer)
    
    def getAudioProducer(self):
        return self._audioProducer

    def getVideoProducer(self):
        return self._videoProducer
