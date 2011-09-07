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

import gettext
import os

from twisted.python import util
from zope.interface import implements

from flumotion.admin.assistant.interfaces import IProducerPlugin
from flumotion.admin.assistant.models import VideoProducer
from flumotion.common import errors
from flumotion.common.fraction import fractionAsString
from flumotion.common.i18n import N_, gettexter
from flumotion.common.messages import Info
from flumotion.admin.gtk.basesteps import VideoProducerStep

__version__ = "$Rev$"
_ = gettext.gettext
T_ = gettexter()


class WebcamProducer(VideoProducer):
    componentType = 'webcam-producer'

    def __init__(self):
        super(WebcamProducer, self).__init__()

    def getProperties(self):
        p = super(WebcamProducer, self).getProperties()

        if 'mime' not in p:
            p.mime = self.framerate['mime']
        if 'format' not in p:
            p.format = self.framerate.get('format', None)
        if 'framerate' not in p:
            p.framerate = fractionAsString(self.framerate['framerate'])

        self.properties = p

        return p


class WebcamStep(VideoProducerStep):
    name = 'Webcam'
    title = _('Webcam')
    icon = 'webcam.png'
    gladeFile = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                              'wizard.glade')
    componentType = 'video4linux'
    docSection = 'help-configuration-assistant-producer-video-webcam'
    docAnchor = ''

    def __init__(self, wizard, model):
        VideoProducerStep.__init__(self, wizard, model)
        # _sizes is probed, not set from the UI
        self._sizes = None

    # WizardStep

    def setup(self):
        self.device.data_type = str
        self.framerate.data_type = object
        self.size.data_type = object

        self.add_proxy(self.model.properties, ['device'])
        self.add_proxy(self.model, ['size', 'framerate'])

    def workerChanged(self, worker):
        self.model.worker = worker
        self._clear()
        self._populateDevices()

    # Private

    def _clear(self):
        # Clear is called:
        # - when changing a worker
        # - after probing a device, if none found
        self.size.set_sensitive(False)
        self.framerate.set_sensitive(False)

    def _populateDevices(self):
        msg = Info(T_(N_('Checking for Webcam devices...')),
            mid='webcam-check')
        self.wizard.add_msg(msg)
        d = self.runInWorker('flumotion.worker.checks.device',
                             'fetchDevices', 'webcam-check',
                             ['v4l2src', 'v4lsrc'], 'device')

        def webcamCheckDone(devices):
            self.wizard.clear_msg('webcam-check')
            self.device.prefill(devices)

        def trapRemoteFailure(failure):
            failure.trap(errors.RemoteRunFailure)

        def trapRemoteError(failure):
            failure.trap(errors.RemoteRunError)

        d.addCallback(webcamCheckDone)
        d.addErrback(trapRemoteError)
        d.addErrback(trapRemoteFailure)

        return d

    def _runChecks(self):
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
                self.debug('Could not detect the device\'s configuration.')
                self._clear()
                self.wizard.taskFinished(blockNext=True)
                return None

            factoryName, sizes = result
            self.model.properties.element_factory = factoryName
            self._populateSizes(sizes)
            self.wizard.clear_msg('webcam-check')
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
        if len(values) > 1:
            self.size.set_active(1)

    def _populateFramerates(self, size):
        values = util.OrderedDict()
        for d in self._sizes[size]:
            num, denom = d['framerate']
            values['%.2f fps' % (1.0*num/denom)] = d
        self.framerate.prefill(values.items())

    # Callbacks

    def on_device_changed(self, combo):
        self._runChecks()

    def on_size_changed(self, combo):
        size = self.size.get_selected()
        if size:
            self._populateFramerates(size)
            self.model.properties.width, self.model.properties.height = size


class WebcamWizardPlugin(object):
    implements(IProducerPlugin)

    def __init__(self, wizard):
        self.wizard = wizard
        self.model = WebcamProducer()

    def getProductionStep(self, type):
        return WebcamStep(self.wizard, self.model)
