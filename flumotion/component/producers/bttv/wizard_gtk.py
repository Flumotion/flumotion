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
#
# note:
# v4l talks about "signal" (PAL/...) and "channel" (TV/Composite/...)
# and frequency
# gst talks about "norm" and "channel"
# and frequency
# apps (and flumotion) talk about "TV Norm" and "source",
# and channel (corresponding to frequency)
#

import gettext
import os

from zope.interface import implements

from flumotion.common import errors
from flumotion.common.i18n import N_, gettexter
from flumotion.common.messages import Info
from flumotion.wizard.basesteps import VideoProducerStep
from flumotion.wizard.interfaces import IProducerPlugin
from flumotion.wizard.models import VideoProducer

__version__ = "$Rev$"
_ = gettext.gettext
T_ = gettexter()


class TVCardProducer(VideoProducer):
    componentType = 'tvcard-producer'

    def __init__(self):
        super(TVCardProducer, self).__init__()

        self.properties.device = '/dev/video0'
        self.properties.signal = ''
        self.properties.channel = ''


class TVCardStep(VideoProducerStep):
    name = 'TVCard'
    title = _('TV Card')
    icon = 'tv.png'
    gladeFile = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                              'wizard.glade')
    componentType = 'bttv'

    def __init__(self, wizard, model):
        VideoProducerStep.__init__(self, wizard, model)
        self._inSetup = False

    # WizardStep

    def setup(self):
        self._inSetup = True

        self.device.data_type = str
        self.width.data_type = int
        self.height.data_type = int
        self.framerate.data_type = float
        self.channel.data_type = str
        self.signal.data_type = str

        self.channel.prefill([''])
        self.signal.prefill([''])
        self.device.prefill(['/dev/video0',
                             '/dev/video1',
                             '/dev/video2',
                             '/dev/video3'])

        self.add_proxy(self.model.properties,
                       ['device', 'height', 'width',
                        'framerate', 'signal', 'channel'])

        self._inSetup = False

    def workerChanged(self, worker):
        self.model.worker = worker
        self._clearCombos()
        self._runChecks()

    # Private

    def _clearCombos(self):
        self.channel.clear()
        self.channel.set_sensitive(False)
        self.signal.clear()
        self.signal.set_sensitive(False)

    def _runChecks(self):
        if self._inSetup:
            return None

        self.wizard.waitForTask('bttv checks')

        device = self.device.get_selected()
        assert device
        msg = Info(T_(
            N_("Probing the TV card. This can take a while...")),
                            mid='tvcard-check')
        self.wizard.add_msg(msg)
        d = self.runInWorker('flumotion.worker.checks.video', 'checkTVCard',
                               device, mid='tvcard-check')

        def errRemoteRunFailure(failure):
            failure.trap(errors.RemoteRunFailure)
            self.debug('a RemoteRunFailure happened')
            self._clearCombos()
            self.wizard.taskFinished(True)

        def errRemoteRunError(failure):
            failure.trap(errors.RemoteRunError)
            self.debug('a RemoteRunError happened')
            self._clearCombos()
            self.wizard.taskFinished(True)

        def deviceFound(result):
            if not result:
                self._clearCombos()
                self.wizard.taskFinished(True)
                return None

            deviceName, channels, signals = result
            self.wizard.clear_msg('tvcard-check')
            self.channel.prefill(channels)
            self.channel.set_sensitive(True)
            self.signal.prefill(signals)
            self.signal.set_sensitive(True)
            self.wizard.taskFinished()

        d.addCallback(deviceFound)
        d.addErrback(errRemoteRunFailure)
        d.addErrback(errRemoteRunError)

    # Callbacks

    def on_device__changed(self, combo):
        self._runChecks()


class BTTVWizardPlugin(object):
    implements(IProducerPlugin)
    def __init__(self, wizard):
        self.wizard = wizard
        self.model = TVCardProducer()

    def getProductionStep(self, type):
        return TVCardStep(self.wizard, self.model)

