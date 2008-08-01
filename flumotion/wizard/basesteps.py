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

from flumotion.common import messages
from flumotion.wizard.workerstep import WorkerWizardStep

__version__ = "$Rev$"
_ = gettext.gettext


class AudioProducerStep(WorkerWizardStep):
    section = _('Production')

    def __init__(self, wizard, model):
        self.model = model
        WorkerWizardStep.__init__(self, wizard)


class VideoProducerStep(WorkerWizardStep):
    section = _('Production')
    icon = 'widget_doc.png'

    def __init__(self, wizard, model):
        self.model = model
        WorkerWizardStep.__init__(self, wizard)

    # WizardStep

    def getNext(self):
        from flumotion.wizard.overlaystep import OverlayStep
        return OverlayStep(self.wizard, self.model)


class VideoEncoderStep(WorkerWizardStep):
    section = _('Conversion')

    def __init__(self, wizard, model):
        self.model = model
        WorkerWizardStep.__init__(self, wizard)

    def getNext(self):
        return self.wizard.getStep('Encoding').getAudioPage()


class AudioEncoderStep(WorkerWizardStep):
    gladeFile = 'audio-encoder-wizard.glade'
    section = _('Conversion')

    def __init__(self, wizard, model):
        self.model = model
        WorkerWizardStep.__init__(self, wizard)

    # WizardStep

    def getNext(self):
        return None


class ConsumerStep(WorkerWizardStep):
    section = _('Consumption')

    def getConsumerModel(self):
        raise NotImplementedError(self)

    def getComponentType(self):
        raise NotImplementedError(self)

    def getServerConsumers(self):
        """Returns the http-server consumer model or None
        if there will only a stream served.
        @returns: the server consumer or None
        """
        return []

    def getPorters(self):
        """Returns the porter model or None if there will only a stream served.
        @returns: the porter or None
        """
        return []

    # WizardStep

    def getNext(self):
        return self.wizard.getStep('Consumption').getNext(self)
