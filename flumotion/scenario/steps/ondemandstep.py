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

from flumotion.admin.assistant.models import HTTPServer, Plug
from flumotion.admin.gtk.workerstep import WorkerWizardStep
from flumotion.common import messages
from flumotion.common.i18n import N_, gettexter
from flumotion.ui.fileselector import FileSelectorDialog

__version__ = "$Rev$"
_ = gettext.gettext
T_ = gettexter()


class LoggerPlug(Plug):

    plugType = 'requestlogger-file'

    def __init__(self, logfile):
        """
        @param videoProducer: video producer
        @type  videoProducer: L{flumotion.admin.assistant.models.VideoProducer}
          subclass or None
        """
        super(LoggerPlug, self).__init__()
        self.properties.logfile = logfile


class OnDemand(HTTPServer):
    """I am a model representing the configuration file for a
    an on demand HTTP server component.
    """
    componentType = 'http-server'

    def __init__(self, worker=None):
        super(OnDemand, self).__init__(worker, mountPoint='/')
        self.properties.path = '/tmp'
        self.properties.port = 8800

        self.add_logger = False
        self.logfile = '/tmp/access.log'

    # Component

    def getProperties(self):
        properties = super(OnDemand, self).getProperties()

        if self.add_logger:
            self.addPlug(LoggerPlug(self.logfile))

        return properties


class OnDemandStep(WorkerWizardStep):
    """I am a step of the configuration wizard which allows you
    to configure an on demand configuration over HTTP
    """
    name = 'Demand'
    title = _('On Demand')
    sidebarName = _('On Demand')
    section = _('Production')
    gladeFile = 'ondemand-wizard.glade'
    docSection = 'help-configuration-assistant-ondemand'
    docAnchor = ''
    docVersion = 'local'

    def __init__(self, wizard):
        self.model = OnDemand()
        self._idleId = -1
        self._blockNext = {}
        WorkerWizardStep.__init__(self, wizard)

    # WizardStep

    def setup(self):
        self.path.data_type = str
        self.port.data_type = int
        self.mount_point.data_type = str
        self.add_logger.data_type = bool
        self.logfile.data_type = str

        self._proxy = self.add_proxy(self.model.properties,
                       ['path',
                        'port',
                        'mount_point',
                       ])

        self._plugProxy = self.add_proxy(self.model,
                       ['add_logger',
                        'logfile',
                       ])

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
        self._runPathCheck(self.model.properties.path, 'path')
        if self.model.add_logger:
            self._runPathCheck(dirname(self.model.logfile), 'logfile')

    def _runPathCheck(self, path, id):
        self.wizard.waitForTask('ondemand check')
        self._blockNext[id] = True

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

        def checkPathFinished(pathExists):
            if not pathExists:
                message = messages.Warning(T_(N_(
                    "Directory '%s' does not exist, "
                    "or is not readable on worker '%s'.")
                    % (path, self.worker)))
                message.id = 'demand-'+id+'-check'
                self.wizard.add_msg(message)
            else:
                self.wizard.clear_msg('demand-'+id+'-check')
                self._blockNext[id] = False

            self.wizard.taskFinished()
            self._verify()

        def checkPath(unused):
            d = self.runInWorker('flumotion.worker.checks.check',
                                 'checkDirectory', path)
            d.addCallback(checkPathFinished)

        d = self.wizard.checkImport(self.worker, 'twisted.web')
        d.addCallback(checkPath)
        d.addErrback(importError)

    def _abortScheduledCheck(self):
        if self._idleId != -1:
            gobject.source_remove(self._idleId)
            self._idleId = -1

    def _scheduleCheck(self, checkToRun, data, id):
        self._abortScheduledCheck()
        self._idleId = gobject.timeout_add(300, checkToRun, data, id)

    def _clearMessage(self, id):
        self.wizard.clear_msg('demand-'+id+'-check')
        self._blockNext[id] = False

    def _verify(self):
        self.wizard.blockNext(reduce(lambda x, y: x or y,
                                     self._blockNext.values(),
                                     False))

    def _showFileSelector(self, response_cb, path, directoryOnly=False):

        def deleteEvent(fs, event):
            pass

        fs = FileSelectorDialog(self.wizard.window,
                                self.wizard.getAdminModel())

        fs.connect('response', response_cb)
        fs.connect('delete-event', deleteEvent)
        fs.selector.setWorkerName(self.model.worker)
        fs.selector.setOnlyDirectoriesMode(directoryOnly)
        fs.setDirectory(path)
        fs.show_all()

    # Callbacks

    # FIXME: Find a way to check whether the mount point is already taken.
    #        See #1186

    def on_mount_point__changed(self, entry):
        self._blockNext['mount-point'] = not entry.get_text()
        self._verify()

    def on_select_directory__clicked(self, button):

        def response(fs, response):
            fs.hide()
            if response == gtk.RESPONSE_OK:
                self.model.properties.path = fs.getFilename()
                self._proxy.update('path')

                self._clearMessage('path')
                self._verify()

        directory = self.model.properties.path

        self._showFileSelector(response,
                               path=directory,
                               directoryOnly=True)

    def on_select_logfile__activate(self, button):

        def response(fs, response):
            fs.hide()
            if response == gtk.RESPONSE_OK:
                directory = fs.getFilename()
                if directory == '/':
                    directory = ''
                filename = basename(self.model.logfile)

                self.model.logfile = "%s/%s" % (directory, filename)
                self._plugProxy.update('logfile')

                self._clearMessage('logfile')
                self._verify()

        self._showFileSelector(response,
                               path=self.model.logfile,
                               directoryOnly=True)

    def on_add_logger__toggled(self, cb):
        self.logfile.set_sensitive(cb.get_active())
        self.select_logfile.set_sensitive(cb.get_active())

        if cb.get_active():
            self._scheduleCheck(self._runPathCheck,
                                dirname(self.model.logfile),
                                'logfile')
        else:
            self._clearMessage('logfile')
            self._verify()

    def on_logfile__changed(self, entry):
        self._scheduleCheck(self._runPathCheck,
                            dirname(entry.get_text()),
                            'logfile')

    def on_path__changed(self, entry):
        self._scheduleCheck(self._runPathCheck,
                            entry.get_text(),
                            'path')
