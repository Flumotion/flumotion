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

from flumotion.wizard.basesteps import WorkerWizardStep, VideoEncoderStep, \
    AudioEncoderStep
from flumotion.wizard.enums import EncodingAudio, EncodingFormat, EncodingVideo
from flumotion.wizard.models import AudioEncoder, VideoEncoder, Muxer

_ = gettext.gettext


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
        WorkerWizardStep.__init__(self, wizard)
        self._muxer = Muxer()
        self._audio_encoder = AudioEncoder()
        self._video_encoder = VideoEncoder()
        self.wizard.flow.addComponent(self._muxer)

    # Public API

    def get_audio_page(self):
        if self.wizard.get_step_option(_('Source'), 'has-audio'):
            return self._get_audio_page()
        return None

    # WizardStep

    def before_show(self):
        self.format.set_enum(EncodingFormat)
        self.audio.set_enum(EncodingAudio)
        self.video.set_enum(EncodingVideo)

        flow = self.wizard.flow
        production = self.wizard.get_step(_('Source'))

        audio_producer = production.get_audio_producer()
        if audio_producer and self._audio_encoder not in flow:
            flow.addComponent(self._audio_encoder)

        video_producer = production.get_video_producer()
        if video_producer and self._video_encoder not in flow:
            flow.addComponent(self._video_encoder)

    def activated(self):
        self._verify()

    def get_next(self):
        if self.wizard.get_step_option(_('Source'), 'has-video'):
            return self._get_video_page()
        elif self.wizard.get_step_option(_('Source'), 'has-audio'):
            return self._get_audio_page()
        else:
            return None

    # Private

    def _get_audio_page(self):
        audio = self.audio.get_selected()
        if audio == EncodingAudio.Vorbis:
            step_class = VorbisStep
        elif audio == EncodingAudio.Speex:
            step_class = SpeexStep
        elif audio == EncodingAudio.Mulaw:
            return None
        return step_class(self.wizard, self._audio_encoder)

    def _get_video_page(self):
        video = self.video.get_selected()
        if video == EncodingVideo.Theora:
            step_class = TheoraStep
        elif video == EncodingVideo.Smoke:
            step_class = SmokeStep
        elif video == EncodingVideo.JPEG:
            step_class = JPEGStep
        else:
            raise AssertionError(video)

        return step_class(self.wizard, self._video_encoder)

    def _verify(self):
        # XXX: isn't there a better way of doing this, like blocking
        #      the signal

        format = self.format.get_selected()
        if format == EncodingFormat.Ogg:
            self.debug('running Ogg checks')
            def hasOgg(unused):
                # XXX: Smoke can't be put in ogg. Poke Wim to fix
                self.video.set_enum(
                    EncodingVideo, [EncodingVideo.Theora])
                self.audio.set_enum(
                    EncodingAudio, [EncodingAudio.Speex,
                                    EncodingAudio.Vorbis])

            def hasOggmux(unused):
                d = self.run_in_worker('flumotion.component.muxers.checks',
                                       'checkOgg')
                d.addCallback(hasOgg)
            d = self.wizard.require_elements(self.worker, 'oggmux')
            d.addCallback(hasOggmux)

        elif format == EncodingFormat.Multipart:
            self.video.set_enum(
                EncodingVideo, [EncodingVideo.Smoke,
                                EncodingVideo.JPEG])
            self.audio.set_enum(
                EncodingAudio, [EncodingAudio.Mulaw])

        for option, widgets in [
            ('has-audio', [self.audio, self.label_audio]),
            ('has-video', [self.video, self.label_video])]:
            value = self.wizard.get_step_option(_('Source'), option)
            for widget in widgets:
                widget.set_property('visible', value)

    # Callbacks

    def on_format__changed(self, combo):
        format = combo.get_selected()
        if format is not None:
            self._muxer.name = format.component_type
        self._verify()

    def on_audio__changed(self, combo):
        audio = combo.get_selected()
        if audio is not None:
            self._audio_encoder.name = audio.component_type

    def on_video__changed(self, combo):
        video = combo.get_selected()
        if video is not None:
            self._video_encoder.name = video.component_type


