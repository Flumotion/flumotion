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

"""A wizard step for configuring an on demand stream
"""

import gettext
from os.path import dirname, basename

import gobject
import gtk

from flumotion.ui.wizard import WizardStep
from flumotion.common import messages
from flumotion.common.i18n import N_, gettexter
from flumotion.ui.fileselector import FileSelectorDialog

__version__ = "$Rev$"
_ = gettext.gettext
T_ = gettexter()


class LoadConfigurationStep(WizardStep):
    """I am a step of the wizard which allows you to use an existing
    configuration file to set up the server
    """
    name = 'LoadConfiguration'
    title = _('Load Configuration')
    sidebarName = _('Configuration')
    section = _('Configuration')
    gladeFile = 'loadconf-wizard.glade'
    docSection = 'help-configuration-assistant-loadconf'
    docAnchor = ''
    docVersion = 'local'

    # WizardStep

    def setup(self):
        self.filename.data_type = str

    def getNext(self):
        return None

    # Public

    def getConfigurationFilename(self):
        return self.filename.get_text()

    # Callbacks

    def on_select__clicked(self, button):
        dialog = gtk.FileChooserDialog(
            _("Import Configuration..."), self._window,
            gtk.FILE_CHOOSER_ACTION_OPEN,
            (gtk.STOCK_CANCEL, gtk.RESPONSE_REJECT,
             _('Import'), gtk.RESPONSE_ACCEPT))
        dialog.set_modal(True)
        dialog.set_default_response(gtk.RESPONSE_ACCEPT)
        ffilter = gtk.FileFilter()
        ffilter.set_name(_("Flumotion XML Configuration files"))
        ffilter.add_pattern("*.xml")
        dialog.add_filter(ffilter)
        ffilter = gtk.FileFilter()
        ffilter.set_name(_("All files"))
        ffilter.add_pattern("*")
        dialog.add_filter(ffilter)

        def response(dialog, response):
            if response == gtk.RESPONSE_ACCEPT:
                self.filename.set_text(dialog.get_filename())
            dialog.destroy()

        dialog.connect('response', response)
        dialog.show()
