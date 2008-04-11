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

import gtk

from flumotion.common.errors import NoBundleError
from flumotion.ui.wizard import WizardStep

# Register components
from flumotion.common import componentui

__version__ = "$Rev$"
# pychecker doesn't like the auto-generated widget attrs
# or the extra args we name in callbacks
__pychecker__ = 'no-classattr no-argsused'
N_ = _ = gettext.gettext


class ProductionStep(WizardStep):

    glade_file = 'wizard_production.glade'
    name = _('Production')
    section = _('Production')
    icon = 'source.png'

    def __init__(self, wizard):
        self._audio_producer = None
        self._video_producer = None
        self._loadedSteps = None
        WizardStep.__init__(self, wizard)

    # Public API

    def hasAudio(self):
        """Returns if audio will be used in the stream
        created by the wizard.

        @returns: if audio will be used
        @rtype:   bool
        """
        return self.has_audio.get_active()

    def hasVideo(self):
        """Returns if video will be used in the stream
        created by the wizard.

        @returns: if video will be used
        @rtype:   bool
        """
        return self.has_video.get_active()

    def get_audio_producer(self):
        """Returns the selected audio producer or None
        @returns: producer or None
        @rtype: L{flumotion.wizard.models.AudioProducer}
        """
        if self.has_audio.get_active():
            return self._audio_producer

    def get_video_producer(self):
        """Returns the selected video producer or None
        @returns: producer or None
        @rtype: L{flumotion.wizard.models.VideoProducer}
        """
        if self.has_video.get_active():
            return self._video_producer

    def get_video_step(self):
        """Return the video step to be shown, given the currently
        selected values in this step
        @returns: video step
        @rtype: a deferred returning a L{basesteps.VideoProducerStep} instance
        """
        def step_loaded(step):
            if step is not None:
                self._video_producer = step.model
            self.wizard.taskFinished()
            return step
        self.wizard.waitForTask('video producer step')
        d = self._load_step(self.video, 'video')
        d.addCallback(step_loaded)
        return d

    def get_audio_step(self):
        """Return the audio step to be shown, given the currently
        selected values in this step
        @returns: audio step
        @rtype: a deferred returning a L{basesteps.AudioProducerStep} instance
        """
        def step_loaded(step):
            if step is not None:
                self._audio_producer = step.model
            self.wizard.taskFinished()
            return step
        self.wizard.waitForTask('audio producer step')
        d = self._load_step(self.audio, 'audio')
        d.addCallback(step_loaded)
        return d

    # WizardStep

    def setup(self):
        self.audio.data_type = object
        self.video.data_type = object
        # We want to save the audio/video attributes as
        # component_type in the respective models
        self.audio.model_attribute = 'component_type'
        self.video.model_attribute = 'component_type'

        tips = gtk.Tooltips()
        tips.set_tip(self.has_video, _('If you want to stream video'))
        tips.set_tip(self.has_audio, _('If you want to stream audio'))

        self._populate_combos()

    def get_next(self):
        if self.has_video.get_active():
            return self.get_video_step()
        elif self.has_audio.get_active():
            return self.get_audio_step()
        else:
            raise AssertionError

    # Private API

    def _populate_combos(self):
        def got_entries(entries, combo, default_type):
            data = []
            default = None
            for entry in entries:
                if entry.component_type == default_type:
                    default = entry
                    continue
                data.append((N_(entry.description), entry.component_type))
            assert default
            data.insert(0, (N_(default.description), default.component_type))
            combo.prefill(data)
            combo.set_sensitive(True)

        for ctype, combo, default_type in [
            ('video-producer', self.video, 'videotest-producer'),
            ('audio-producer', self.audio, 'audiotest-producer')]:
            d = self.wizard.getWizardEntries(
                wizard_types=[ctype])
            d.addCallback(got_entries, combo, default_type)
            combo.prefill([('...', None)])
            combo.set_sensitive(False)

        self.wizard.waitForTask('querying producers')
        def done(_):
            self.wizard.taskFinished()
            self._loadedSteps = True
        d.addCallback(done)

    def _load_plugin(self, component_type, type):
        def got_factory(factory):
            return factory(self.wizard)

        def noBundle(failure):
            failure.trap(NoBundleError)

        d = self.wizard.get_wizard_entry(component_type)
        d.addCallback(got_factory)
        d.addErrback(noBundle)

        return d

    def _load_step(self, combo, type):
        def plugin_loaded(plugin, entry):
            # FIXME: verify that factory implements IProductionPlugin
            step = plugin.getProductionStep(type)
            return step

        entry = combo.get_selected()
        d = self._load_plugin(entry, type)
        d.addCallback(plugin_loaded, entry)

        return d

    def _verify(self):
        if not self._loadedSteps:
            return

        has_audio = self.has_audio.get_active()
        has_video = self.has_video.get_active()
        can_continue = False
        if has_audio or has_video:
            can_continue = True

        self.wizard.block_next(not can_continue)

    # Callbacks

    def on_has_video__toggled(self, button):
        self.video.set_sensitive(button.get_active())
        self._verify()

    def on_has_audio__toggled(self, button):
        self.audio.set_sensitive(button.get_active())
        self._verify()

    def on_video__changed(self, button):
        self._verify()

    def on_audio__changed(self, button):
        self._verify()
