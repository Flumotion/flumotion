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

from flumotion.wizard.models import Consumer
from flumotion.wizard.basesteps import ConsumerStep

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
        self.has_time = False
        self.has_size = False
        self.time_unit = TIME_HOUR
        self.size_unit = SIZE_KB
        self.time = 12
        self.size = 10
        self.properties.directory = ""

    # Component

    def _getRotationType(self):
        if self.has_time:
            return 'time'
        elif self.has_size:
            return 'size'
        else:
            return 'none'

    def getProperties(self):
        properties = super(Disker, self).getProperties()
        properties.rotate_type = self._getRotationType()
        if 'size' in properties:
            properties.size *= self.size_unit
        if 'time' in properties:
            properties.time *= self.time_unit

        return properties


class DiskStep(ConsumerStep):
    gladeFile = 'disker-wizard.glade'
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
        self.start_recording.data_type = bool

        self.has_time.data_type = bool
        self.time.data_type = int
        self.time_unit.data_type = int
        self.time_unit.prefill([
            (_('minute(s)'), TIME_MINUTE),
            (_('hour(s)'), TIME_HOUR),
            (_('day(s)'), TIME_DAY),
            (_('week(s)'), TIME_WEEK)])
        self.time_unit.select(TIME_HOUR)

        self.has_size.data_type = bool
        self.size.data_type = int
        self.size_unit.data_type = long
        self.size_unit.prefill([
            (_('kB'), SIZE_KB),
            (_('MB'), SIZE_MB),
            (_('GB'), SIZE_GB),
            (_('TB'), SIZE_TB),
             ])

        self.add_proxy(self.model,
                       ['rotate',
                        'has_size',
                        'has_time',
                        'size_unit',
                        'time_unit'])

        self.add_proxy(self.model.properties,
                       ['size',
                        'time',
                        'directory',
                        'start_recording'])

    def workerChanged(self, worker):
        self.model.worker = worker
        self.wizard.requireElements(self.worker, 'multifdsink')

    # Private

    def _update_radio(self):
        rotate = self.rotate.get_active()
        self.has_size.set_sensitive(rotate)
        self.has_time.set_sensitive(rotate)

        has_size = rotate and self.has_size.get_active()
        self.size.set_sensitive(has_size)
        self.size_unit.set_sensitive(has_size)

        has_time = rotate and self.has_time.get_active()
        self.time.set_sensitive(has_time)
        self.time_unit.set_sensitive(has_time)

    # Callbacks

    def on_has_time_toggled(self, radio):
        self._update_radio()

    def on_has_size_toggled(self, radio):
        self._update_radio()

    def on_rotate_toggled(self, check):
        self._update_radio()


class DiskBothStep(DiskStep):
    name = 'Disk (audio & video)'
    title = _('Disk (audio and video)')
    sidebarName = _('Disk audio/video')

    # ConsumerStep

    def getConsumerType(self):
        return 'audio-video'


class DiskAudioStep(DiskStep):
    name = 'Disk (audio only)'
    title = _('Disk (audio only)')
    sidebarName = _('Disk audio')

    # ConsumerStep

    def getConsumerType(self):
        return 'audio'


class DiskVideoStep(DiskStep):
    name = 'Disk (video only)'
    title = _('Disk (video only)')
    sidebarName = _('Disk video')

    # ConsumerStep

    def getConsumerType(self):
        return 'video'
