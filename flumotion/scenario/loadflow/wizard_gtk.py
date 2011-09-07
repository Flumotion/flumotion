# -*- Mode: Python -*-
# vi:si:et:sw=4:sts=4:ts=4

# Flumotion - a streaming media server
# Copyright (C) 2004,2005,2006,2007,2008,2009 Fluendo, S.L.
# Copyright (C) 2010,2011 Flumotion Services, S.A.
# All rights reserved.
#
# This file may be distributed and/or modified under the terms of
# the GNU Lesser General Public License version 2.1 as published by
# the Free Software Foundation.
# This file is distributed without any warranty; without even the implied
# warranty of merchantability or fitness for a particular purpose.
# See "LICENSE.LGPL" in the source distribution for more information.
#
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
