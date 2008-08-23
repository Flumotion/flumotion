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

import gobject
import gtk

from flumotion.common import messages

from flumotion.admin.assistant.models import HTTPServer
from flumotion.admin.gtk.workerstep import WorkerWizardStep
from flumotion.common.i18n import N_, gettexter
from flumotion.ui.fileselector import FileSelectorDialog

__version__ = "$Rev$"
_ = gettext.gettext
T_ = gettexter()


class OnDemand(HTTPServer):
    """I am a model representing the configuration file for a
    an on demand HTTP server component.
    """
    componentType = 'http-server'

    def __init__(self, worker=None):
        super(OnDemand, self).__init__(worker, mountPoint='/')
        self.properties.path = '/tmp'
        self.properties.port = 8800

    # Component

    def getProperties(self):
        properties = super(OnDemand, self).getProperties()

        return properties


class OnDemandStep(WorkerWizardStep):
    """I am a step of the configuration wizard which allows you
    to configure an on demand configuration over HTTP
    """
    name = 'Demand'
    title = _('Demand')
    sidebarName = _('On demand')
    section = _('Production')
    gladeFile = 'ondemand-wizard.glade'
    docSection = 'help-configuration-assistant-ondemand'
    docAnchor = ''
    docVersion = 'local'

    def __init__(self, wizard):
        self.model = OnDemand()
        self._idleId = -1
        WorkerWizardStep.__init__(self, wizard)

    # WizardStep

    def setup(self):
        self.path.data_type = str
        self.port.data_type = int
        self.mount_point.data_type = str

        self._proxy = self.add_proxy(self.model.properties,
                       ['path',
                        'port',
                        'mount_point'])

        self.mount_point.set_text("/")

    def workerChanged(self, worker):
        self.model.worker = worker
        self._runChecks()

    def getNext(self):
        return None

    # Public

    def getServerConsumer(self):
        return self.model

    # Private

    def _runChecks(self):
        self.wizard.waitForTask('ondemand check')

        def importError(failure):
            failure.trap(ImportError)
            self.info('could not import twisted-web')
            message = messages.Warning(T_(N_(
                "Worker '%s' cannot import module '%s'."),
                self.worker, 'twisted.web'))
            message.add(T_(N_("\nThis module is part of the '%s'."),
                           'Twisted Project'))
            message.add(T_(N_("\nThe project's homepage is %s"),
                           'http://www.twistedmatrix.com/'))
            message.id = 'module-twisted-web'
            self.wizard.add_msg(message)
            self.wizard.taskFinished(True)

        def checkPathFinished(pathExists, path):
            if not pathExists:
                message = messages.Warning(T_(N_(
                    "Directory '%s' does not exist, "
                    "or is not readable on worker '%s'.")
                                  % (path, self.worker)))
                message.id = 'demand-directory-check'
                self.wizard.add_msg(message)
            else:
                self.wizard.clear_msg('demand-directory-check')

            self.wizard.taskFinished(blockNext=not pathExists)

        def checkPath(unused):
            path = self.path.get_text()
            d = self.runInWorker('flumotion.worker.checks.check',
                                 'checkDirectory', path)
            d.addCallback(checkPathFinished, path)

        d = self.wizard.checkImport(self.worker, 'twisted.web')
        d.addCallback(checkPath)
        d.addErrback(importError)

    def _abortScheduledCheck(self):
        if self._idleId != -1:
            gobject.source_remove(self._idleId)
            self._idleId = -1

    def _scheduleCheck(self):
        self._abortScheduledCheck()
        self._idleId = gobject.timeout_add(300, self._runChecks)

    def _verify(self):
        self._updateBlocked()

    def _updateBlocked(self):
        # FIXME: This should be updated and only called when all pending
        #        tasks are done.
        self.wizard.blockNext(self.mount_point.get_text() == '')

    def _showFileSelector(self):

        def response(fs, response):
            fs.hide()
            if response == gtk.RESPONSE_OK:
                self.model.properties.path = fs.getFilename()
                self._proxy.update('path')

        def deleteEvent(fs, event):
            pass
        fs = FileSelectorDialog(self.wizard.window,
                                self.wizard.getAdminModel())
        fs.connect('response', response)
        fs.connect('delete-event', deleteEvent)
        fs.selector.setWorkerName(self.model.worker)
        fs.setDirectory(self.model.properties.path)
        fs.show_all()

    # Callbacks

    def on_mount_point_changed(self, entry):
        self._verify()
        self.wizard.blockNext(entry.get_text() == "/")

    def on_path__changed(self, entry):
        self._scheduleCheck()

    def on_select__clicked(self, button):
        self._showFileSelector()
