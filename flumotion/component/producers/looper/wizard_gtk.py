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

import gobject
import gtk

from zope.interface import implements

from flumotion.common import messages
from flumotion.common.i18n import N_, gettexter
from flumotion.admin.gtk.basesteps import AudioProducerStep, VideoProducerStep
from flumotion.admin.assistant.interfaces import IProducerPlugin
from flumotion.admin.assistant.models import AudioProducer, VideoProducer, \
     AudioEncoder, VideoEncoder, VideoConverter
from flumotion.ui.fileselector import FileSelectorDialog

__pychecker__ = 'no-returnvalues'
__version__ = "$Rev: 6583 $"
_ = gettext.gettext
T_ = gettexter('flumotion')


class LoopProducer(AudioProducer, VideoProducer):
    componentType = 'loop-producer'

    def __init__(self):
        super(LoopProducer, self).__init__()
        self.properties.location = None
        self.properties.framerate = 5.0
        self.properties.width = 320
        self.properties.height = 240

    def getFeederName(self, component):
        if isinstance(component, AudioEncoder):
            return 'audio'
        elif isinstance(component, (VideoEncoder, VideoConverter)):
            return 'video'
        else:
            raise AssertionError


class _LoopCommon:
    icon = 'looper.png'
    componentType = 'filesrc'
    gladeFile = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                              'wizard.glade')

    _mimetype = 'application/ogg'
    _audio_required = True
    _video_required = True

    def __init__(self):
        self._idleId = -1
        self._blockNext = {}

    def workerChanged(self, worker):
        self.model.worker = worker
        self._runChecks()

    def setup(self):
        return

    def _runChecks(self):
        self._runFileCheck(self.model.properties.location, 'location')

    def _runFileCheck(self, location, id):
        self._blockNext[id] = True
        if location is None or location == '':
            self._verify()
            return
        self.wizard.waitForTask('looper location check')

        def checkFileFinished(result):
            validFile, properties = result
            if not validFile:
                message = messages.Warning(T_(N_(
                    "'%s' is not a valid file, "
                    "or is not readable on worker '%s'.")
                    % (location, self.worker)))
                message.id = 'looper-'+id+'-check'
                self.wizard.add_msg(message)
            else:
                self._updateFileProperties(properties)
                self.wizard.clear_msg('looper-'+id+'-check')
                self._blockNext[id] = False
            self.wizard.taskFinished()
            self._verify()
        d = self.runInWorker('flumotion.worker.checks.check',
                             'checkMediaFile',
                             location,
                             self._mimetype,
                             self._audio_required,
                             self._video_required)
        d.addCallback(checkFileFinished)

    def _abortScheduledCheck(self):
        if self._idleId != -1:
            gobject.source_remove(self._idleId)
            self._idleId = -1

    def _scheduleCheck(self, checkToRun, data, id):
        self._abortScheduledCheck()
        self._idleId = gobject.timeout_add(300, checkToRun, data, id)

    def _clearMessage(self, id):
        self.wizard.clear_msg('looper-'+id+'-check')
        self._blockNext[id] = False

    def _verify(self):
        self.wizard.blockNext(reduce(lambda x, y: x or y,
                                     self._blockNext.values(),
                                     False))

    def _showFileSelector(self, response_cb, location):

        def deleteEvent(fs, event):
            pass

        fs = FileSelectorDialog(self.wizard.window,
                                self.wizard.getAdminModel())

        fs.connect('response', response_cb)
        fs.connect('delete-event', deleteEvent)
        fs.selector.setWorkerName(self.model.worker)
        fs.selector.setOnlyDirectoriesMode(False)
        if location:
            directory = os.path.dirname(location)
        else:
            directory = '/'
        fs.selector.setDirectory(directory)
        fs.show_all()

    def _updateFileProperties(self, props):
        pass

    def on_browse_clicked(self, button):

        def response(fs, response):
            fs.hide()
            if response == gtk.RESPONSE_OK:
                self.model.properties.location = fs.getFilename()
                self._proxy.update('location')
                self._clearMessage('location')
                self._runFileCheck(self.model.properties.location, 'location')

        self._showFileSelector(response,
                               self.model.properties.location)

    def on_location_changed(self, entry):
        self._scheduleCheck(self._runFileCheck,
                            entry.get_text(),
                            'location')


class LoopVideoStep(_LoopCommon, VideoProducerStep):
    title = _('Loop Video')
    name = 'Loop Video'

    def __init__(self, wizard, model):
        VideoProducerStep.__init__(self, wizard, model)
        _LoopCommon.__init__(self)

    def setup(self):
        self._audio_required = False
        self.location.data_type = str
        self.width.data_type = int
        self.height.data_type = int
        self.framerate.data_type = float
        self._proxy = self.add_proxy(self.model.properties,
                                     ['width', 'height',
                                      'framerate', 'location'])

    def _updateFileProperties(self, props):
        self.model.properties.width = props.get('width',
                                                self.model.properties.width)
        self.model.properties.height = props.get('height',
                                                 self.model.properties.height)
        self.model.properties.framerate = props.get('framerate',
                                            self.model.properties.framerate)
        self._proxy.update('width')
        self._proxy.update('height')
        self._proxy.update('framerate')


class LoopAudioStep(_LoopCommon, AudioProducerStep):
    name = 'Loop audio'
    title = _('Loop audio')

    def __init__(self, wizard, model):
        AudioProducerStep.__init__(self, wizard, model)
        _LoopCommon.__init__(self)

    def setup(self):
        self._video_required = False
        self.location.data_type = str
        self._proxy = self.add_proxy(self.model.properties, ['location'])
        self.video.hide()
        videoProducer = self.wizard.getStep('Production').getVideoProducer()
        if not videoProducer or videoProducer.componentType != 'loop-producer':
            self.location_box.set_sensitive(True)
        else:
            self.location.set_text(videoProducer.properties.location)
            self.location_box.set_sensitive(False)

    def getNext(self):
        return None


class LoopWizardPlugin(object):
    implements(IProducerPlugin)

    def __init__(self, wizard):
        self.wizard = wizard

    def getProductionStep(self, type):
        if type == 'audio':
            return LoopAudioStep(self.wizard, LoopProducer())
        elif type == 'video':
            return LoopVideoStep(self.wizard, LoopProducer())
