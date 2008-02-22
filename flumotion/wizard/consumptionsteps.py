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

from flumotion.common.python import any
from flumotion.component.consumers.httpstreamer.httpstreamer_wizard import \
     HTTPBothStep, HTTPAudioStep, HTTPVideoStep
from flumotion.component.consumers.disker.disker_wizard import \
     DiskBothStep, DiskAudioStep, DiskVideoStep
from flumotion.component.consumers.shout2.shout2_wizard import \
     Shout2BothStep, Shout2AudioStep, Shout2VideoStep
from flumotion.ui.wizard import WizardStep

__version__ = "$Rev$"
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


