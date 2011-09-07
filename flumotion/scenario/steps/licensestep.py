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
