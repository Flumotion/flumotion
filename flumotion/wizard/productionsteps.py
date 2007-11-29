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
import math

import gtk
from flumotion.twisted.defer import defer_generator_method

from flumotion.common import errors, messages
from flumotion.common.messages import N_
from flumotion.common.python import sorted
from flumotion.ui.fgtk import ProxyWidgetMapping
from flumotion.wizard.basesteps import WorkerWizardStep, \
    AudioSourceStep, VideoSourceStep
from flumotion.wizard.enums import AudioDevice, SoundcardSystem, \
    AudioTestSamplerate, VideoDevice, VideoTestFormat, VideoTestPattern
from flumotion.wizard.models import AudioProducer, VideoProducer

T_ = messages.gettexter('flumotion')
_ = gettext.gettext

# pychecker doesn't like the auto-generated widget attrs
# or the extra args we name in callbacks
__pychecker__ = 'no-classattr no-argsused'

# the denominator arg for all calls of this function was sniffed from
# the glade file's spinbutton adjustment

def _fraction_from_float(number, denominator):
    """
    Return a string to be used in serializing to XML.
    """
    return "%d/%d" % (number * denominator, denominator)


class ProductionStep(WorkerWizardStep):
    glade_typedict = ProxyWidgetMapping()

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
        @rtype: a L{VideoSourceStep} subclass
        """
        source = self.combobox_video.get_selected()
        if source == VideoDevice.Test:
            step_class = TestVideoSourceStep
        elif source == VideoDevice.Webcam:
            step_class = WebcamStep
        elif source == VideoDevice.TVCard:
            step_class = TVCardStep
        elif source == VideoDevice.Firewire:
            step_class = FireWireStep
        else:
            raise AssertionError(source)

        return step_class(self.wizard, self._video_producer)

    def get_audio_step(self):
        """Return the audio step to be shown, given the currently
        selected values in this step
        @returns: audio step
        @rtype: a L{AudioSourceStep} subclass
        """
        source = self.combobox_audio.get_selected()
        if source == AudioDevice.Test:
            step_class = TestAudioSourceStep
        elif source == AudioDevice.Soundcard:
            step_class = SoundcardStep
        elif source == AudioDevice.Firewire:
            # Only show firewire audio if we're using firewire video
            if self.combobox_video.get_active() == VideoDevice.Firewire:
                return
            step_class = FireWireAudioStep
        else:
            raise AssertionError(source)
        return step_class(self.wizard, self._audio_producer)

    # WizardStep

    def activated(self):
        self._verify()

    def get_next(self):
        if self.checkbutton_has_video.get_active():
            return self.get_video_step()
        elif self.checkbutton_has_audio.get_active():
            return self.get_audio_step()
        else:
            raise AssertionError

    def get_state(self):
        return {
            'audio': self.combobox_audio.get_selected(),
            'video': self.combobox_video.get_selected(),
            'has-audio': self.checkbutton_has_audio.get_active(),
            'has-video': self.checkbutton_has_video.get_active(),
            }

    # Private API

    def _setup(self):
        self._audio_producer = AudioProducer()
        self.wizard.flow.addComponent(self._audio_producer)
        self._video_producer = VideoProducer()
        self.wizard.flow.addComponent(self._video_producer)

        self.combobox_video.set_enum(VideoDevice)
        self.combobox_audio.set_enum(AudioDevice)
        tips = gtk.Tooltips()
        tips.set_tip(self.checkbutton_has_video,
                     _('If you want to stream video'))
        tips.set_tip(self.checkbutton_has_audio,
                     _('If you want to stream audio'))

    def _verify(self):
        # FIXME: We should wait for the first worker to connect before
        #        opening the wizard or so
        if not hasattr(self.wizard, 'combobox_worker'):
            return

        has_audio = self.checkbutton_has_audio.get_active()
        has_video = self.checkbutton_has_video.get_active()
        can_continue = False
        can_select_worker = False
        if has_audio or has_video:
            can_continue = True

            video_source = self.combobox_video.get_active()
            audio_source = self.combobox_audio.get_active()
            if (has_audio and audio_source == AudioDevice.Firewire and
                not (has_video and video_source == VideoDevice.Firewire)):
                can_select_worker = True
        self.wizard.block_next(not can_continue)

        self.wizard.combobox_worker.set_sensitive(can_select_worker)

    # Callbacks

    def on_checkbutton_has_video_toggled(self, button):
        self.combobox_video.set_sensitive(button.get_active())
        if button.get_active():
            self.wizard.flow.addComponent(self._video_producer)
        else:
            self.wizard.flow.removeComponent(self._video_producer)
        self._verify()

    def on_checkbutton_has_audio_toggled(self, button):
        self.combobox_audio.set_sensitive(button.get_active())
        if button.get_active():
            self.wizard.flow.addComponent(self._audio_producer)
        else:
            self.wizard.flow.removeComponent(self._audio_producer)
        self._verify()

    def on_combobox_video_changed(self, button):
        video_source = self.combobox_video.get_active()
        # FIXME!!!
        if type(video_source) == int:
            return
        self._video_producer.name = video_source.component_type
        self._verify()

    def on_combobox_audio_changed(self, button):
        audio_source = self.combobox_audio.get_active()
        # FIXME!!!
        if type(audio_source) == int:
            return
        self._audio_producer.name = audio_source.component_type
        self._verify()


class TestVideoSourceStep(VideoSourceStep):
    glade_typedict = ProxyWidgetMapping()
    name = _('Test Video Source')
    glade_file = 'wizard_testsource.glade'
    component_type = 'videotestsrc'
    icon = 'testsource.png'

    # WizardStep

    def setup(self):
        self.combobox_pattern.set_enum(VideoTestPattern)
        self.combobox_format.set_enum(VideoTestFormat)

        # FIXME: Remember to remove the values from the glade file
        #        when we use proxy widgets
        self.model.width = 320
        self.model.height = 240

    def before_show(self):
        self.wizard.require_elements(self.worker, 'videotestsrc')

    def get_state(self):
        format = self.combobox_format.get_selected()
        options = {}
        if format == VideoTestFormat.YUV:
            options['format'] = 'video/x-raw-yuv'
        elif format == VideoTestFormat.RGB:
            options['format'] = 'video/x-raw-rgb'
        else:
            raise AssertionError

        options['pattern'] = self.combobox_pattern.get_selected().value
        options['width'] = int(self.spinbutton_width.get_value())
        options['height'] = int(self.spinbutton_height.get_value())
        options['framerate'] = _fraction_from_float(
            self.spinbutton_framerate.get_value(), 10)
        return options

    # Callbacks

    def on_spinbutton_height_value_changed(self, spinbutton):
        self.model.height = spinbutton.get_value()

    def on_spinbutton_width_value_changed(self, spinbutton):
        self.model.width = spinbutton.get_value()


class WebcamStep(VideoSourceStep):
    glade_typedict = ProxyWidgetMapping()
    name = _('Webcam')
    glade_file = 'wizard_webcam.glade'
    component_type = 'video4linux'
    icon = 'webcam.png'

    def __init__(self, wizard, model):
        VideoSourceStep.__init__(self, wizard, model)
        self._in_setup = False
        # _sizes is probed, not set from the UI
        self._sizes = None
        self._factoryName = None

    # WizardStep

    def setup(self):
        self._in_setup = True
        self.combobox_device.prefill(['/dev/video0',
                                      '/dev/video1',
                                      '/dev/video2',
                                      '/dev/video3'])
        self._in_setup = False

    def worker_changed(self):
        self._clear()
        self._run_checks()

    def get_state(self):
        options = {}
        size = self.combobox_size.get_selected()
        if size:
            w, h = size
        else:
            self.warning('something bad happened: no height/width selected?')
            w, h = 320, 240

        framerate = self.combobox_framerate.get_selected()
        if framerate:
            num, denom = framerate['framerate']
            mime = framerate['mime']
            format = framerate.get('format', None)
        else:
            self.warning('something bad happened: no framerate selected?')
            num, denom = 15, 2
            mime = 'video/x-raw-yuv'
            format = None

        options['device'] = self.combobox_device.get_selected()
        options['width'] = w
        options['element-factory'] = self._factoryName
        options['height'] = h
        options['framerate'] = '%d/%d' % (num, denom)
        options['mime'] = mime
        if format:
            options['format'] = format
        return options

    # Private

    def _clear(self):
        self.combobox_size.set_sensitive(False)
        self.combobox_framerate.set_sensitive(False)
        self.label_name.set_label("")
        self.wizard.block_next(True)

    def _run_checks(self):
        if self._in_setup:
            return None

        self.wizard.block_next(True)

        device = self.combobox_device.get_selected()
        msg = messages.Info(T_(
                N_("Probing webcam, this can take a while...")),
            id='webcam-check')
        self.wizard.add_msg(msg)
        d = self.run_in_worker('flumotion.worker.checks.video', 'checkWebcam',
                           device, id='webcam-check')

        def errRemoteRunFailure(failure):
            failure.trap(errors.RemoteRunFailure)
            self.debug('a RemoteRunFailure happened')
            self._clear()

        def errRemoteRunError(failure):
            failure.trap(errors.RemoteRunError)
            self.debug('a RemoteRunError happened')
            self._clear()

        def deviceFound(result):
            if not result:
                self.debug('no device %s' % device)
                self._clear()
                return None

            deviceName, factoryName, sizes = result
            self._factoryName = factoryName
            self._set_sizes(sizes)
            self.wizard.clear_msg('webcam-check')
            self.label_name.set_label(deviceName)
            self.wizard.block_next(False)
            self.combobox_size.set_sensitive(True)
            self.combobox_framerate.set_sensitive(True)

        d.addCallback(deviceFound)
        d.addErrback(errRemoteRunFailure)
        d.addErrback(errRemoteRunError)

    def _set_sizes(self, sizes):
        # Set sizes before populating the values, since
        # it trigger size_changed which depends on this
        # to be set
        self._sizes = sizes

        values = []
        for w, h in sorted(sizes.keys(), reverse=True):
            values.append(['%d x %d' % (w, h), (w, h)])
        self.combobox_size.prefill(values)

    def _set_framerates(self, size):
        values = []
        for d in self._sizes[size]:
            num, denom = d['framerate']
            values.append(('%.2f fps' % (1.0*num/denom), d))
        self.combobox_framerate.prefill(values)
        self.model.width, self.model.height = size

    # Callbacks

    def on_combobox_device_changed(self, combo):
        self._run_checks()

    def on_combobox_size_changed(self, combo):
        size = self.combobox_size.get_selected()
        if size:
            self._set_framerates(size)


# note:
# v4l talks about "signal" (PAL/...) and "channel" (TV/Composite/...)
# and frequency
# gst talks about "norm" and "channel"
# and frequency
# apps (and flumotion) talk about "TV Norm" and "source",
# and channel (corresponding to frequency)
class TVCardStep(VideoSourceStep):
    glade_typedict = ProxyWidgetMapping()
    name = _('TV Card')
    glade_file = 'wizard_tvcard.glade'
    component_type = 'bttv'
    icon = 'tv.png'

    def __init__(self, wizard, model):
        VideoSourceStep.__init__(self, wizard, model)
        self._in_setup = False

    # WizardStep

    def setup(self):
        self._in_setup = True
        self.combobox_device.prefill(['/dev/video0',
                                      '/dev/video1',
                                      '/dev/video2',
                                      '/dev/video3'])
        self._in_setup = False

    def worker_changed(self):
        self._clear_combos()
        self._run_checks()

    def get_state(self):
        options = {}
        options['device'] = self.combobox_device.get_selected()
        options['signal'] = self.combobox_tvnorm.get_selected()
        options['channel'] = self.combobox_source.get_selected()
        options['width'] = int(self.spinbutton_width.get_value())
        options['height'] = int(self.spinbutton_height.get_value())
        options['framerate'] = \
            _fraction_from_float(self.spinbutton_framerate.get_value(), 10)
        return options

    # Private

    def _clear_combos(self):
        self.combobox_tvnorm.clear()
        self.combobox_tvnorm.set_sensitive(False)
        self.combobox_source.clear()
        self.combobox_source.set_sensitive(False)

    def _run_checks(self):
        if self._in_setup:
            return None

        self.wizard.block_next(True)

        device = self.combobox_device.get_selected()
        assert device
        msg = messages.Info(T_(
            N_("Probing TV-card, this can take a while...")),
                            id='tvcard-check')
        self.wizard.add_msg(msg)
        d = self.run_in_worker('flumotion.worker.checks.video', 'checkTVCard',
                               device, id='tvcard-check')

        def errRemoteRunFailure(failure):
            failure.trap(errors.RemoteRunFailure)
            self.debug('a RemoteRunFailure happened')
            self._clear_combos()

        def errRemoteRunError(failure):
            failure.trap(errors.RemoteRunError)
            self.debug('a RemoteRunError happened')
            self._clear_combos()

        def deviceFound(result):
            if not result:
                self._clear_combos()
                return None

            deviceName, channels, norms = result
            self.wizard.clear_msg('tvcard-check')
            self.wizard.block_next(False)
            self.combobox_tvnorm.prefill(norms)
            self.combobox_tvnorm.set_sensitive(True)
            self.combobox_source.prefill(channels)
            self.combobox_source.set_sensitive(True)

        d.addCallback(deviceFound)
        d.addErrback(errRemoteRunFailure)
        d.addErrback(errRemoteRunError)

    # Callbacks

    def on_combobox_device_changed(self, combo):
        self._run_checks()

    def on_spinbutton_height_value_changed(self, spinbutton):
        self.model.height = spinbutton.get_value()

    def on_spinbutton_width_value_changed(self, spinbutton):
        self.model.width = spinbutton.get_value()


class FireWireStep(VideoSourceStep):
    glade_typedict = ProxyWidgetMapping()
    name = _('Firewire')
    glade_file = 'wizard_firewire.glade'
    component_type = 'firewire'
    icon = 'firewire.png'
    width_corrections = ['none', 'pad', 'stretch']

    def __init__(self, wizard, model):
        VideoSourceStep.__init__(self, wizard, model)

        # options detected from the device:
        self._dims = None
        self._factors = [1, 2, 3, 4, 6, 8]
        self._input_heights = None
        self._input_widths = None
        self._par = None

        # these are instance state variables:
        self._is_square = None
        self._factor_i = None             # index into self.factors
        self._width_correction = None     # currently chosen item from
                                          # width_corrections

    # WizardStep

    def worker_changed(self):
        self._run_checks()

    def get_state(self):
        options = {} # VideoSourceStep.get_state(self)
        d = self._get_width_height()
        options['height'] = d['oh']
        options['scaled-width'] = d['sw']
        options['width'] = d['ow']
        options['is-square'] = self._is_square
        options['framerate'] = \
            _fraction_from_float(self.spinbutton_framerate.get_value(), 2)
        return options

    # Private

    def _set_sensitive(self, is_sensitive):
        self.vbox_controls.set_sensitive(is_sensitive)
        self.wizard.block_next(not is_sensitive)

    def _update_output_format(self):
        d = self._get_width_height()
        self.model.width = d['ow']
        self.model.height = d['oh']
        num, den = 1, 1
        if not self._is_square:
            num, den = self._par[0], self._par[1]

        msg = _('%dx%d, %d/%d pixel aspect ratio') % (
                   d['ow'], d['oh'], num, den)
        self.label_output_format.set_markup(msg)

    def _run_checks(self):
        self._set_sensitive(False)
        msg = messages.Info(T_(N_('Checking for Firewire device...')),
            id='firewire-check')
        self.wizard.add_msg(msg)
        d = self.run_in_worker('flumotion.worker.checks.video', 'check1394',
            id='firewire-check')
        yield d
        try:
            options = d.value()
            self.wizard.clear_msg('firewire-check')
            self._dims = (options['width'], options['height'])
            self._par = options['par']
            self._input_heights = [self._dims[1]/i for i in self._factors]
            self._input_widths = [self._dims[0]/i for i in self._factors]
            values = []
            for height in self._input_heights:
                values.append('%d pixels' % height)
            self.combobox_scaled_height.prefill(values)
            self._set_sensitive(True)
            self.on_update_output_format()
        except errors.RemoteRunFailure:
            pass
    _run_checks = defer_generator_method(_run_checks)

    def _get_width_height(self):
        # returns dict with sw, sh, ow, oh
        # which are scaled width and height, and output width and height
        sh = self._input_heights[self._factor_i]
        sw = self._input_widths[self._factor_i]
        par = 1. * self._par[0] / self._par[1]

        if self._is_square:
            sw = int(math.ceil(sw * par))
            # for GStreamer element sanity, make sw an even number
            # FIXME: check if this can now be removed
            # sw = sw + (2 - (sw % 2)) % 2

        # if scaled width (after squaring) is not multiple of 8, present
        # width correction
        self.frame_width_correction.set_sensitive(sw % 8 != 0)

        # actual output
        ow = sw
        oh = sh
        if self._width_correction == 'pad':
            ow = sw + (8 - (sw % 8)) % 8
        elif self._width_correction == 'stretch':
            ow = sw + (8 - (sw % 8)) % 8
            sw = ow

        return dict(sw=sw,sh=sh,ow=ow,oh=oh)

    # Callbacks

    def on_update_output_format(self, *args):
        # update label_camera_settings
        standard = 'Unknown'
        aspect = 'Unknown'
        h = self._dims[1]
        if h == 576:
            standard = 'PAL'
        elif h == 480:
            standard = 'NTSC'
        else:
            self.warning('Unknown capture standard for height %d' % h)

        nom = self._par[0]
        den = self._par[1]
        if nom == 59 or nom == 10:
            aspect = '4:3'
        elif nom == 118 or nom == 40:
            aspect = '16:9'
        else:
            self.warning('Unknown pixel aspect ratio %d/%d' % (nom, den))

        text = _('%s, %s (%d/%d pixel aspect ratio)') % (standard, aspect,
            nom, den)
        self.label_camera_settings.set_text(text)

        # factor is a double
        self._factor_i = self.combobox_scaled_height.get_active()
        self._is_square = self.checkbutton_square_pixels.get_active()

        self._width_correction = None
        for i in FireWireStep.width_corrections:
            if getattr(self,'radiobutton_width_'+i).get_active():
                self._width_correction = i
                break
        assert self._width_correction

        self._update_output_format()



class TestAudioSourceStep(AudioSourceStep):
    glade_typedict = ProxyWidgetMapping()
    name = _('Test Audio Source')
    glade_file = 'wizard_audiotest.glade'
    section = _('Production')
    icon = 'soundcard.png'

    # WizardStep

    def before_show(self):
        self.combobox_samplerate.set_enum(AudioTestSamplerate)
        self.combobox_samplerate.set_sensitive(True)

    def worker_changed(self):
        self.wizard.require_elements(self.worker, 'audiotestsrc')

    def get_state(self):
        return dict(frequency=int(self.spinbutton_freq.get_value()),
                    volume=float(self.spinbutton_volume.get_value()),
                    rate=int(self.combobox_samplerate.get_selected().name))

    def get_next(self):
        return None


OSS_DEVICES = ["/dev/dsp",
               "/dev/dsp1",
               "/dev/dsp2"]
ALSA_DEVICES = ['hw:0',
                'hw:1',
                'hw:2']
CHANNELS = [(_('Stereo'), 2),
            (_('Mono'), 1)]
BITDEPTHS = [(_('16-bit'), 16),
             (_('8-bit'), 8)]
SAMPLE_RATES = [48000,
                44100,
                32000,
                22050,
                16000,
                11025,
                8000]

class SoundcardStep(AudioSourceStep):
    glade_typedict = ProxyWidgetMapping()
    name = _('Soundcard')
    glade_file = 'wizard_soundcard.glade'
    section = _('Production')
    component_type = 'osssrc'
    icon = 'soundcard.png'

    def __init__(self, wizard, model):
        AudioSourceStep.__init__(self, wizard, model)
        self._block_update = False

    # WizardStep

    def setup(self):
        # block updates, because populating a shown combobox will of course
        # trigger the callback
        self._block_update = True
        self.combobox_system.set_enum(SoundcardSystem)
        self.combobox_channels.prefill(CHANNELS)
        self.combobox_samplerate.prefill([(str(r), r) for r in SAMPLE_RATES])
        self.combobox_bitdepth.prefill(BITDEPTHS)
        self._block_update = False

    def worker_changed(self):
        self._clear_combos()
        self._update_devices()
        self._update_inputs()

    def get_state(self):
        channels = self.combobox_channels.get_selected()
        element = self.combobox_system.get_selected().element_name
        bitdepth = self.combobox_bitdepth.get_selected()
        samplerate = self.combobox_samplerate.get_selected()
        input_track = self.combobox_input.get_selected()

        d = dict(device=self.combobox_device.get_selected(),
                 depth=int(bitdepth),
                 rate=int(samplerate),
                 channels=channels)
        if input_track:
            d['input-track'] = input_track
        # FIXME: can a key with a dash be specified ?
        d['source-element'] = element
        return d

    def get_next(self):
        return None

    # Private

    def _clear_combos(self):
        self.combobox_input.clear()
        self.combobox_input.set_sensitive(False)
        self.combobox_channels.set_sensitive(False)
        self.combobox_samplerate.set_sensitive(False)
        self.combobox_bitdepth.set_sensitive(False)

    def _update_devices(self):
        self._block_update = True
        self.combobox_device.clear()
        enum = self.combobox_system.get_selected()
        if enum == SoundcardSystem.Alsa:
            self.combobox_device.prefill(ALSA_DEVICES)
        elif enum == SoundcardSystem.OSS:
            self.combobox_device.prefill(OSS_DEVICES)
        else:
            raise AssertionError
        self._block_update = False

    def _update_inputs(self):
        if self._block_update:
            return
        self.wizard.block_next(True)

        system = self.combobox_system.get_selected()
        device = self.combobox_device.get_selected()
        channels = self.combobox_channels.get_selected() or 2
        d = self.run_in_worker('flumotion.worker.checks.audio', 'checkMixerTracks',
                               system.element_name,
                               device,
                               channels,
                               id='soundcard-check')

        def checkFailed(failure):
            self._clear_combos()
            self.wizard.block_next(True)

        def soundcardCheckComplete((deviceName, tracks)):
            self.wizard.clear_msg('soundcard-check')
            self.wizard.block_next(False)
            self.label_devicename.set_label(deviceName)
            self._block_update = True
            self.combobox_channels.set_sensitive(True)
            self.combobox_samplerate.set_sensitive(True)
            self.combobox_bitdepth.set_sensitive(True)
            self.combobox_input.prefill(tracks)
            self.combobox_input.set_sensitive(bool(tracks))
            self._block_update = False

        d.addCallback(soundcardCheckComplete)
        d.addErrback(checkFailed)

        return d

    # Callbacks

    def on_combobox_system_changed(self, combo):
        if not self._block_update:
            self._update_devices()
            self._update_inputs()

    def on_combobox_device_changed(self, combo):
        self._update_inputs()

    def on_combobox_channels_changed(self, combo):
        # FIXME: make it so that the number of channels can be changed
        # and the check gets executed with the new number
        # self.update_inputs()
        pass


class FireWireAudioStep(AudioSourceStep):
    name = _('Firewire audio')
    section = _('Production')
    glade_file = 'wizard_firewire.glade'
    component_type = 'firewire'
    icon = 'firewire.png'
    width_corrections = ['none', 'pad', 'stretch']

    def __init__(self, wizard, model):
        AudioSourceStep.__init__(self, wizard, model)

        # options detected from the device:
        self._dims = None
        self._factors = [1, 2, 3, 4, 6, 8]
        self._input_heights = None
        self._input_widths = None
        self._par = None

        # these are instance state variables:
        self._is_square = None
        self._factor_i = None             # index into self.factors
        self._width_correction = None     # currently chosen item from
                                          # width_corrections

    # WizardStep

    def setup(self):
        self.frame_scaling.hide()
        self.frame_width_correction.hide()
        self.frame_capture.hide()
        self.frame_output_format.hide()

    def worker_changed(self):
        self._run_checks()

    def get_state(self):
        options = {} # VideoSourceStep.get_state(self)
        d = self._get_width_height()
        options['height'] = d['oh']
        options['scaled-width'] = d['sw']
        options['width'] = d['ow']
        options['is-square'] = self._is_square
        options['framerate'] = \
            _fraction_from_float(self.spinbutton_framerate.get_value(), 2)
        return options

    def get_next(self):
        return None

    # Private API

    def _set_sensitive(self, is_sensitive):
        self.vbox_controls.set_sensitive(is_sensitive)
        self.wizard.block_next(not is_sensitive)

    def _update_output_format(self):
        d = self._get_width_height()
        num, den = 1, 1
        if not self._is_square:
            num, den = self._par[0], self._par[1]

        msg = _('%dx%d, %d/%d pixel aspect ratio') % (
                   d['ow'], d['oh'], num, den)
        self.label_output_format.set_markup(msg)

    def _run_checks(self):
        self._set_sensitive(False)
        msg = messages.Info(T_(N_('Checking for Firewire device...')),
            id='firewire-check')
        self.wizard.add_msg(msg)
        d = self.run_in_worker('flumotion.worker.checks.video', 'check1394',
            id='firewire-check')
        def firewireCheckDone(options):
            self.wizard.clear_msg('firewire-check')
            self._dims = (options['width'], options['height'])
            self._par = options['par']
            self._input_heights = [self._dims[1]/i for i in self._factors]
            self._input_widths = [self._dims[0]/i for i in self._factors]
            store = gtk.ListStore(str)
            for i in self._input_heights:
                store.set(store.append(), 0, '%d pixels' % i)
            self.combobox_scaled_height.set_model(store)
            self.combobox_scaled_height.set_active(1)
            self._set_sensitive(True)
            self.on_update_output_format()
        d.addCallback(firewireCheckDone)
        return d

    def _get_width_height(self):
        # returns dict with sw, sh, ow, oh
        # which are scaled width and height, and output width and height
        sh = self._input_heights[self._factor_i]
        sw = self._input_widths[self._factor_i]
        par = 1. * self._par[0] / self._par[1]

        if self._is_square:
            sw = int(math.ceil(sw * par))
            # for GStreamer element sanity, make sw an even number
            # FIXME: check if this can now be removed
            # sw = sw + (2 - (sw % 2)) % 2

        # if scaled width (after squaring) is not multiple of 8, present
        # width correction
        self.frame_width_correction.set_sensitive(sw % 8 != 0)

        # actual output
        ow = sw
        oh = sh
        if self._width_correction == 'pad':
            ow = sw + (8 - (sw % 8)) % 8
        elif self._width_correction == 'stretch':
            ow = sw + (8 - (sw % 8)) % 8
            sw = ow

        return dict(sw=sw,sh=sh,ow=ow,oh=oh)

    # Callbacks

    def on_update_output_format(self, *args):
        # update label_camera_settings
        standard = 'Unknown'
        aspect = 'Unknown'
        h = self._dims[1]
        if h == 576:
            standard = 'PAL'
        elif h == 480:
            standard = 'NTSC'
        else:
            self.warning('Unknown capture standard for height %d' % h)

        nom = self._par[0]
        den = self._par[1]
        if nom == 59 or nom == 10:
            aspect = '4:3'
        elif nom == 118 or nom == 40:
            aspect = '16:9'
        else:
            self.warning('Unknown pixel aspect ratio %d/%d' % (nom, den))

        text = _('%s, %s (%d/%d pixel aspect ratio)') % (standard, aspect,
            nom, den)
        self.label_camera_settings.set_text(text)

        # factor is a double
        self._factor_i = self.combobox_scaled_height.get_active()
        self._is_square = self.checkbutton_square_pixels.get_active()

        self._width_correction = None
        for i in FireWireAudioStep.width_corrections:
            if getattr(self,'radiobutton_width_'+i).get_active():
                self._width_correction = i
                break
        assert self._width_correction

        self._update_output_format()


