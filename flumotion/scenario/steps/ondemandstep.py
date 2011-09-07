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

from flumotion.admin.assistant.models import HTTPServer, Plug, Porter
from flumotion.admin.assistant.interfaces import IHTTPServerPlugin
from flumotion.admin.gtk.workerstep import WorkerWizardStep
from flumotion.common import messages
from flumotion.common.i18n import N_, gettexter
from flumotion.ui.fileselector import FileSelectorDialog
from flumotion.configure import configure

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
        self.properties.port = configure.defaultHTTPStreamPort
        self.setPorter(
            Porter(worker=None, port=self.properties.port))

        self.properties.path = '/tmp'

        self.properties.allow_browsing = True
        self.add_logger = False
        self.logfile = '/tmp/access.log'

    # Component

    def getProperties(self):
        properties = super(OnDemand, self).getProperties()

        if self.add_logger:
            self.addPlug(LoggerPlug(self.logfile))

        porter = self.getPorter()

        properties.porter_socket_path = porter.getSocketPath()
        properties.porter_username = porter.getUsername()
        properties.porter_password = porter.getPassword()
        properties.type = 'slave'
        # FIXME: Try to maintain the port empty when we are slave. Needed
        # for now as the adminwindow tab shows the URL based on this property.
        properties.port = (self.properties.port or
                           self.getPorter().getProperties().port)
        return properties

    def setPorter(self, porter):
        self._porter = porter

    def getPorter(self):
        self._porter.worker = self.worker
        if self.properties.port:
            self._porter.properties.port = self.properties.port
        return self._porter


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

        self._proxy = self.add_proxy(self.model.properties,
                       ['path',
                        'port',
                        'mount_point',
                       ])

    def workerChanged(self, worker):
        self.model.worker = worker
        d = self._runChecks()
        d.addCallback(self._populatePlugins, worker)

    def getNext(self):
        return None

    # Public

    def getServerConsumer(self):
        return self.model

    # Private

    def _addPlugLine(self, line):
        self.plugarea.addLine(line)

    def _populatePlugins(self, canPopulate, worker):
        if not canPopulate:
            return

        self.plugarea.clean()

        def gotEntries(entries):
            for entry in entries:

                def response(factory, entry):
                    if IHTTPServerPlugin.implementedBy(factory):
                        plugin = factory(self.wizard, self.model)
                        self._addPlugLine(plugin.getPlugWizard(
                            N_(entry.description)))

                d = self.wizard.getWizardPlugEntry(entry.componentType)
                d.addCallback(response, entry)

        d = self.wizard.getWizardEntries(wizardTypes=['httpserver-plug', ])
        d.addCallbacks(gotEntries)
        return d

    def _runChecks(self):
        self.wizard.waitForTask('ondemand check')
        self._blockNext['path'] = True

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
            return False

        def checkPathFinished(pathExists):
            if not pathExists:
                message = messages.Warning(T_(N_(
                    "Directory '%s' does not exist, "
                    "or is not readable on worker '%s'.")
                    % (self.model.properties.path, self.worker)))
                message.id = 'ondemand-path-check'
                self.wizard.add_msg(message)
                self.wizard.taskFinished(True)
                return False
            else:
                self.wizard.clear_msg('ondemand-path-check')
                self._blockNext['path'] = False
                self.wizard.taskFinished(False)
                return True

            self.wizard.taskFinished()

        def checkPath(unused):
            d = self.runInWorker('flumotion.worker.checks.check',
                                 'checkDirectory', self.model.properties.path)
            d.addCallback(checkPathFinished)
            return d

        d = self.wizard.checkImport(self.worker, 'twisted.web')
        d.addCallback(checkPath)
        d.addErrback(importError)
        return d

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
        self.wizard.blockNext(not entry.get_text())

    def on_select_directory__clicked(self, button):

        def response(fs, response):
            fs.hide()
            if response == gtk.RESPONSE_OK:
                self.model.properties.path = fs.getFilename()
                self._proxy.update('path')
                self.wizard.clear_msg('ondemand-path-check')

        directory = self.model.properties.path

        self._showFileSelector(response,
                               path=directory,
                               directoryOnly=True)

    def on_path__changed(self, entry):
        self._runChecks()
