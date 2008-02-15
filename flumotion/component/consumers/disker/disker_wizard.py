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

from flumotion.common.enum import EnumClass
from flumotion.wizard.workerstep import WorkerWizardStep

__version__ = "$Rev$"
_ = gettext.gettext

RotateTime = EnumClass(
    'RotateTime',
    ['Minutes', 'Hours', 'Days', 'Weeks'],
    [_('minute(s)'),
     _('hour(s)'),
     _('day(s)'),
     _('week(s)')],
    unit=(60,
          60*60,
          60*60*24,
          60*60*25*7))
RotateSize = EnumClass(
    'RotateSize',
    ['kB', 'MB', 'GB', 'TB'],
    [_('kB'), _('MB'), _('GB'), _('TB')],
    unit=(1 << 10L,
          1 << 20L,
          1 << 30L,
          1 << 40L))


class DiskStep(WorkerWizardStep):
    glade_file = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                              'disker-wizard.glade')
    section = _('Consumption')
    icon = 'kcmdevices.png'

    # WizardStep

    def setup(self):
        self.combobox_time_list.set_enum(RotateTime)
        self.combobox_size_list.set_enum(RotateSize)
        self.radiobutton_has_time.set_active(True)
        self.spinbutton_time.set_value(12)
        self.combobox_time_list.select(RotateTime.Hours)
        self.checkbutton_record_at_startup.set_active(True)

    def get_state(self):
        options = {}
        if not self.checkbutton_rotate.get_active():
            options['rotate-type'] = 'none'
        else:
            if self.radiobutton_has_time.get_active():
                options['rotate-type'] = 'time'
                time_value = self.combobox_time_list.get_selected()
                options['time'] = long(
                    self.spinbutton_time.get_value() * time_value.unit)
            elif self.radiobutton_has_size.get_active():
                options['rotate-type'] = 'size'
                size_value = self.combobox_size_list.get_selected()
                options['size'] = long(
                    self.spinbutton_size.get_value() * size_value.unit)

        options['directory'] = self.entry_location.get_text()
        options['start-recording'] = \
            self.checkbutton_record_at_startup.get_active()
        return options

    def get_next(self):
        return self.wizard.get_step('Consumption').get_next(self)

    # Private

    def _update_radio(self):
        if self.radiobutton_has_size.get_active():
            self.spinbutton_size.set_sensitive(True)
            self.combobox_size_list.set_sensitive(True)
            self.spinbutton_time.set_sensitive(False)
            self.combobox_time_list.set_sensitive(False)
        elif self.radiobutton_has_time.get_active():
            self.spinbutton_time.set_sensitive(True)
            self.combobox_time_list.set_sensitive(True)
            self.spinbutton_size.set_sensitive(False)
            self.combobox_size_list.set_sensitive(False)

    # Callbacks

    def on_radiobutton_has_time_toggled(self, radio):
        self._update_radio()

    def on_radiobutton_has_size_toggled(self, radio):
        self._update_radio()

    def on_checkbutton_rotate_toggled(self, button):
        if self.checkbutton_rotate.get_active():
            self.radiobutton_has_size.set_sensitive(True)
            self.radiobutton_has_time.set_sensitive(True)
            self._update_radio()
        else:
            self.radiobutton_has_size.set_sensitive(False)
            self.spinbutton_size.set_sensitive(False)
            self.combobox_size_list.set_sensitive(False)
            self.radiobutton_has_time.set_sensitive(False)
            self.spinbutton_time.set_sensitive(False)
            self.combobox_time_list.set_sensitive(False)


class DiskBothStep(DiskStep):
    name = _('Disk (audio & video)')
    sidebar_name = _('Disk audio/video')


class DiskAudioStep(DiskStep):
    name = _('Disk (audio only)')
    sidebar_name = _('Disk audio')


class DiskVideoStep(DiskStep):
    name = _('Disk (video only)')
    sidebar_name = _('Disk video')



