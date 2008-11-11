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

from flumotion.ui.wizard import WizardStep

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
