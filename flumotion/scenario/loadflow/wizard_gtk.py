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
from flumotion.scenario.steps.loadflowstep import LoadFlowStep
from flumotion.scenario.steps.summarysteps import LiveSummaryStep

_ = gettext.gettext


class LoadFlowAssistantPlugin(object):
    implements(IScenarioAssistantPlugin)
    short = _("Load flow")
    description = _(
        """Allows you to load an existing flow file to set up a flow.
        """)

    # IScenarioAssistantPlugin

    def addSteps(self, wizard):
        wizard.addStepSection(LoadFlowStep)
        wizard.addStepSection(LiveSummaryStep)

    def save(self, wizard, saver):
        step = wizard.getStep('LoadFlow')
        xmlFile = step.getFlowFilename()
        saver.setFlowFile(xmlFile)

    def getSelectComponentName(self):
        return None
