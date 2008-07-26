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

import gettext
import os

from zope.interface import implements

from flumotion.common import errors
from flumotion.common.fraction import fractionAsString
from flumotion.common.i18n import N_, gettexter
from flumotion.common.messages import Info
# FIXME: make pychecker able to suppress shadowed builtins like these
# at the defining site, not caller site
# P2.4
__pychecker__ = 'no-shadowbuiltin'
from flumotion.common.python import sorted
__pychecker__ = ''
from flumotion.wizard.basesteps import VideoProducerStep
from flumotion.wizard.interfaces import IProducerPlugin
from flumotion.wizard.models import VideoProducer

__version__ = "$Rev$"
_ = gettext.gettext
T_ = gettexter()


class WebcamProducer(VideoProducer):
    componentType = 'webcam-producer'

    def __init__(self):
        super(WebcamProducer, self).__init__()

        self.properties.device = '/dev/video0'


class WebcamStep(VideoProducerStep):
    name = 'Webcam'
    title = _('Webcam')
    icon = 'webcam.png'
    gladeFile = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                              'wizard.glade')
    componentType = 'video4linux'

    def __init__(self, wizard, model):
        VideoProducerStep.__init__(self, wizard, model)
        self._inSetup = False
        # _sizes is probed, not set from the UI
        self._sizes = None

    # WizardStep

    def setup(self):
        self._inSetup = True
        self.device.data_type = str
        self.framerate.data_type = object

        self.device.prefill(['/dev/video0',
                             '/dev/video1',
                             '/dev/video2',
                             '/dev/video3'])

        self.add_proxy(self.model.properties,['device'])

        self._inSetup = False

    def workerChanged(self, worker):
        self.model.worker = worker
        self._clear()
        self._runChecks()

    # Private

    def _clear(self):
        # Clear is called:
        # - when changing a worker
        # - after probing a device, if none found
        self.size.set_sensitive(False)
        self.framerate.set_sensitive(False)
        self.label_name.set_label("")

    def _runChecks(self):
        if self._inSetup:
            return None

        self.wizard.waitForTask('webcam checks')

        device = self.device.get_selected()
        msg = Info(T_(
                N_("Probing the webcam. This can take a while...")),
            mid='webcam-check')
        self.wizard.add_msg(msg)
        d = self.runInWorker('flumotion.worker.checks.video', 'checkWebcam',
                           device, mid='webcam-check')

        def errRemoteRunFailure(failure):
            failure.trap(errors.RemoteRunFailure)
            self.debug('a RemoteRunFailure happened')
            self._clear()
            self.wizard.taskFinished(blockNext=True)

        def errRemoteRunError(failure):
            failure.trap(errors.RemoteRunError)
            self.debug('a RemoteRunError happened')
            self._clear()
            self.wizard.taskFinished(blockNext=True)

        def deviceFound(result):
            if not result:
                self.debug('no device %s' % device)
                self._clear()
                self.wizard.taskFinished(blockNext=True)
                return None

            deviceName, factoryName, sizes = result
            self.model.properties.element_factory = factoryName
            self._populateSizes(sizes)
            self.wizard.clear_msg('webcam-check')
            self.label_name.set_label(deviceName)
            self.wizard.taskFinished()
            self.size.set_sensitive(True)
            self.framerate.set_sensitive(True)

        d.addCallback(deviceFound)
        d.addErrback(errRemoteRunFailure)
        d.addErrback(errRemoteRunError)

    def _populateSizes(self, sizes):
        # Set sizes before populating the values, since
        # it trigger size_changed which depends on this
        # to be set
        self._sizes = sizes

        values = []
        for w, h in sorted(sizes.keys(), reverse=True):
            values.append(['%d x %d' % (w, h), (w, h)])
        self.size.prefill(values)

    def _populateFramerates(self, size):
        values = []
        for d in self._sizes[size]:
            num, denom = d['framerate']
            values.append(('%.2f fps' % (1.0*num/denom), d))
        self.framerate.prefill(values)

    def _updateSize(self):
        size = self.size.get_selected()
        if size:
            self._populateFramerates(size)
            width, height = size
        else:
            self.warning('something bad happened: no height/width selected?')
            width, height = 320, 240

        self.model.properties.width = width
        self.model.properties.height = height

    def _updateFramerate(self):
        if self._inSetup:
            return None

        framerate = self.framerate.get_selected()
        if framerate:
            num, denom = framerate['framerate']
            mime = framerate['mime']
            format = framerate.get('format', None)
        else:
            self.warning('something bad happened: no framerate selected?')
            num, denom = 15, 2
            mime = 'video/x-raw-yuv'
            format = None

        self.model.properties.mime = mime
        self.model.properties.framerate = fractionAsString((num, denom))
        if format:
            self.model.properties.format = format

    # Callbacks

    def on_device_changed(self, combo):
        self._runChecks()

    def on_size_changed(self, combo):
        self._updateSize()

    def on_framerate_changed(self, combo):
        self._updateFramerate()


class WebcamWizardPlugin(object):
    implements(IProducerPlugin)
    def __init__(self, wizard):
        self.wizard = wizard
        self.model = WebcamProducer()

    def getProductionStep(self, type):
        return WebcamStep(self.wizard, self.model)

