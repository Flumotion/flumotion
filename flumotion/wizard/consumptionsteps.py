# -*- Mode: Python -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# Flumotion - a streaming media server
# Copyright (C) 2004,2005,2006,2007 Fluendo, S.L. (www.fluendo.com).
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

__version__ = "$Rev$"

import gettext

from flumotion.configure import configure
from flumotion.common.python import any
from flumotion.wizard.basesteps import WizardStep, WorkerWizardStep
from flumotion.wizard.enums import RotateSize, RotateTime

_ = gettext.gettext
X_ = _


class ConsumptionStep(WizardStep):
    name = _('Consumption')
    glade_file = 'wizard_consumption.glade'
    section = _('Consumption')
    icon = 'consumption.png'

    # WizardStep

    def setup(self):
        pass

    def activated(self):
        has_audio = self.wizard.get_step_option('Source', 'has-audio')
        has_video = self.wizard.get_step_option('Source', 'has-video')
        has_both = has_audio and has_video

        # Hide all checkbuttons if we don't have both audio and video selected
        for checkbutton in (self.http_audio_video,
                            self.http_audio,
                            self.http_video,
                            self.disk_audio_video,
                            self.disk_audio,
                            self.disk_video,
                            self.shout2_audio_video,
                            self.shout2_audio,
                            self.shout2_video):
            checkbutton.set_property('visible', has_both)

    def get_next(self, step=None):
        items = self._get_items()
        assert items

        if step:
            stepname = step.get_name()
            if stepname in items and items[-1] != stepname:
                stepname = items[items.index(stepname)+1]
            else:
                stepname = None
        else:
            stepname = items[0]

        steps = {
            _('HTTP Streamer (audio & video)'): HTTPBothStep,
            _('HTTP Streamer (audio only)'): HTTPAudioStep,
            _('HTTP Streamer (video only)'): HTTPVideoStep,
            _('Disk (audio & video)'): DiskBothStep,
            _('Disk (audio only)'): DiskAudioStep,
            _('Disk (video only)'): DiskVideoStep,
            _('Icecast streamer (audio & video)'): Shout2BothStep,
            _('Icecast streamer (audio only)'): Shout2AudioStep,
            _('Icecast streamer (video only)'): Shout2VideoStep,
        }

        if stepname in steps:
            step_class = steps[stepname]
            return step_class(self.wizard)

    # Private

    def _verify(self):
        disk = self.disk.get_active()
        disk_audio = self.disk_audio.get_active()
        disk_video = self.disk_video.get_active()
        disk_audio_video = self.disk_audio_video.get_active()
        http = self.http.get_active()
        http_audio = self.http_audio.get_active()
        http_video = self.http_video.get_active()
        http_audio_video = self.http_audio_video.get_active()
        shout2 = self.shout2.get_active()
        shout2_audio = self.shout2_audio.get_active()
        shout2_video = self.shout2_video.get_active()
        shout2_audio_video = self.shout2_audio_video.get_active()

        block_next = True
        if ((disk and any([disk_audio, disk_video, disk_audio_video])) or
            (http and any([http_audio, http_video, http_audio_video])) or
            (shout2 and any([shout2_audio, shout2_video, shout2_audio_video]))):
            block_next = False
        self.wizard.block_next(block_next)

    def _get_items(self):
        uielements = []
        if self.http.get_active():
            uielements.append(('HTTP Streamer',
                               [self.http_audio,
                                self.http_video,
                                self.http_audio_video]))
        if self.disk.get_active():
            uielements.append(('Disk',
                               [self.disk_audio,
                                self.disk_video,
                                self.disk_audio_video]))
        if self.shout2.get_active():
            uielements.append(('Icecast streamer',
                               [self.shout2_audio,
                                self.shout2_video,
                                self.shout2_audio_video]))

        has_audio = self.wizard.get_step_option('Source', 'has-audio')
        has_video = self.wizard.get_step_option('Source', 'has-video')

        items = []
        for name, (audio, video, audio_video) in uielements:
            # Audio & Video, all checkbuttons are visible and
            # changeable by the user
            if has_audio and has_video:
                enable_audio_video = audio_video.get_active()
                enable_audio = audio.get_active()
                enable_video = video.get_active()
            # Audio only, user cannot chose, the checkbuttons are not
            # visible and it is not possible for the user to change,
            # just add audio, and nothing else
            elif has_audio and not has_video:
                enable_audio_video = False
                enable_audio = True
                enable_video = False
            # Video only, like audio only but with video
            elif has_video and not has_audio:
                enable_audio_video = False
                enable_audio = False
                enable_video = True
            else:
                raise AssertionError

            # These strings here should be translated but not marked
            # for translation
            if enable_audio_video:
                items.append(X_("%s (audio & video)" % (name,)))
            if enable_audio:
                items.append(X_("%s (audio only)" % (name,)))
            if enable_video:
                items.append(X_("%s (video only)" % (name,)))

        return items

    # Callbacks

    def on_disk__toggled(self, button):
        value = self.disk.get_active()
        self.disk_audio_video.set_sensitive(value)
        self.disk_audio.set_sensitive(value)
        self.disk_video.set_sensitive(value)

        self._verify()

    def on_shout2__toggled(self, button):
        value = self.shout2.get_active()
        self.shout2_audio_video.set_sensitive(value)
        self.shout2_audio.set_sensitive(value)
        self.shout2_video.set_sensitive(value)

        self._verify()

    def on_http_audio_video__toggled(self, button):
        self._verify()

    def on_http_audio__toggled(self, button):
        self._verify()

    def on_http_video__toggled(self, button):
        self._verify()

    def on_http__toggled(self, button):
        value = self.http.get_active()
        self.http_audio_video.set_sensitive(value)
        self.http_audio.set_sensitive(value)
        self.http_video.set_sensitive(value)

        self._verify()


