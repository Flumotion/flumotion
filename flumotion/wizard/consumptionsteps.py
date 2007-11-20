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

from flumotion.configure import configure
from flumotion.wizard.basesteps import WorkerWizardStep
from flumotion.wizard.enums import RotateSize, RotateTime


class ConsumptionStep(WorkerWizardStep):
    name = 'Consumption'
    glade_file = 'wizard_consumption.glade'
    section = 'Consumption'
    icon = 'consumption.png'
    has_worker = False

    # WizardStep

    def setup(self):
        pass

    def activated(self):
        has_audio = self.wizard.get_step_option('Source', 'has-audio')
        has_video = self.wizard.get_step_option('Source', 'has-video')
        has_both = has_audio and has_video

        # Hide all checkbuttons if we don't have both audio and video selected
        for checkbutton in (self.checkbutton_http_audio_video,
                            self.checkbutton_http_audio,
                            self.checkbutton_http_video,
                            self.checkbutton_disk_audio_video,
                            self.checkbutton_disk_audio,
                            self.checkbutton_disk_video,
                            self.checkbutton_shout2_audio_video,
                            self.checkbutton_shout2_audio,
                            self.checkbutton_shout2_video):
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
            'HTTP Streamer (audio & video)': HTTPBothStep,
            'HTTP Streamer (audio only)': HTTPAudioStep,
            'HTTP Streamer (video only)': HTTPVideoStep,
            'Disk (audio & video)': DiskBothStep,
            'Disk (audio only)': DiskAudioStep,
            'Disk (video only)': DiskVideoStep,
            'Icecast streamer (audio & video)': Shout2BothStep,
            'Icecast streamer (audio only)': Shout2AudioStep,
            'Icecast streamer (video only)': Shout2VideoStep,
        }

        if stepname in steps:
            step_class = steps[stepname]
            return step_class(self.wizard)

    # Private

    def _verify(self):
        disk = self.checkbutton_disk.get_active()
        disk_audio = self.checkbutton_disk_audio.get_active()
        disk_video = self.checkbutton_disk_video.get_active()
        disk_audio_video = self.checkbutton_disk_audio_video.get_active()
        http = self.checkbutton_http.get_active()
        http_audio = self.checkbutton_http_audio.get_active()
        http_video = self.checkbutton_http_video.get_active()
        http_audio_video = self.checkbutton_http_audio_video.get_active()
        shout2 = self.checkbutton_shout2.get_active()
        shout2_audio = self.checkbutton_shout2_audio.get_active()
        shout2_video = self.checkbutton_shout2_video.get_active()
        shout2_audio_video = self.checkbutton_shout2_audio_video.get_active()

        block_next = True
        if ((disk and any([disk_audio, disk_video, disk_audio_video])) or
            (http and any([http_audio, http_video, http_audio_video])) or
            (shout2 and any([shout2_audio, shout2_video, shout2_audio_video]))):
            block_next = False
        self.wizard.block_next(block_next)

    def _get_items(self):
        uielements = []
        if self.checkbutton_http.get_active():
            uielements.append(('HTTP Streamer',
                               [self.checkbutton_http_audio,
                                self.checkbutton_http_video,
                                self.checkbutton_http_audio_video]))
        if self.checkbutton_disk.get_active():
            uielements.append(('Disk',
                               [self.checkbutton_disk_audio,
                                self.checkbutton_disk_video,
                                self.checkbutton_disk_audio_video]))
        if self.checkbutton_shout2.get_active():
            uielements.append(('Icecast streamer',
                               [self.checkbutton_shout2_audio,
                                self.checkbutton_shout2_video,
                                self.checkbutton_shout2_audio_video]))

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

            if enable_audio_video:
                items.append("%s (audio & video)" % (name,))
            if enable_audio:
                items.append("%s (audio only)" % (name,))
            if enable_video:
                items.append("%s (video only)" % (name,))

        return items

    # Callbacks

    def on_checkbutton_disk_toggled(self, button):
        value = self.checkbutton_disk.get_active()
        self.checkbutton_disk_audio_video.set_sensitive(value)
        self.checkbutton_disk_audio.set_sensitive(value)
        self.checkbutton_disk_video.set_sensitive(value)

        self._verify()

    def on_checkbutton_shout2_toggled(self, button):
        value = self.checkbutton_shout2.get_active()
        self.checkbutton_shout2_audio_video.set_sensitive(value)
        self.checkbutton_shout2_audio.set_sensitive(value)
        self.checkbutton_shout2_video.set_sensitive(value)

        self._verify()

    def on_secondary_checkbutton_toggled(self, button):
        self._verify()

    def on_checkbutton_http_toggled(self, button):
        value = self.checkbutton_http.get_active()
        self.checkbutton_http_audio_video.set_sensitive(value)
        self.checkbutton_http_audio.set_sensitive(value)
        self.checkbutton_http_video.set_sensitive(value)

        self._verify()


