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

from flumotion.twisted.defer import defer_generator_method
from flumotion.wizard.basesteps import WorkerWizardStep, VideoEncoderStep, \
    AudioEncoderStep
from flumotion.wizard.enums import EncodingAudio, EncodingFormat, EncodingVideo
from flumotion.wizard.models import AudioEncoder, VideoEncoder, Muxer

# the denominator arg for all calls of this function was sniffed from
# the glade file's spinbutton adjustment

def _fraction_from_float(number, denominator):
    """
    Return a string to be used in serializing to XML.
    """
    return "%d/%d" % (number * denominator, denominator)


class ConversionStep(WorkerWizardStep):
    glade_file = 'wizard_encoding.glade'
    name = 'Encoding'
    section = 'Conversion'

    def __init__(self, wizard):
        WorkerWizardStep.__init__(self, wizard)
        self._muxer = Muxer()
        self._audio_encoder = AudioEncoder()
        self._video_encoder = VideoEncoder()
        self.wizard.flow.addComponent(self._muxer)

    # Public API

    def get_audio_page(self):
        if self.wizard.get_step_option('Source', 'has-audio'):
            codec = self.combobox_audio.get_enum()
            if codec == EncodingAudio.Vorbis:
                step_class = VorbisStep
            elif codec == EncodingAudio.Speex:
                step_class = SpeexStep
            elif codec == EncodingAudio.Mulaw:
                return None
            return step_class(self.wizard, self._audio_encoder)
        return None

    # WizardStep

    def before_show(self):
        self.combobox_format.set_enum(EncodingFormat)
        self.combobox_audio.set_enum(EncodingAudio)
        self.combobox_video.set_enum(EncodingVideo)

        flow = self.wizard.flow
        production = self.wizard.get_step('Source')

        audio_producer = production.get_audio_producer()
        if audio_producer and self._audio_encoder not in flow:
            flow.addComponent(self._audio_encoder)

        video_producer = production.get_video_producer()
        if video_producer and self._video_encoder not in flow:
            flow.addComponent(self._video_encoder)

    def activated(self):
        self._verify()

    def get_next(self):
        if self.wizard.get_step_option('Source', 'has-video'):
            codec = self.combobox_video.get_enum()
            if codec == EncodingVideo.Theora:
                step_class = TheoraStep
            elif codec == EncodingVideo.Smoke:
                step_class = SmokeStep
            elif codec == EncodingVideo.JPEG:
                step_class = JPEGStep
            else:
                raise AssertionError(codec)
            return step_class(self.wizard, self._video_encoder)
        elif self.wizard.get_step_option('Source', 'has-audio'):
            return self.get_audio_page()
        else:
            return None

    # Private

    def _verify(self):
        # XXX: isn't there a better way of doing this, like blocking
        #      the signal

        format = self.combobox_format.get_active()
        if format == EncodingFormat.Ogg:
            self.debug('running Ogg checks')
            d = self.wizard.require_elements(self.worker, 'oggmux')

            yield d
            d = self.run_in_worker('flumotion.component.muxers.checks', 'checkOgg')

            yield d

            # XXX: Smoke can't be put in ogg. Poke Wim to fix
            self.combobox_video.set_multi_active(EncodingVideo.Theora)
            self.combobox_audio.set_multi_active(EncodingAudio.Speex,
                                                 EncodingAudio.Vorbis)
        elif format == EncodingFormat.Multipart:
            self.combobox_video.set_multi_active(EncodingVideo.Smoke,
                                                 EncodingVideo.JPEG)
            self.combobox_audio.set_multi_active(EncodingAudio.Mulaw)

        has_audio = self.wizard.get_step_option('Source', 'has-audio')
        self.combobox_audio.set_property('visible', has_audio)
        self.label_audio.set_property('visible', has_audio)

        has_video = self.wizard.get_step_option('Source', 'has-video')
        self.combobox_video.set_property('visible', has_video)
        self.label_video.set_property('visible', has_video)
    _verify = defer_generator_method(_verify)

    # Callbacks

    def on_combobox_format_changed(self, combo):
        format = combo.get_active()
        if format == 0:
            return

        self._muxer.name = combo.get_active().component_type
        self._verify()

    def on_combobox_audio_changed(self, combo):
        audio = combo.get_active()
        if audio == 0:
            return

        self._audio_encoder.name = combo.get_active().component_type

    def on_combobox_video_changed(self, combo):
        video = combo.get_active()
        if video == 0:
            return

        self._video_encoder.name = combo.get_active().component_type


