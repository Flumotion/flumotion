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

from flumotion.common.errors import NoBundleError
from flumotion.wizard.models import AudioEncoder, VideoEncoder, Muxer
from flumotion.wizard.workerstep import WorkerWizardStep

__version__ = "$Rev$"
_ = gettext.gettext
N_ = _ = gettext.gettext

# the denominator arg for all calls of this function was sniffed from
# the glade file's spinbutton adjustment

def _fraction_from_float(number, denominator):
    """
    Return a string to be used in serializing to XML.
    """
    return "%d/%d" % (number * denominator, denominator)


class ConversionStep(WorkerWizardStep):
    glade_file = 'wizard_encoding.glade'
    name = _('Encoding')
    section = _('Conversion')

    def __init__(self, wizard):
        self._audio_encoder = None
        self._video_encoder = None
        WorkerWizardStep.__init__(self, wizard)

    # Public API

    def get_audio_page(self):
        if self.wizard.hasAudio():
            return self._get_audio_page()
        return None

    def get_video_encoder(self):
        """Returns the selected video encoder or None
        @returns: encoder or None
        @rtype: L{flumotion.wizard.models.VideoEncoder}
        """
        return self._video_encoder

    def get_audio_encoder(self):
        """Returns the selected audio encoder or None
        @returns: encoder or None
        @rtype: L{flumotion.wizard.models.AudioEncoder}
        """
        return self._audio_encoder

    def get_muxer_type(self):
        """Returns the component-type, such as "ogg-muxer"
        of the currently selected muxer.
        @returns: the muxer
        @rtype: string
        """
        entry = self.muxer.get_selected()
        return entry.component_type

    def get_muxer_format(self):
        """Returns the format of the muxer, such as "ogg".
        @returns: the muxer format
        @rtype: string
        """
        entry = self.muxer.get_selected()
        return entry.getProvidedMediaTypes()[0]

    def get_audio_format(self):
        """Returns the format of the audio encoder, such as "vorbis"
        @returns: the audio format
        @rtype: string
        """
        if self._audio_encoder:
            entry = self.audio.get_selected()
            return entry.getProvidedMediaTypes()[0]

    def get_video_format(self):
        """Returns the format of the video encoder, such as "theora"
        @returns: the video format
        @rtype: string
        """
        if self._video_encoder:
            entry = self.video.get_selected()
            return entry.getProvidedMediaTypes()[0]

    # WizardStep

    def activated(self):
        data = [('muxer', self.muxer)]

        production = self.wizard.get_step('Source')
        audio_producer = production.get_audio_producer()
        if audio_producer:
            data.append(('audio-encoder', self.audio))
        else:
            self.audio.hide()
            self.label_audio.hide()

        video_producer = production.get_video_producer()
        if video_producer:
            data.append(('video-encoder', self.video))
        else:
            self.video.hide()
            self.label_video.hide()

        # If there is data in the combo already, do not populate it,
        # Because it means we're pressing "back" in the wizard and the
        # combo is already populated.
        if not len(self.video) or not len(self.audio):
            self._populate_combos(data)

    def get_next(self):
        if self.wizard.hasVideo():
            return self._get_video_page()
        elif self.wizard.hasAudio():
            return self._get_audio_page()
        else:
            return None

    # Private

    def _populate_combos(self, combos, provides=None):
        for ctype, combo in combos:
            d = self.wizard.getWizardEntries(
                wizard_types=[ctype],
                provides=provides)
            d.addCallback(self._add_entries, ctype, combo)
            combo.prefill([('...', None)])
            combo.set_sensitive(False)
        self.wizard.block_next(True)
        d.addCallback(lambda x: self.wizard.block_next(False))

    def _add_entries(self, entries, ctype, combo):
        data = []
        for entry in entries:
            data.append((N_(entry.description), entry))
        combo.prefill(data)
        combo.set_sensitive(True)

    def _create_dummy_model(self, entry):
        if entry.type == 'audio-encoder':
            encoder = AudioEncoder()
        elif entry.type == 'video-encoder':
            encoder = VideoEncoder()
        else:
            raise AssertionError

        encoder.component_type = entry.component_type
        encoder.worker = self.worker

        if entry.type == 'audio-encoder':
            self._audio_encoder = encoder
        else:
            self._video_encoder = encoder

    def _load_plugin(self, entry):
        def got_factory(factory):
            return factory(self.wizard)

        def no_bundle(failure):
            failure.trap(NoBundleError)

        d = self.wizard.get_wizard_entry(entry.component_type)
        d.addCallback(got_factory)
        d.addErrback(no_bundle)

        return d

    def _load_step(self, combo):
        entry = combo.get_selected()
        def plugin_loaded(plugin, entry):
            if plugin is None:
                self._create_dummy_model(entry)
                return None
            # FIXME: verify that factory implements IEncoderPlugin
            step = plugin.getConversionStep()
            if isinstance(step, WorkerWizardStep):
                step.worker = self.worker
                step.worker_changed(self.worker)
            return step

        d = self._load_plugin(entry)
        d.addCallback(plugin_loaded, entry)

        return d

    def _get_audio_page(self):
        def step_loaded(step):
            if step is not None:
                self._audio_encoder = step.model
            self.wizard.block_next(False)
            return step
        self.wizard.block_next(True)
        d = self._load_step(self.audio)
        d.addCallback(step_loaded)
        return d

    def _get_video_page(self):
        def step_loaded(step):
            if step is not None:
                self._video_encoder = step.model
            self.wizard.block_next(False)
            return step
        self.wizard.block_next(True)
        d = self._load_step(self.video)
        d.addCallback(step_loaded)
        return d

    def _muxer_changed(self):
        muxer_entry = self.muxer.get_selected()
        # '...' used while waiting for the query to be done
        if muxer_entry is None:
            return
        self._populate_combos([('audio-encoder', self.audio),
                               ('video-encoder', self.video)],
                              provides=muxer_entry.getAcceptedMediaTypes())

    # Callbacks

    def on_muxer__changed(self, combo):
        self._muxer_changed()