# XXX: If audio codec is speex, disable java applet option
class HTTPStep(WorkerWizardStep):
    glade_file = 'wizard_http.glade'
    section = 'Consumption'
    component_type = 'http-streamer'

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
        options = WorkerWizardStep.get_state(self)

        options['bandwidth-limit'] = int(options['bandwidth-limit'] * 1e6)
        options['client-limit'] = int(options['client-limit'])

        if not self.checkbutton_bandwidth_limit.get_active():
            del options['bandwidth-limit']
        if not self.checkbutton_client_limit.get_active():
            del options['client-limit']

        options['port'] = int(options['port'])

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
    name = 'HTTP Streamer (audio & video)'
    sidebar_name = 'HTTP audio/video'
    port = configure.defaultStreamPortRange[0]


class HTTPAudioStep(HTTPStep):
    name = 'HTTP Streamer (audio only)'
    sidebar_name = 'HTTP audio'
    port = configure.defaultStreamPortRange[1]


class HTTPVideoStep(HTTPStep):
    name = 'HTTP Streamer (video only)'
    sidebar_name = 'HTTP video'
    port = configure.defaultStreamPortRange[2]


class DiskStep(WorkerWizardStep):
    glade_file = 'wizard_disk.glade'
    section = 'Consumption'
    icon = 'kcmdevices.png'

    # WizardStep

    def setup(self):
        self.combobox_time_list.set_enum(RotateTime)
        self.combobox_size_list.set_enum(RotateSize)
        self.radiobutton_has_time.set_active(True)
        self.spinbutton_time.set_value(12)
        self.combobox_time_list.set_active(RotateTime.Hours)
        self.checkbutton_record_at_startup.set_active(True)

    def get_state(self):
        options = {}
        if not self.checkbutton_rotate.get_active():
            options['rotate-type'] = 'none'
        else:
            if self.radiobutton_has_time:
                options['rotate-type'] = 'time'
                unit = self.combobox_time_list.get_enum().unit
                options['time'] = long(self.spinbutton_time.get_value() * unit)
            elif self.radiobutton_has_size:
                options['rotate-type'] = 'size'
                unit = self.combobox_size_list.get_enum().unit
                options['size'] = long(self.spinbutton_size.get_value() * unit)

        options['directory'] = self.entry_location.get_text()
        options['start-recording'] = \
            self.checkbutton_record_at_startup.get_active()
        return options

    def get_next(self):
        return self.wizard.get_step('Consumption').get_next(self)

    # Private

    def _update_radio(self):
        if self.radiobutton_has_size:
            self.spinbutton_size.set_sensitive(True)
            self.combobox_size_list.set_sensitive(True)
            self.spinbutton_time.set_sensitive(False)
            self.combobox_time_list.set_sensitive(False)
        elif self.radiobutton_has_time:
            self.spinbutton_time.set_sensitive(True)
            self.combobox_time_list.set_sensitive(True)
            self.spinbutton_size.set_sensitive(False)
            self.combobox_size_list.set_sensitive(False)

    # Callbacks

    def on_radiobutton_rotate_toggled(self, button):
        # This is bound to both radiobutton_has_size and radiobutton_has_time
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
    name = 'Disk (audio & video)'
    sidebar_name = 'Disk audio/video'


class DiskAudioStep(DiskStep):
    name = 'Disk (audio only)'
    sidebar_name = 'Disk audio'


class DiskVideoStep(DiskStep):
    name = 'Disk (video only)'
    sidebar_name = 'Disk video'


class Shout2Step(WorkerWizardStep):
    glade_file = 'wizard_shout2.glade'
    section = 'Consumption'
    component_type = 'shout2'

    # WizardStep

    def before_show(self):
        self.wizard.check_elements(self.worker, 'shout2send')

    def get_next(self):
        return self.wizard.get_step('Consumption').get_next(self)

    def get_state(self):
        options = WorkerWizardStep.get_state(self)

        options['port'] = int(options['port'])

        for option in options.keys():
            if options[option] == '':
                del options[option]

        return options


class Shout2BothStep(Shout2Step):
    name = 'Icecast streamer (audio & video)'
    sidebar_name = 'Icecast audio/video'


class Shout2AudioStep(Shout2Step):
    name = 'Icecast streamer (audio only)'
    sidebar_name = 'Icecast audio'


class Shout2VideoStep(Shout2Step):
    name = 'Icecast streamer (video only)'
    sidebar_name = 'Icecast video'


