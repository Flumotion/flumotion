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

"""Scenarios for the ConfigurationAssistant

This file contains the base classes, common steps
and two basic scenarios for the configuration wizard.
"""
import gettext

from flumotion.admin.assistant.save import AssistantSaver
from flumotion.ui.wizard import WizardStep
from flumotion.admin.gtk.basesteps import ConsumerStep
from flumotion.admin.gtk.consumptionsteps import ConsumptionStep
from flumotion.admin.gtk.conversionsteps import ConversionStep
from flumotion.admin.gtk.ondemandstep import OnDemandStep
from flumotion.admin.gtk.productionsteps import LiveProductionStep

_ = gettext.gettext


class LicenseStep(WizardStep):
    name = "ContentLicense"
    title = _("Content License")
    section = _('License')
    icon = 'licenses.png'
    gladeFile = "license-wizard.glade"
    docSection = 'help-configuration-assistant-license'
    docAnchor = ''
    docVersion = 'local'

    # Public API

    def getLicenseType(self):
        """Get the selected license type
        @returns: the license type or None
        @rtype: string or None
        """
        if self.set_license.get_active():
            return self.license.get_selected()

    # WizardStep

    def setup(self):
        self.license.prefill([
            (_('Creative Commons'), 'CC'),
            (_('Commercial'), 'Commercial')])

    def getNext(self):
        return None

    # Callbacks

    def on_set_license__toggled(self, button):
        self.license.set_sensitive(button.get_active())


class SummaryStep(WizardStep):
    name = "Summary"
    title = _("Summary")
    section = _("Summary")
    icon = 'summary.png'
    gladeFile = "summary-wizard.glade"
    lastStep = True
    docSection = 'help-configuration-assistant-summary'
    docAnchor = ''
    docVersion = 'local'

    # WizardStep

    def getNext(self):
        return None


class Scenario(object):
    """Base class for Scenarios

    A scenario decides the following::
      - Which steps should be shown
      - How the configuration for the steps should be saved
    """

    def __init__(self, wizard):
        self.wizard = wizard
        self._flowName = 'default'
        self._existingComponentNames = []

    def getSaver(self):
        """Returns a wizard saver that should be used to save the
        configuration generated to be created by this scenario.
        @returns: the wizard saver
        @rtype: L{AssistantSaver}
        """
        saver = AssistantSaver()
        saver.setFlowName(self._flowName)
        saver.setExistingComponentNames(self._existingComponentNames)
        return saver

    def setExistingComponentNames(self, componentNames):
        """Tells the scenario about the existing components available, so
        we can resolve naming conflicts when saving the configuration
        @param componentNames: existing component names
        @type componentNames: list of strings
        """
        self._existingComponentNames = componentNames

    def addSteps(self):
        """Add the wizard section steps specific for this scenario"""
        raise NotImplementedError("%s.addSteps" % (
            self.__class__.__name__, ))

    def save(self):
        """Save the content of the wizard
        Can be overridden in a subclass
        @returns: wizard saver
        @rtype: L{AssistantSaver}
        """
        raise NotImplementedError("%s.save" % (
            self.__class__.__name__, ))


class LiveScenario(Scenario):
    short = _("Set up a live stream")
    description = _(
        """Allows you to create a live stream from a device or a file.
        """)

    # Scenario

    def addSteps(self):
        self.wizard.addStepSection(LiveProductionStep)
        self.wizard.addStepSection(ConversionStep)
        self.wizard.addStepSection(ConsumptionStep)
        self.wizard.addStepSection(LicenseStep)
        self.wizard.addStepSection(SummaryStep)

    def save(self):
        saver = self.getSaver()

        saver.setAudioProducer(self.wizard.getAudioProducer())
        saver.setVideoProducer(self.wizard.getVideoProducer())

        productionStep = None
        if self.wizard.hasStep('Production'):
            productionStep = self.wizard.getStep('Production')

        if productionStep and productionStep.hasVideo():
            if self.wizard.hasStep('Overlay'):
                overlayStep = self.wizard.getStep('Overlay')
                saver.setVideoOverlay(overlayStep.getOverlay())

        encodingStep = self.wizard.getStep('Encoding')
        saver.setAudioEncoder(self.wizard.getAudioEncoder())
        saver.setVideoEncoder(self.wizard.getVideoEncoder())
        saver.setMuxer(encodingStep.getMuxerType(), encodingStep.worker)

        consumptionStep = self.wizard.getStep('Consumption')
        httpPorter = None
        if consumptionStep.haveHTTP():
            httpPorter = consumptionStep.getHTTPPorter()
            existingPorter = self.wizard.getHTTPPorter()
            if existingPorter is None:
                self.wizard.setHTTPPorter(httpPorter)
            elif existingPorter.properties.port == httpPorter.properties.port:
                httpPorter = existingPorter
                assert httpPorter.exists, httpPorter
            saver.addPorter(httpPorter, 'http')

        for step in self._getConsumptionSteps():
            consumerType = step.getConsumerType()
            consumer = step.getConsumerModel()
            if httpPorter is not None:
                consumer.setPorter(httpPorter)
            saver.addConsumer(consumer, consumerType)

            for server in step.getServerConsumers():
                saver.addServerConsumer(server, consumerType)

        if self.wizard.hasStep('ContentLicense'):
            licenseStep = self.wizard.getStep('ContentLicense')
            if licenseStep.getLicenseType() == 'CC':
                saver.setUseCCLicense(True)

        return saver

    # Private

    def _getConsumptionSteps(self):
        """Fetches the consumption steps chosen by the user
        @returns: consumption steps
        @rtype: generator of a L{ConsumerStep} instances
        """
        for step in self.wizard.getVisitedSteps():
            if isinstance(step, ConsumerStep):
                yield step


class OnDemandScenario(Scenario):
    short = _("Stream files on demand")
    description = _("""Allows you to serve a collection of files from disk.""")

    # Scenario

    def addSteps(self):
        self.wizard.addStepSection(OnDemandStep)
        self.wizard.addStepSection(SummaryStep)

    def save(self):
        saver = self.getSaver()

        ondemandStep = self.wizard.getStep('Demand')
        consumer = ondemandStep.getServerConsumer()
        saver.addServerConsumer(consumer, 'ondemand')
        return saver