class TheoraStep(VideoEncoderStep):
    name = 'Theora encoder'
    sidebar_name = 'Theora'
    glade_file = 'wizard_theora.glade'
    component_type = 'theora'
    icon = 'xiphfish.png'

    # WizardStep

    def setup(self):
        # XXX: move to glade file
        self.spinbutton_bitrate.set_range(0, 4000)
        self.spinbutton_bitrate.set_value(400)
        self.spinbutton_quality.set_range(0, 63)
        self.spinbutton_quality.set_value(16)

    def worker_changed(self):
        d = self.wizard.require_elements(self.worker, 'theoraenc')

        yield d

        d = self.run_in_worker('flumotion.worker.checks.encoder', 'checkTheora')

        yield d
    worker_changed = defer_generator_method(worker_changed)

    def get_state(self):
        options = {}
        if self.radiobutton_bitrate:
            options['bitrate'] = int(self.spinbutton_bitrate.get_value()) * 1000
        elif self.radiobutton_quality:
            options['quality'] = int(self.spinbutton_quality.get_value())

        options['keyframe-maxdistance'] = int(self.spinbutton_keyframe_maxdistance.get_value())
        options['noise-sensitivity'] = \
            max(int(self.spinbutton_noise_sensitivity.get_value()
                    * (32768 / 100.)),
                1)
        options['sharpness'] = int(self.spinbutton_sharpness.get_value())

        return options

    def get_next(self):
        return self.wizard.get_step('Encoding').get_audio_page()

    # Callbacks

    def on_radiobutton_toggled(self, button):
        # This is bound to both radiobutton_bitrate and radiobutton_quality
        self.spinbutton_bitrate.set_sensitive(
            self.radiobutton_bitrate.get_active())
        self.spinbutton_quality.set_sensitive(
            self.radiobutton_quality.get_active())


class SmokeStep(VideoEncoderStep):
    name = 'Smoke encoder'
    sidebar_name = 'Smoke'
    glade_file = 'wizard_smoke.glade'
    section = 'Conversion'
    component_type = 'smoke'

    # WizardStep

    def worker_changed(self):
        self.wizard.require_elements(self.worker, 'smokeenc')

    def get_state(self):
        options = VideoEncoderStep.get_state(self)
        options['qmin'] = int(options['qmin'])
        options['qmax'] = int(options['qmax'])
        options['threshold'] = int(options['threshold'])
        options['keyframe'] = int(options['keyframe'])
        return options

    def get_next(self):
        return self.wizard.get_step('Encoding').get_audio_page()


class JPEGStep(VideoEncoderStep):
    name = 'JPEG encoder'
    sidebar_name = 'JPEG'
    glade_file = 'wizard_jpeg.glade'
    section = 'Conversion'
    component_type = 'jpeg'

    # WizardStep

    def worker_changed(self):
        self.wizard.require_elements(self.worker, 'jpegenc')

    def get_state(self):
        options = VideoEncoderStep.get_state(self)
        options['quality'] = int(options['quality'])
        options['framerate'] = _fraction_from_float(options['framerate'], 2)
        return options

    def get_next(self):
        return self.wizard.get_step('Encoding').get_audio_page()


# Worker?
class VorbisStep(AudioEncoderStep):
    glade_file = 'wizard_vorbis.glade'
    name = 'Vorbis encoder'
    sidebar_name = 'Vorbis'
    component_type = 'vorbis'
    icon = 'xiphfish.png'

    # WizardStep

    def setup(self):
        self.spinbutton_bitrate.set_range(6, 250)
        self.spinbutton_bitrate.set_value(64)
        # By choosing quality as a default, we avoid samplerate/bitrate
        # mismatch
        self.radiobutton_bitrate.set_active(False)
        self.radiobutton_quality.set_active(True)

    def worker_changed(self):
        self.debug('running Vorbis checks')
        d = self.wizard.require_elements(self.worker, 'vorbisenc')

        yield d
        d = self.run_in_worker('flumotion.worker.checks.encoder', 'checkVorbis')

        yield d
    worker_changed = defer_generator_method(worker_changed)

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
    name = 'Speex encoder'
    sidebar_name = 'Speex'
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
        options = AudioEncoderStep.get_state(self)
        options['bitrate'] = int(self.spinbutton_bitrate.get_value()) * 1000
        return options
