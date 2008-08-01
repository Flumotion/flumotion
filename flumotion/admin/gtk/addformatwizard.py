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

"""assistant used to add new streamer format"""

from flumotion.wizard.configurationwizard import ConfigurationWizard
from flumotion.wizard.consumptionsteps import ConsumptionStep
from flumotion.wizard.conversionsteps import ConversionStep
from flumotion.wizard.scenarios import LiveScenario, SummaryStep
from flumotion.wizard.productionsteps import SelectProducersStep


class AddFormatWizard(ConfigurationWizard):
    def __init__(self, parent=None):
        self._selectProducerStep = None
        ConfigurationWizard.__init__(self, parent)
        self.setScenario(LiveScenario(self))

    # ConfigurationWizard

    def addSteps(self):
        self._selectProducerStep = SelectProducersStep(self)
        self.addStepSection(self._selectProducerStep)
        self.addStepSection(ConversionStep)
        self.addStepSection(ConsumptionStep)
        self.addStepSection(SummaryStep)

    def hasAudio(self):
        return self._selectProducerStep.hasAudio()

    def hasVideo(self):
        return self._selectProducerStep.hasVideo()

    def getAudioProducer(self):
        return self._selectProducerStep.getAudioProducer()

    def getVideoProducer(self):
        return self._selectProducerStep.getVideoProducer()

    # Public API

    def setAudioProducers(self, audioProducers):
        self._selectProducerStep.setAudioProducers(audioProducers)

    def setVideoProducers(self, videoProducers):
        self._selectProducerStep.setVideoProducers(videoProducers)
