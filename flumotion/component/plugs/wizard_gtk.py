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

"""Wizard plugin for the cortado http plug
"""

from zope.interface import implements

import gtk
import os

from flumotion.admin.assistant.interfaces import IHTTPServerPlugin
from flumotion.admin.assistant.models import Plug
from flumotion.common import messages
from flumotion.common.i18n import N_, gettexter
from flumotion.ui.fileselector import FileSelectorDialog
from flumotion.ui.plugarea import WizardPlugLine

__version__ = "$Rev$"
T_ = gettexter()


class RequestLoggerPlug(Plug):
    """I am a model representing the configuration file for a
    Request Logger plug.
    """
    plugType = "requestlogger-file"

    def __init__(self, component):
        Plug.__init__(self)
        self.component = component
        self.properties.logfile = '/tmp/access.log'

    def setActive(self, active):
        if active:
            self.component.addPlug(self)
        else:
            self.component.delPlug(self)


class RequestLoggerPlugLine(WizardPlugLine):
    gladeFile = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                             'wizard.glade')
    toplevel_name = 'requestlogger-window'

    def __init__(self, wizard, model, description):
        WizardPlugLine.__init__(self, wizard, model, description)

        self.logfile.data_type = str
        self._proxy = self.add_proxy(self.model.properties, ['logfile'])

        if self.getActive():
            self.model.setActive(True)
        else:
            self.plugActiveChanged(False)

    # WizardPlugLine

    def plugActiveChanged(self, active):
        self.logfile.set_sensitive(active)
        self.select_logfile.set_sensitive(active)
        self.model.setActive(active)

    # Callbacks

    def on_select_logfile_clicked(self, button):

        def response(fs, response):
            fs.hide()
            if response == gtk.RESPONSE_OK:
                filename = os.path.join(fs.getFilename(), 'access.log')
                self.model.properties.logfile = filename
                self._proxy.update('logfile')

        fs = FileSelectorDialog(self.wizard.window,
                                self.wizard.getAdminModel())

        fs.connect('response', response)
        fs.selector.setOnlyDirectoriesMode(True)
        fs.selector.setWorkerName(self.model.component.worker)
        directory = os.path.dirname(self.model.properties.logfile)
        fs.setDirectory(directory)
        fs.show_all()

    def on_logfile_changed(self, button):
        self._runChecks()

    def _runChecks(self):
        self.wizard.waitForTask('ondemand check')

        worker = self.model.component.worker
        directory = os.path.dirname(self.logfile.get_text())

        def importError(failure):
            failure.trap(ImportError)
            self.info('could not import twisted-web')
            message = messages.Warning(T_(N_(
                "Worker '%s' cannot import module '%s'."),
                worker, 'twisted.web'))
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
                    % (directory, worker)))
                message.id = 'log-path-check'
                self.wizard.add_msg(message)
                self.wizard.taskFinished(True)
                return False
            else:
                self.wizard.clear_msg('log-path-check')
                self.wizard.taskFinished(False)
                return True

            self.wizard.taskFinished()

        def checkPath(unused):
            d = self.wizard.runInWorker(
                worker, 'flumotion.worker.checks.check',
                'checkDirectory', directory)
            d.addCallback(checkPathFinished)
            return d

        d = self.wizard.checkImport(worker, 'twisted.web')
        d.addCallback(checkPath)
        d.addErrback(importError)
        return d


class RequestLoggerPlugWizardPlugin(object):
    implements(IHTTPServerPlugin)

    def __init__(self, wizard, component):
        self.wizard = wizard
        self.model = RequestLoggerPlug(component)

    def workerChanged(self, worker):
        pass

    def getPlugWizard(self, description):
        return RequestLoggerPlugLine(self.wizard, self.model, description)


class RequestModifierForceDownloadPlug(Plug):
    """I am a model representing the configuration file for the
    Force download plug.
    """
    plugType = "requestmodifier-forcedownload"

    def __init__(self, component):
        Plug.__init__(self)
        self.component = component
        self.properties.argument_name = 'force'
        self.properties.trigger_value = 'true'

    def setActive(self, active):
        if active:
            self.component.addPlug(self)
        else:
            self.component.delPlug(self)


class RequestModifierForceDownloadPlugLine(WizardPlugLine):

    def __init__(self, wizard, model, description):
        WizardPlugLine.__init__(self, wizard, model, description)

        if self.getActive():
            self.model.setActive(True)

    # WizardPlugLine

    def plugActiveChanged(self, active):
        self.model.setActive(active)


class RequestModifierForceDownloadPlugWizardPlugin(object):
    implements(IHTTPServerPlugin)

    def __init__(self, wizard, component):
        self.wizard = wizard
        self.model = RequestModifierForceDownloadPlug(component)

    def workerChanged(self, worker):
        pass

    def getPlugWizard(self, description):
        return RequestModifierForceDownloadPlugLine(self.wizard, self.model,
                                                    description)