class TheoraStep(VideoEncoderStep):
    name = _('Theora encoder')
    sidebar_name = _('Theora')
    glade_file = 'wizard_theora.glade'
    component_type = 'theora'
    icon = 'xiphfish.png'

    # WizardStep

    def worker_changed(self):
        self.debug('running Theora checks')
        def hasTheora(unused):
            self.run_in_worker('flumotion.worker.checks.encoder', 'checkTheora')

        d = self.wizard.require_elements(self.worker, 'theoraenc')
        d.addCallback(hasTheora)

    def get_state(self):
        options = {}
        if self.radiobutton_bitrate:
            options['bitrate'] = int(
                self.spinbutton_bitrate.get_value()) * 1000
        elif self.radiobutton_quality:
            options['quality'] = int(self.spinbutton_quality.get_value())

        options['keyframe-maxdistance'] = int(
            self.spinbutton_keyframe_maxdistance.get_value())
        options['noise-sensitivity'] = \
            max(int(self.spinbutton_noise_sensitivity.get_value()
                    * (32768 / 100.)),
                1)
        options['sharpness'] = int(self.spinbutton_sharpness.get_value())

        return options

    def get_next(self):
        return self.wizard.get_step(_('Encoding')).get_audio_page()

    # Callbacks

    def on_radiobutton_toggled(self, button):
        # This is bound to both radiobutton_bitrate and radiobutton_quality
        self.spinbutton_bitrate.set_sensitive(
            self.radiobutton_bitrate.get_active())
        self.spinbutton_quality.set_sensitive(
            self.radiobutton_quality.get_active())


class SmokeStep(VideoEncoderStep):
    name = _('Smoke encoder')
    sidebar_name = _('Smoke')
    glade_file = 'wizard_smoke.glade'
    section = _('Conversion')
    component_type = 'smoke'

    # WizardStep

    def worker_changed(self):
        self.wizard.require_elements(self.worker, 'smokeenc')

    def get_next(self):
        return self.wizard.get_step(_('Encoding')).get_audio_page()


class JPEGStep(VideoEncoderStep):
    name = 'JPEG encoder'
    sidebar_name = 'JPEG'
    glade_file = 'wizard_jpeg.glade'
    section = _('Conversion')
    component_type = 'jpeg'

    # WizardStep

    def worker_changed(self):
        self.wizard.require_elements(self.worker, 'jpegenc')

    def get_state(self):
        options = {}
        options['quality'] = int(self.spinbutton_quality.get_value())
        options['framerate'] = _fraction_from_float(
            int(self.spinbutton_framerate.get_value()), 2)
        return options

    def get_next(self):
        return self.wizard.get_step(_('Encoding')).get_audio_page()


# Worker?
class VorbisStep(AudioEncoderStep):
    glade_file = 'wizard_vorbis.glade'
    name = _('Vorbis encoder')
    sidebar_name = _('Vorbis')
    component_type = 'vorbis'
    icon = 'xiphfish.png'

    # WizardStep

    def setup(self):
        # By choosing quality as a default, we avoid samplerate/bitrate
        # mismatch
        self.radiobutton_bitrate.set_active(False)

    def worker_changed(self):
        self.debug('running Vorbis checks')
        def hasVorbis(unused):
            self.run_in_worker('flumotion.worker.checks.encoder', 'checkVorbis')

        d = self.wizard.require_elements(self.worker, 'vorbisenc')
        d.addCallback(hasVorbis)

    def get_state(self):
        options = {}
        if self.radiobutton_bitrate:
            options['bitrate'] = int(self.spinbutton_bitrate.get_value()) * 1000
        elif self.radiobutton_quality:
            options['quality'] = self.spinbutton_quality.get_value()
        return options

    # Callbacks

    def on_radiobutton_toggled(self, button):
        # This is bound to both radiobutton_bitrate and radiobutton_quality
        self.spinbutton_bitrate.set_sensitive(
            self.radiobutton_bitrate.get_active())
        self.spinbutton_quality.set_sensitive(
            self.radiobutton_quality.get_active())


class SpeexStep(AudioEncoderStep):
    name = _('Speex encoder')
    sidebar_name = _('Speex')
    component_type = 'speex'
    icon = 'xiphfish.png'

    # WizardStep

    def setup(self):
        # Should be 2150 instead of 3 -> 3000
        self.spinbutton_bitrate.set_range(3, 30)
        self.spinbutton_bitrate.set_value(11)

    def worker_changed(self):
        self.wizard.require_elements(self.worker, 'speexenc')

    def get_state(self):
        options = {}
        options['bitrate'] = int(self.spinbutton_bitrate.get_value()) * 1000
        return options
