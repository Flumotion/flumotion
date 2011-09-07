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
from flumotion.admin.settings import getSettings

__version__ = "$Rev$"
_ = gettext.gettext
T_ = gettexter()


class LoadFlowStep(WizardStep):
    """I am a step of the wizard which allows you to use an existing
    configuration file to set up the server
    """
    name = 'LoadFlow'
    title = _('Load Flow')
    sidebarName = _('Load Flow')
    section = _('Load Flow')
    gladeFile = 'loadflow-wizard.glade'
    docSection = 'help-configuration-assistant-loadflow'
    docAnchor = ''
    docVersion = 'local'

    def activated(self):
        self.wizard.blockNext(True)

    # WizardStep

    def setup(self):
        self.filename.data_type = str

    def getNext(self):
        return None

    # Public

    def getFlowFilename(self):
        return self.filename.get_text()

    # Callbacks

    def on_select__clicked(self, button):
        settings = getSettings()
        dialog = gtk.FileChooserDialog(
            _("Import Flow..."), self._window,
            gtk.FILE_CHOOSER_ACTION_OPEN,
            (gtk.STOCK_CANCEL, gtk.RESPONSE_REJECT,
             _('Import'), gtk.RESPONSE_ACCEPT))
        dialog.set_modal(True)
        dialog.set_default_response(gtk.RESPONSE_ACCEPT)
        ffilter = gtk.FileFilter()
        ffilter.set_name(_("Flumotion XML Flow files"))
        ffilter.add_pattern("*.xml")
        dialog.add_filter(ffilter)
        ffilter = gtk.FileFilter()
        ffilter.set_name(_("All files"))
        ffilter.add_pattern("*")
        dialog.add_filter(ffilter)
        if settings.hasValue('import_dir'):
            dialog.set_current_folder_uri(settings.getValue('import_dir'))

        def response(dialog, response):
            if response == gtk.RESPONSE_ACCEPT:
                if settings.getValue('import_dir') != \
                        dialog.get_current_folder_uri():
                    settings.setValue('import_dir',
                                      dialog.get_current_folder_uri())
                    settings.save()
                self.filename.set_text(dialog.get_filename())
                self.wizard.blockNext(False)
            dialog.destroy()

        dialog.connect('response', response)
        dialog.show()
