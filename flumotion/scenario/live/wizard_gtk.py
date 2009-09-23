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
from flumotion.scenario.steps.productionsteps import SelectProducersStep, \
        LiveProductionStep
from flumotion.scenario.steps.consumptionsteps import ConsumptionStep
from flumotion.scenario.steps.conversionsteps import ConversionStep, \
        SelectFormatStep
from flumotion.scenario.steps.licensestep import LicenseStep
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
        self._muxer = None

    # IScenarioAssistantPlugin

    def addSteps(self, wizard):
        if self._mode == 'normal':
            wizard.addStepSection(LiveProductionStep)
        elif self._mode == 'addformat':
            self._selectProducerStep = SelectProducersStep(wizard)
            wizard.addStepSection(self._selectProducerStep)
        elif self._mode == 'addstreamer':
            self._selectFormatStep = SelectFormatStep(wizard)
            wizard.addStepSection(self._selectFormatStep)

        if self._mode != 'addstreamer':
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
        if self._muxer:
            saver.addMuxer(self._muxer.type, self._muxer)
        else:
            saver.setMuxer(encodingStep.getMuxerType(), encodingStep.worker)

        httpPorters = wizard.getHTTPPorters()
        steps = list(self._getConsumptionSteps(wizard))

        for step in steps:
            consumerType = step.getConsumerType()
            consumer = step.getConsumerModel()
            if consumer.componentType == 'http-streamer':
                porter = self._obtainPorter(httpPorters, consumer.getPorter())

                if porter not in httpPorters:
                    saver.addPorter(porter, 'http')
                    httpPorters.append(porter)
                consumer.setPorter(porter)
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
        if not mode in ['normal', 'addformat', 'addstreamer']:
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
        if not wizard.hasStep('Production'):
            return None

        productionStep = wizard.getStep('Production')
        return productionStep.getAudioProducer()

    def getVideoProducer(self, wizard):
        """Returns the selected video producer or None
        @returns: producer or None
        @rtype: L{flumotion.admin.assistant.models.VideoProducer}
        """
        if not wizard.hasStep('Production'):
            return None

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

    def setExistingMuxer(self, muxer):
        self._muxer = muxer

    def setAudioProducers(self, audioProducers):
        self._selectProducerStep.setAudioProducers(audioProducers)

    def setVideoProducers(self, videoProducers):
        self._selectProducerStep.setVideoProducers(videoProducers)

    def setMuxers(self, muxers):
        self._selectFormatStep.setMuxers(muxers)

    # Private

    def _getConsumptionSteps(self, wizard):
        """Fetches the consumption steps chosen by the user
        @returns: consumption steps
        @rtype: generator of a L{ConsumerStep} instances
        """
        for step in wizard.getVisitedSteps():
            if isinstance(step, ConsumerStep):
                yield step

    def _obtainPorter(self, actualPorters, consumerPorter):
        """
        Looks if the consumerPorter has been already created and is inside
        the actualPorters list. If it is so, we return the existent porter,
        otherwise we return the consumerPorter.

        @param actualPorters : list of already exsisting porters.
        @type  actualPorters : list of L{flumotion.assistant.models.Porter}
        @param consumerPorter: porter model created by the consumer.
        @type  consumerPorter: L{flumotion.assistant.models.Porter}

        @rtype : L{flumotion.assistant.models.Porter}
        """
        for porter in actualPorters:
            p1 = porter.getProperties()
            p2 = consumerPorter.getProperties()

            if p1.port == p2.port and porter.worker == consumerPorter.worker:
                return porter

        return consumerPorter
