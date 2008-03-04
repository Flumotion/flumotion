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
from flumotion.common.messages import N_, gettexter, Info
from flumotion.wizard.basesteps import VideoSourceStep
from flumotion.wizard.interfaces import IProducerPlugin
from flumotion.wizard.models import VideoProducer

__version__ = "$Rev$"
_ = gettext.gettext
T_ = gettexter('flumotion')


class TVCardProducer(VideoProducer):
    component_type = 'tvcard-producer'

    def __init__(self):
        super(TVCardProducer, self).__init__()

        self.properties.device = '/dev/video0'


class TVCardStep(VideoSourceStep):
    name = _('TV Card')
    glade_file = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                              'bttv-wizard.glade')
    component_type = 'bttv'
    icon = 'tv.png'

    def __init__(self, wizard, model):
        VideoSourceStep.__init__(self, wizard, model)
        self._in_setup = False

    # WizardStep

    def setup(self):
        self._in_setup = True

        self.device.data_type = str
        self.width.data_type = int
        self.height.data_type = int
        self.framerate.data_type = float

        self.device.prefill(['/dev/video0',
                             '/dev/video1',
                             '/dev/video2',
                             '/dev/video3'])

        self.add_proxy(self.model.properties,
                       ['device', 'height', 'width',
                        'framerate'])

        self._in_setup = False

    def worker_changed(self, worker):
        self.model.worker = worker
        self._clear_combos()
        self._run_checks()

    # Private

    def _clear_combos(self):
        self.tvnorm.clear()
        self.tvnorm.set_sensitive(False)
        self.source.clear()
        self.source.set_sensitive(False)

    def _run_checks(self):
        if self._in_setup:
            return None

        self.wizard.block_next(True)

        device = self.device.get_selected()
        assert device
        msg = Info(T_(
            N_("Probing TV-card, this can take a while...")),
                            id='tvcard-check')
        self.wizard.add_msg(msg)
        d = self.run_in_worker('flumotion.worker.checks.video', 'checkTVCard',
                               device, id='tvcard-check')

        def errRemoteRunFailure(failure):
            failure.trap(errors.RemoteRunFailure)
            self.debug('a RemoteRunFailure happened')
            self._clear_combos()

        def errRemoteRunError(failure):
            failure.trap(errors.RemoteRunError)
            self.debug('a RemoteRunError happened')
            self._clear_combos()

        def deviceFound(result):
            if not result:
                self._clear_combos()
                return None

            deviceName, channels, norms = result
            self.wizard.clear_msg('tvcard-check')
            self.wizard.block_next(False)
            self.tvnorm.prefill(norms)
            self.tvnorm.set_sensitive(True)
            self.source.prefill(channels)
            self.source.set_sensitive(True)

        d.addCallback(deviceFound)
        d.addErrback(errRemoteRunFailure)
        d.addErrback(errRemoteRunError)

    # Callbacks

    def on_device__changed(self, combo):
        self._run_checks()


class BTTVWizardPlugin(object):
    implements(IProducerPlugin)
    def __init__(self, wizard):
        self.wizard = wizard
        self.model = TVCardProducer()

    def getProductionStep(self, type):
        return TVCardStep(self.wizard, self.model)

