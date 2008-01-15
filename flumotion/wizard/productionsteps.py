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

import gettext

import gtk
from twisted.internet.defer import Deferred

from flumotion.common import messages
from flumotion.common.errors import NoBundleError
from flumotion.wizard.models import AudioProducer, VideoProducer
from flumotion.wizard.basesteps import WorkerWizardStep

# Register components
from flumotion.common import componentui

__version__ = "$Rev$"
# pychecker doesn't like the auto-generated widget attrs
# or the extra args we name in callbacks
__pychecker__ = 'no-classattr no-argsused'
T_ = messages.gettexter('flumotion')
N_ = _ = gettext.gettext


class ProductionStep(WorkerWizardStep):

    glade_file = 'wizard_source.glade'
    name = _('Source')
    section = _('Production')
    icon = 'source.png'

    def __init__(self, wizard):
        WorkerWizardStep.__init__(self, wizard)
        self._audio_producer = None
        self._video_producer = None
        # FIXME: Why isn't setup() called for WorkerWizardSteps?
        self._setup()

    # Public API

    def get_audio_producer(self):
        """Returns the selected audio producer or None
        @returns: producer or None
        @rtype: L{flumotion.wizard.models.AudioProducer}
        """
        return self._audio_producer

    def get_video_producer(self):
        """Returns the selected video producer or None
        @returns: producer or None
        @rtype: L{flumotion.wizard.models.VideoProducer}
        """
        return self._video_producer

    def get_video_step(self):
        """Return the video step to be shown, given the currently
        selected values in this step
        @returns: video step
        @rtype: a deferred returning a L{VideoSourceStep} instance
        """
        return self._load_step(self.video, self._video_producer, 'video')

    def get_audio_step(self):
        """Return the audio step to be shown, given the currently
        selected values in this step
        @returns: audio step
        @rtype: a deferred returning an L{AudioSourceStep} instance
        """
        return self._load_step(self.audio, self._audio_producer, 'audio')

    # WizardStep

    def activated(self):
        self._verify()

    def get_next(self):
        if self.has_video.get_active():
            return self.get_video_step()
        elif self.has_audio.get_active():
            return self.get_audio_step()
        else:
            raise AssertionError

    # Private API

    def _setup(self):
        self._audio_producer = AudioProducer()
        self.wizard.flow.addComponent(self._audio_producer)
        self._video_producer = VideoProducer()
        self.wizard.flow.addComponent(self._video_producer)

        self.audio.data_type = object
        self.video.data_type = object
        # We want to save the audio/video attributes as
        # component_type in the respective models
        self.audio.model_attribute = 'component_type'
        self.video.model_attribute = 'component_type'

        tips = gtk.Tooltips()
        tips.set_tip(self.has_video,
                     _('If you want to stream video'))
        tips.set_tip(self.has_audio,
                     _('If you want to stream audio'))

        self.add_proxy(self._audio_producer, ['audio'])
        self.add_proxy(self._video_producer, ['video'])

        def got_entries(entries, combo):
            data = []
            for entry in entries:
                data.append((N_(entry.description), entry.component_type))
            combo.prefill(data)

        for ctype, combo in [('video-producer', self.video),
                             ('audio-producer', self.audio)]:
            d = self.wizard._admin.getWizardEntries(
                wizard_types=[ctype])
            d.addCallback(got_entries, combo)

    def _load_plugin(self, component_type, type):
        def got_factory(factory):
            return factory(self.wizard)

        def noBundle(failure):
            failure.trap(NoBundleError)

        d = self.wizard.get_wizard_entry(component_type)
        d.addCallback(got_factory)
        d.addErrback(noBundle)

        return d

    def _load_step(self, combo, producer, type):
        def plugin_loaded(plugin):
            step_class = plugin.get_production_step(type)
            step = step_class(self.wizard, producer)
            if isinstance(step, WorkerWizardStep):
                step.worker = self.worker
                step.worker_changed()
            return step

        d = self._load_plugin(combo.get_selected(), type)
        d.addCallback(plugin_loaded)

        return d

    def _verify(self):
        # FIXME: We should wait for the first worker to connect before
        #        opening the wizard or so
        if not hasattr(self.wizard, 'combobox_worker'):
            return

        has_audio = self.has_audio.get_active()
        has_video = self.has_video.get_active()
        can_continue = False
        can_select_worker = False
        if has_audio or has_video:
            can_continue = True

            video_source = self.video.get_active()
            audio_source = self.audio.get_active()
            if (has_audio and audio_source == 'firewire-producer' and
                not (has_video and video_source == 'firewire-producer')):
                can_select_worker = True
        self.wizard.block_next(not can_continue)

        self.wizard.combobox_worker.set_sensitive(can_select_worker)

    # Callbacks

    def on_has_video__toggled(self, button):
        self.video.set_sensitive(button.get_active())
        if button.get_active():
            self.wizard.flow.addComponent(self._video_producer)
        else:
            self.wizard.flow.removeComponent(self._video_producer)
        self._verify()

    def on_has_audio__toggled(self, button):
        self.audio.set_sensitive(button.get_active())
        if button.get_active():
            self.wizard.flow.addComponent(self._audio_producer)
        else:
            self.wizard.flow.removeComponent(self._audio_producer)
        self._verify()

    def on_video__changed(self, button):
        self._verify()

    def on_audio__changed(self, button):
        self._verify()
