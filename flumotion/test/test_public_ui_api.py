# -*- Mode: Python -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# Flumotion - a streaming media server
# Copyright (C) 2004,2005,2006,2007 Fluendo, S.L. (www.fluendo.com).
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

from flumotion.common import testsuite


class TestPublicUI(testsuite.TestCase):

    def testPublicUIAPI(self):
        from flumotion.admin.admin import AdminModel
        from flumotion.admin.gtk import connections
        from flumotion.admin.gtk import dialogs
        from flumotion.admin.gtk import message
        from flumotion.admin.gtk.dialogs import ProgressDialog
        from flumotion.ui.glade import GladeWidget, GladeWindow
        from flumotion.ui.wizard import WizardStep
        from flumotion.wizard.configurationwizard import ConfigurationWizard

        from flumotion.ui import icons
        icons.register_icons()