# XXX: If audio codec is speex, disable java applet option
class HTTPStep(WorkerWizardStep):
    glade_file = 'wizard_http.glade'
    section = _('Consumption')
    component_type = 'http-streamer'

    def __init__(self, wizard):
        WorkerWizardStep.__init__(self, wizard)
        self._missing_elements = False

    # WizardStep

    def setup(self):
        self.spinbutton_port.set_value(self.port)

    def activated(self):
        self._verify()

    def worker_changed(self):
        def got_missing(missing):
            self._missing_elements = bool(missing)
            self._verify()
        self._missing_elements = True
        d = self.wizard.require_elements(self.worker, 'multifdsink')
        d.addCallback(got_missing)

    def get_state(self):
        options = {
            'mount-point': self.entry_mount_point.get_text(),
            'burst-on-connect': self.checkbutton_burst_on_connect.get_active(),
            'port': int(self.spinbutton_port.get_value()),
            }

        if not self.checkbutton_bandwidth_limit.get_active():
            options['bandwidth-limit'] = int(
                self.spinbutton_bandwidth_limit.get_value() * 1e6)
        if not self.checkbutton_client_limit.get_active():
            options['client-limit'] = int(
                self.spinbutton_client_limit.get_value())
        return options

    def get_next(self):
        return self.wizard.get_step('Consumption').get_next(self)

    # Private

    def _verify(self):
        self.spinbutton_client_limit.set_sensitive(
            self.checkbutton_client_limit.get_active())
        self.spinbutton_bandwidth_limit.set_sensitive(
            self.checkbutton_bandwidth_limit.get_active())
        self.wizard.block_next(self._missing_elements or
                               self.entry_mount_point.get_text() == '')

    # Callbacks

    def on_entry_mount_point_changed(self, entry):
        self._verify()

    def on_checkbutton_client_limit_toggled(self, checkbutton):
        self._verify()

    def on_checkbutton_bandwidth_limit_toggled(self, checkbutton):
        self._verify()


class HTTPBothStep(HTTPStep):
    name = _('HTTP Streamer (audio & video)')
    sidebar_name = _('HTTP audio/video')
    port = configure.defaultStreamPortRange[0]


class HTTPAudioStep(HTTPStep):
    name = _('HTTP Streamer (audio only)')
    sidebar_name = _('HTTP audio')
    port = configure.defaultStreamPortRange[1]


class HTTPVideoStep(HTTPStep):
    name = _('HTTP Streamer (video only)')
    sidebar_name = _('HTTP video')
    port = configure.defaultStreamPortRange[2]


class DiskStep(WorkerWizardStep):
    glade_file = 'wizard_disk.glade'
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


class Shout2Step(WorkerWizardStep):
    glade_file = 'wizard_shout2.glade'
    section = _('Consumption')
    component_type = 'shout2'

    # WizardStep

    def before_show(self):
        self.wizard.check_elements(self.worker, 'shout2send')

    def get_next(self):
        return self.wizard.get_step('Consumption').get_next(self)


class Shout2BothStep(Shout2Step):
    name = _('Icecast streamer (audio & video)')
    sidebar_name = _('Icecast audio/video')


class Shout2AudioStep(Shout2Step):
    name = _('Icecast streamer (audio only)')
    sidebar_name = _('Icecast audio')


class Shout2VideoStep(Shout2Step):
    name = _('Icecast streamer (video only)')
    sidebar_name = _('Icecast video')


