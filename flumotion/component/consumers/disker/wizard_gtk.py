# -*- Mode: Python -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# Flumotion - a streaming media server
# Copyright (C) 2004,2005,2006,2007,2008 Fluendo, S.L. (www.fluendo.com).
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
import gtk

from flumotion.admin.assistant.interfaces import IConsumerPlugin
from flumotion.admin.assistant.models import Consumer
from flumotion.admin.gtk.basesteps import ConsumerStep
from flumotion.ui.fileselector import FileSelectorDialog

__version__ = "$Rev$"
_ = gettext.gettext

(SIZE_KB,
 SIZE_MB,
 SIZE_GB,
 SIZE_TB) = tuple([1 << (10L*i) for i in range(1, 5)])

TIME_MINUTE = 60
TIME_HOUR = 60*60
TIME_DAY = 60*60*24
TIME_WEEK = 60*60*24*7


class Disker(Consumer):
    """I am a model representing the configuration file for a
    Disk consumer.

    @ivar has_time: if rotation should be done based on time
    @ivar has_size: if rotation should be done based on size
    @ivar time_unit: the selected size unit,
      size will be multiplied by this value when saved
    @ivar size_unit: the selected time unit,
      time will be multiplied by this value when saved
    """
    componentType = 'disk-consumer'

    def __init__(self):
        super(Disker, self).__init__()
        self.has_size = False
        self.has_time = False
        self.size = 10
        self.size_unit = SIZE_KB
        self.time = 12
        self.time_unit = TIME_HOUR

        self.properties.directory = "/tmp"
        self.properties.start_recording = False

    def _getRotationType(self):
        if self.has_time:
            return 'time'
        elif self.has_size:
            return 'size'
        else:
            return 'none'

    # Component

    def getProperties(self):
        properties = super(Disker, self).getProperties()
        properties.rotate_type = self._getRotationType()
        if 'size' == properties.rotate_type:
            properties.size = self.size_unit * self.size
        elif 'time' == properties.rotate_type:
            properties.time = self.time_unit * self.time

        return properties


class DiskStep(ConsumerStep):
    gladeFile = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                              'wizard.glade')
    icon = 'kcmdevices.png'

    def __init__(self, wizard):
        self.model = Disker()
        ConsumerStep.__init__(self, wizard)

    # ConsumerStep

    def getConsumerModel(self):
        return self.model

    # WizardStep

    def setup(self):
        self.directory.data_type = str
        self.has_size.data_type = bool
        self.has_time.data_type = bool
        self.size.data_type = int
        self.size_unit.data_type = long
        self.start_recording.data_type = bool
        self.time.data_type = int
        self.time_unit.data_type = int

        self.size_unit.prefill([
            (_('kB'), SIZE_KB),
            (_('MB'), SIZE_MB),
            (_('GB'), SIZE_GB),
            (_('TB'), SIZE_TB),
             ])
        self.time_unit.prefill([
            (_('minute(s)'), TIME_MINUTE),
            (_('hour(s)'), TIME_HOUR),
            (_('day(s)'), TIME_DAY),
            (_('week(s)'), TIME_WEEK)])
        self.time_unit.select(TIME_HOUR)

        self.add_proxy(self.model,
                       ['has_size',
                        'has_time',
                        'rotate',
                        'size_unit',
                        'time_unit',
                        'time',
                        'size'])

        self._proxy = self.add_proxy(self.model.properties,
                       ['directory',
                        'start_recording'])

    def workerChanged(self, worker):
        self.model.worker = worker
        self.wizard.requireElements(self.worker, 'multifdsink')

    # Private

    def _updateRadio(self):
        rotate = self.rotate.get_active()
        self.has_size.set_sensitive(rotate)
        self.has_time.set_sensitive(rotate)

        hasSize = rotate and self.has_size.get_active()
        self.size.set_sensitive(hasSize)
        self.size_unit.set_sensitive(hasSize)
        self.model.has_size = hasSize

        hasTime = rotate and self.has_time.get_active()
        self.time.set_sensitive(hasTime)
        self.time_unit.set_sensitive(hasTime)
        self.model.has_time = hasTime

    def _select(self):

        def response(fs, response):
            fs.hide()
            if response == gtk.RESPONSE_OK:
                self.model.properties.directory = fs.getFilename()
                self._proxy.update('directory')

        def deleteEvent(fs, event):
            pass
        fs = FileSelectorDialog(self.wizard.window,
                                self.wizard.getAdminModel())
        fs.connect('response', response)
        fs.connect('delete-event', deleteEvent)
        fs.selector.setWorkerName(self.model.worker)
        fs.setDirectory(self.model.properties.directory)
        fs.show_all()

    # Callbacks

    def on_has_time__toggled(self, radio):
        self._updateRadio()

    def on_has_size__toggled(self, radio):
        self._updateRadio()

    def on_rotate__toggled(self, check):
        self._updateRadio()

    def on_select__clicked(self, check):
        self._select()


class DiskBothStep(DiskStep):
    name = 'Disk (audio & video)'
    title = _('Disk (Audio and Video)')
    sidebarName = _('Disk Audio/Video')

    # ConsumerStep

    def getConsumerType(self):
        return 'audio-video'


class DiskAudioStep(DiskStep):
    name = 'Disk (audio only)'
    title = _('Disk (Audio Only)')
    sidebarName = _('Disk Audio')

    # ConsumerStep

    def getConsumerType(self):
        return 'audio'


class DiskVideoStep(DiskStep):
    name = 'Disk (video only)'
    title = _('Disk (Video Only)')
    sidebarName = _('Disk Video')

    # ConsumerStep

    def getConsumerType(self):
        return 'video'


class DiskConsumerWizardPlugin(object):
    implements(IConsumerPlugin)

    def __init__(self, wizard):
        self.wizard = wizard

    def getConsumptionStep(self, type):
        if type == 'video':
            return DiskVideoStep(self.wizard)
        elif type == 'audio':
            return DiskAudioStep(self.wizard)
        elif type == 'audio-video':
            return DiskBothStep(self.wizard)
