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
import os

from twisted.internet import defer

from flumotion.common import errors
from flumotion.common.messages import N_, ngettext, gettexter, Warning
from flumotion.wizard.models import HTTPServer
from flumotion.wizard.workerstep import WorkerWizardStep


__version__ = "$Rev$"
_ = gettext.gettext
T_ = gettexter('flumotion')


class OnDemand(HTTPServer):
    """I am a model representing the configuration file for a
    an on demand HTTP server component.
    """
    component_type = 'http-server'
    def __init__(self, worker=None):
        super(OnDemand, self).__init__(worker, mount_point='/')
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
    gladeFile = 'ondemand-wizard.glade'
    name = _('Demand')
    sidebarName = _('On demand')
    section = _('Production')

    def __init__(self, wizard):
        self.model = OnDemand()
        WorkerWizardStep.__init__(self, wizard)

    # WizardStep

    def setup(self):
        self.path.data_type = str
        self.port.data_type = int
        self.mount_point.data_type = str

        self.add_proxy(self.model.properties,
                       ['path',
                        'port',
                        'mount_point'])

        self.mount_point.set_text("/")

    def workerChanged(self, worker):
        self.model.worker = worker
        self._checkElements()

    def getNext(self):
        from flumotion.wizard.configurationwizard import SummaryStep
        return SummaryStep(self.wizard)

    # Public

    def getServerConsumer(self):
        return self.model

    # Private

    def _checkElements(self):
        self.wizard.waitForTask('ondemand check')

        def importError(failure):
            failure.trap(ImportError)
            self.info('could not import twisted-web')
            message = Warning(T_(N_(
                "Worker '%s' cannot import module '%s'."),
                self.worker, 'twisted.web'))
            message.add(T_(N_("\nThis module is part of the '%s'."),
                           'Twisted Project'))
            message.add(T_(N_("\nThe project's homepage is %s"),
                           'http://www.twistedmatrix.com/'))
            message.id = 'module-twisted-web'
            self.wizard.add_msg(message)
            self.wizard.taskFinished(True)

        def finished(unused):
            self.wizard.taskFinished()

        d = self.wizard.checkImport(self.worker, 'twisted.web')
        d.addCallback(finished)
        d.addErrback(importError)

    def _verify(self):
        self._updateBlocked()

    def _updateBlocked(self):
        # FIXME: This should be updated and only called when all pending
        #        tasks are done.
        self.wizard.blockNext(self.mount_point.get_text() == '')

    # Callbacks

    def on_mount_point_changed(self, entry):
        self._verify()
        self.wizard.blockNext(entry.get_text() == "/")

