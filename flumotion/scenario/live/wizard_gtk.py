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

from zope.interface import implements

from flumotion.admin.assistant.interfaces import IScenarioAssistantPlugin
from flumotion.admin.gtk.basesteps import ConsumerStep
from flumotion.scenario.steps.productionsteps import SelectProducersStep
from flumotion.scenario.steps.consumptionsteps import ConsumptionStep
from flumotion.scenario.steps.conversionsteps import ConversionStep
from flumotion.scenario.steps.licensestep import LicenseStep
from flumotion.scenario.steps.productionsteps import LiveProductionStep
from flumotion.scenario.steps.summarysteps import LiveSummaryStep

_ = gettext.gettext


class LiveAssistantPlugin(object):
    """
    This is the live scenario which predefines the steps the wizard should take
    """

    implements(IScenarioAssistantPlugin)
    short = _("Stream live")
    description = _(
        """Allows you to create a live stream from a device or a file
        """)

    def __init__(self):
        self._selectProducerStep = None
        self._defaultConsumer = None
        self._mode = 'normal'
        self._videoEncoder = None
        self._audioEncoder = None
        self._muxerEntry = None

    # IScenarioAssistantPlugin

    def addSteps(self, wizard):
        if self._mode == 'normal':
            wizard.addStepSection(LiveProductionStep)
        elif self._mode == 'addformat':
            self._selectProducerStep = SelectProducersStep(wizard)
            wizard.addStepSection(self._selectProducerStep)

        wizard.addStepSection(ConversionStep)
        wizard.addStepSection(ConsumptionStep)

        if self._mode == 'normal':
            wizard.addStepSection(LicenseStep)
        wizard.addStepSection(LiveSummaryStep)

    def save(self, wizard, saver):
        saver.setAudioProducer(self.getAudioProducer(wizard))
        saver.setVideoProducer(self.getVideoProducer(wizard))

        productionStep = None
        if wizard.hasStep('Production'):
            productionStep = wizard.getStep('Production')

        if productionStep and productionStep.hasVideo():
            if wizard.hasStep('Overlay'):
                overlayStep = wizard.getStep('Overlay')
                saver.setVideoOverlay(overlayStep.getOverlay())

        encodingStep = wizard.getStep('Encoding')
        saver.setAudioEncoder(self.getAudioEncoder())
        saver.setVideoEncoder(self.getVideoEncoder())
        saver.setMuxer(encodingStep.getMuxerType(), encodingStep.worker)

        consumptionStep = wizard.getStep('Consumption')
        httpPorter = None
        if consumptionStep.haveHTTP():
            httpPorter = consumptionStep.getHTTPPorter()
            existingPorter = wizard.getHTTPPorter()
            if existingPorter is None:
                wizard.setHTTPPorter(httpPorter)
            elif existingPorter.properties.port == httpPorter.properties.port:
                httpPorter = existingPorter
                assert httpPorter.exists, httpPorter
            saver.addPorter(httpPorter, 'http')

        steps = list(self._getConsumptionSteps(wizard))
        for step in steps:
            consumerType = step.getConsumerType()
            consumer = step.getConsumerModel()
            if httpPorter is not None:
                consumer.setPorter(httpPorter)
            saver.addConsumer(consumer, consumerType)
            if not self._defaultConsumer:
                self._defaultConsumer = consumer
            for server in step.getServerConsumers():
                saver.addServerConsumer(server, consumerType)

        if wizard.hasStep('ContentLicense'):
            licenseStep = wizard.getStep('ContentLicense')
            if licenseStep.getLicenseType() == 'CC':
                saver.setUseCCLicense(True)

    def getSelectComponentName(self):
        return self._defaultConsumer.name

    def setMode(self, mode):
        if not mode in ['normal', 'addformat']:
            raise ValueError()

        self._mode = mode

    def hasAudio(self, wizard):
        """If the configured feed has a audio stream
        @return: if we have audio
        @rtype: bool
        """
        productionStep = wizard.getStep('Production')
        return productionStep.hasAudio()

    def hasVideo(self, wizard):
        """If the configured feed has a video stream
        @return: if we have video
        @rtype: bool
        """
        productionStep = wizard.getStep('Production')
        return productionStep.hasVideo()

    def getAudioProducer(self, wizard):
        """Returns the selected audio producer or None
        @returns: producer or None
        @rtype: L{flumotion.admin.assistant.models.AudioProducer}
        """
        productionStep = wizard.getStep('Production')
        return productionStep.getAudioProducer()

    def getVideoProducer(self, wizard):
        """Returns the selected video producer or None
        @returns: producer or None
        @rtype: L{flumotion.admin.assistant.models.VideoProducer}
        """
        productionStep = wizard.getStep('Production')
        return productionStep.getVideoProducer()

    def getVideoEncoder(self):
        """Returns the selected video encoder or None
        @returns: encoder or None
        @rtype: L{flumotion.admin.assistant.models.VideoEncoder}
        """
        return self._videoEncoder

    def getAudioEncoder(self):
        """Returns the selected audio encoder or None
        @returns: encoder or None
        @rtype: L{flumotion.admin.assistant.models.AudioEncoder}
        """
        return self._audioEncoder

    def setVideoEncoder(self, videoEncoder):
        """Select a video encoder
        @param videoEncoder: encoder or None
        @type videoEncoder: L{flumotion.admin.assistant.models.VideoEncoder}
        """
        self._videoEncoder = videoEncoder

    def setAudioEncoder(self, audioEncoder):
        """Select a audio encoder
        @param audioEncoder: encoder or None
        @type audioEncoder: L{flumotion.admin.assistant.models.AudioEncoder}
        """
        self._audioEncoder = audioEncoder

    def setMuxerEntry(self, muxerEntry):
        """Select a muxer entry
        @param audioEncoder: muxer entry
        """
        self._muxerEntry = muxerEntry

    def getMuxerEntry(self):
        """Returns the muxer entry
        @returns: the muxer entry
        """
        return self._muxerEntry

    def setAudioProducers(self, audioProducers):
        self._selectProducerStep.setAudioProducers(audioProducers)

    def setVideoProducers(self, videoProducers):
        self._selectProducerStep.setVideoProducers(videoProducers)

    # Private

    def _getConsumptionSteps(self, wizard):
        """Fetches the consumption steps chosen by the user
        @returns: consumption steps
        @rtype: generator of a L{ConsumerStep} instances
        """
        for step in wizard.getVisitedSteps():
            if isinstance(step, ConsumerStep):
                yield step
