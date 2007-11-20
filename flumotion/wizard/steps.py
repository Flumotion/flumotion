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
import sets

import gtk
from twisted.internet import defer

from flumotion.twisted.defer import defer_generator_method
from flumotion.common import errors, messages
from flumotion.common.messages import N_, ngettext
from flumotion.common.pygobject import gsignal
from flumotion.common.python import sorted, any
from flumotion.configure import configure
from flumotion.ui.wizard import WizardStep, SectionWizard
from flumotion.wizard import save
from flumotion.wizard.enums import AudioDevice, EncodingAudio, \
     EncodingFormat, EncodingVideo, LicenseType, RotateSize, \
     RotateTime, SoundcardBitdepth, SoundcardChannels, SoundcardSystem, \
     SoundcardAlsaDevice, SoundcardOSSDevice, SoundcardSamplerate, \
     AudioTestSamplerate, VideoDevice, VideoTestFormat, VideoTestPattern
from flumotion.wizard.models import AudioProducer, VideoProducer, \
    AudioEncoder, VideoEncoder, Muxer, Flow
from flumotion.wizard.worker import WorkerList

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


class WorkerWizardStep(WizardStep):
    # optional
    has_worker = True

    def __init__(self, wizard):
        WizardStep.__init__(self, wizard)
        self.worker = None

    def worker_changed(self):
        pass

    def run_in_worker(self, module, function, *args, **kwargs):
        return self.wizard.run_in_worker(self.worker, module, function,
                                         *args, **kwargs)


class AudioSourceStep(WorkerWizardStep):
    def __init__(self, wizard, model):
        self.model = model
        WorkerWizardStep.__init__(self, wizard)


class VideoSourceStep(WorkerWizardStep):
    section = 'Production'
    icon = 'widget_doc.png'

    def __init__(self, wizard, model):
        self.model = model
        WorkerWizardStep.__init__(self, wizard)

    # WizardStep

    def get_next(self):
        return OverlayStep(self.wizard, self.model)

    def get_state(self):
        options = WorkerWizardStep.get_state(self)
        options['width'] = int(options['width'])
        options['height'] = int(options['height'])
        return options


class VideoEncoderStep(WorkerWizardStep):
    section = 'Conversion'

    def __init__(self, wizard, model):
        self.model = model
        WorkerWizardStep.__init__(self, wizard)


class AudioEncoderStep(WorkerWizardStep):
    glade_file = 'wizard_audio_encoder.glade'
    section = 'Conversion'

    def __init__(self, wizard, model):
        self.model = model
        WorkerWizardStep.__init__(self, wizard)

    # WizardStep

    def get_next(self):
        return None


class WelcomeStep(WorkerWizardStep):
    glade_file = 'wizard_welcome.glade'
    name = 'Welcome'
    section = 'Welcome'
    icon = 'wizard.png'
    has_worker = False

    def before_show(self):
        self.textview_message.realize()
        normal_bg = self.textview_message.get_style().bg[gtk.STATE_NORMAL]
        self.textview_message.modify_base(gtk.STATE_INSENSITIVE, normal_bg)

    def get_next(self):
        return None


class ProductionStep(WorkerWizardStep):
    glade_file = 'wizard_source.glade'
    name = 'Source'
    section = 'Production'
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
        source = self.combobox_video.get_active()
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
        source = self.combobox_audio.get_active()
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

        self.combobox_video.set_active(VideoDevice.Test)
        self.combobox_audio.set_active(AudioDevice.Test)

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
    name = 'Test Video Source'
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
        format = self.combobox_format.get_enum()
        options = {}
        if format == VideoTestFormat.YUV:
            options['format'] = 'video/x-raw-yuv'
        elif format == VideoTestFormat.RGB:
            options['format'] = 'video/x-raw-rgb'
        else:
            raise AssertionError

        options['pattern'] = self.combobox_pattern.get_value()
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
    name = 'Webcam'
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
        self.combobox_device.set_list(('/dev/video0',
                                       '/dev/video1',
                                       '/dev/video2',
                                       '/dev/video3'))
        cell = gtk.CellRendererText()
        self.combobox_size.pack_start(cell, True)
        self.combobox_size.add_attribute(cell, 'text', 0)
        cell = gtk.CellRendererText()
        self.combobox_framerate.pack_start(cell, True)
        self.combobox_framerate.add_attribute(cell, 'text', 0)
        self._in_setup = False

    def worker_changed(self):
        self._clear()
        self._run_checks()

    def get_state(self):
        options = {}
        i = self.combobox_size.get_active_iter()
        if i:
            w, h = self.combobox_size.get_model().get(i, 1, 2)
        else:
            self.warning('something bad happened: no height/width selected?')
            w, h = 320, 240
        i = self.combobox_framerate.get_active_iter()
        if i:
            d = self.combobox_framerate.get_model().get_value(i, 1)
            num, denom = d['framerate']
            mime = d['mime']
            format = d.get('format', None)
        else:
            self.warning('something bad happened: no framerate selected?')
            num, denom = 15, 2
            mime = 'video/x-raw-yuv'
            format = None

        options['device'] = self.combobox_device.get_string()
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
            yield None

        self.wizard.block_next(True)

        device = self.combobox_device.get_string()
        msg = messages.Info(T_(
                N_("Probing webcam, this can take a while...")),
            id='webcam-check')
        self.wizard.add_msg(msg)
        d = self.run_in_worker('flumotion.worker.checks.video', 'checkWebcam',
                           device, id='webcam-check')
        yield d
        try:
            result = d.value()

            if not result:
                self.debug('no device %s' % device)
                yield None

            deviceName, factoryName, sizes = result
            self._factoryName = factoryName
            self._sizes = sizes
            self.wizard.clear_msg('webcam-check')
            self.label_name.set_label(deviceName)
            self.wizard.block_next(False)
            self.combobox_size.set_sensitive(True)
            self.combobox_framerate.set_sensitive(True)
            store = gtk.ListStore(str, int, int)

            for w, h in sorted(sizes.keys(), reverse=True):
                store.append(['%d x %d' % (w,h), w, h])
            self.combobox_size.set_model(store)
            self.combobox_size.set_active(0)
        except errors.RemoteRunFailure, e:
            self.debug('a RemoteRunFailure happened')
            self._clear()
    _run_checks = defer_generator_method(_run_checks)

    # Callbacks

    def on_combobox_device_changed(self, combo):
        self._run_checks()

    def on_combobox_size_changed(self, combo):
        # check for custom
        i = self.combobox_size.get_active_iter()
        if i:
            w, h = self.combobox_size.get_model().get(i, 1, 2)
            store = gtk.ListStore(str, object)
            for d in self._sizes[(w,h)]:
                num, denom = d['framerate']
                store.append(['%.2f fps' % (1.0*num/denom), d])
            # add custom
            self.combobox_framerate.set_model(store)
            self.combobox_framerate.set_active(0)
            self.model.width = w
            self.model.height = w


# note:
# v4l talks about "signal" (PAL/...) and "channel" (TV/Composite/...)
# and frequency
# gst talks about "norm" and "channel"
# and frequency
# apps (and flumotion) talk about "TV Norm" and "source",
# and channel (corresponding to frequency)
class TVCardStep(VideoSourceStep):
    name = 'TV Card'
    glade_file = 'wizard_tvcard.glade'
    component_type = 'bttv'
    icon = 'tv.png'

    def __init__(self, wizard, model):
        VideoSourceStep.__init__(self, wizard, model)
        self._in_setup = False

    # WizardStep

    def setup(self):
        self._in_setup = True
        self.combobox_device.set_list(('/dev/video0',
                                       '/dev/video1',
                                       '/dev/video2',
                                       '/dev/video3'))
        self._in_setup = False

    def worker_changed(self):
        self._clear_combos()
        self._run_checks()

    def get_state(self):
        options = {}
        options['device'] = self.combobox_device.get_string()
        options['signal'] = self.combobox_tvnorm.get_string()
        options['channel'] = self.combobox_source.get_string()
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
            yield None

        self.wizard.block_next(True)

        device = self.combobox_device.get_string()
        assert device
        d = self.run_in_worker('flumotion.worker.checks.video', 'checkTVCard',
                           device, id='tvcard-check')
        yield d
        try:
            value = d.value()
            if not value:
                yield None

            deviceName, channels, norms = value
            self.wizard.clear_msg('tvcard-check')
            self.wizard.block_next(False)
            self.combobox_tvnorm.set_list(norms)
            self.combobox_tvnorm.set_sensitive(True)
            self.combobox_source.set_list(channels)
            self.combobox_source.set_sensitive(True)
        except errors.RemoteRunFailure, e:
            pass
    _run_checks = defer_generator_method(_run_checks)

    # Callbacks

    def on_combobox_device_changed(self, combo):
        self._run_checks()

    def on_spinbutton_height_value_changed(self, spinbutton):
        self.model.height = spinbutton.get_value()

    def on_spinbutton_width_value_changed(self, spinbutton):
        self.model.width = spinbutton.get_value()


class FireWireStep(VideoSourceStep):
    name = 'Firewire'
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
            store = gtk.ListStore(str)
            for i in self._input_heights:
                store.set(store.append(), 0, '%d pixels' % i)
            self.combobox_scaled_height.set_model(store)
            self.combobox_scaled_height.set_active(1)
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
        for i in self._width_corrections:
            if getattr(self,'radiobutton_width_'+i).get_active():
                self._width_correction = i
                break
        assert self._width_correction

        self._update_output_format()



class TestAudioSourceStep(AudioSourceStep):
    name = 'Test Audio Source'
    glade_file = 'wizard_audiotest.glade'
    section = 'Production'
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
                    rate=self.combobox_samplerate.get_int())

    def get_next(self):
        return None


class SoundcardStep(AudioSourceStep):
    name = 'Soundcard'
    glade_file = 'wizard_soundcard.glade'
    section = 'Production'
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
        self._block_update = False

    def worker_changed(self):
        self._clear_combos()
        self._update_devices()
        self._update_inputs()

    def get_state(self):
        # FIXME: this can't be called if the soundcard hasn't been probed yet
        # for example, when going through the testsuite
        try:
            channels = self.combobox_channels.get_enum().intvalue
            element = self.combobox_system.get_enum().element
            bitdepth = self.combobox_bitdepth.get_string()
            samplerate = self.combobox_samplerate.get_string()
            input = self.combobox_input.get_string()
        except AttributeError:
            # when called without enum setup
            channels = 0
            element = "fakesrc"
            bitdepth = "9"
            samplerate = "12345"
            input = None

        d = dict(device=self.combobox_device.get_string(),
                 depth=int(bitdepth),
                 rate=int(samplerate),
                 channels=channels)
        if input:
            d['input-track'] = input
        # FIXME: can a key with a dash be specified ?
        d['source-element'] = element
        return d

    def get_next(self):
        return None

    # Private

    def _clear_combos(self):
        self.combobox_input.clear()
        self.combobox_input.set_sensitive(False)
        self.combobox_channels.clear()
        self.combobox_channels.set_sensitive(False)
        self.combobox_samplerate.clear()
        self.combobox_samplerate.set_sensitive(False)
        self.combobox_bitdepth.clear()
        self.combobox_bitdepth.set_sensitive(False)

    def _update_devices(self):
        self._block_update = True
        enum = self.combobox_system.get_enum()
        if enum == SoundcardSystem.Alsa:
            self.combobox_device.set_enum(SoundcardAlsaDevice)
        elif enum == SoundcardSystem.OSS:
            self.combobox_device.set_enum(SoundcardOSSDevice)
        else:
            raise AssertionError
        self._block_update = False

    def _update_inputs(self):
        if self._block_update:
            return
        self.wizard.block_next(True)

        enum = self.combobox_system.get_enum()
        device = self.combobox_device.get_string()
        e = self.combobox_channels.get_enum()
        channels = 2
        if e: channels = e.intvalue
        d = self.run_in_worker('flumotion.worker.checks.audio', 'checkMixerTracks',
                           enum.element, device, channels, id='soundcard-check')
        def soundcardCheckComplete((deviceName, tracks)):
            self.wizard.clear_msg('soundcard-check')
            self.wizard.block_next(False)
            self.label_devicename.set_label(deviceName)
            self._block_update = True
            self.combobox_channels.set_enum(SoundcardChannels)
            self.combobox_channels.set_sensitive(True)
            self.combobox_samplerate.set_enum(SoundcardSamplerate)
            self.combobox_samplerate.set_sensitive(True)
            self.combobox_bitdepth.set_enum(SoundcardBitdepth)
            self.combobox_bitdepth.set_sensitive(True)
            self._block_update = False

            self.combobox_input.set_list(tracks)
            self.combobox_input.set_sensitive(True)

        d.addCallback(soundcardCheckComplete)
        # FIXME: when probing failed, do
        # self.clear_combos()
        return d

    # Callbacks

    def on_combobox_system_changed(self, combo):
        if not self._block_update:
            self.update_devices()
            self.update_inputs()

    def on_combobox_device_changed(self, combo):
        self.update_inputs()

    def on_combobox_channels_changed(self, combo):
        # FIXME: make it so that the number of channels can be changed
        # and the check gets executed with the new number
        # self.update_inputs()
        pass


class FireWireAudioStep(AudioSourceStep):
    name = 'Firewire audio'
    glade_file = 'wizard_firewire.glade'
    component_type = 'firewire'
    icon = 'firewire.png'
    width_corrections = ['none', 'pad', 'stretch']
    section = 'Production'

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
        for i in self._width_corrections:
            if getattr(self,'radiobutton_width_'+i).get_active():
                self._width_correction = i
                break
        assert self._width_correction

        self._update_output_format()


class OverlayStep(WorkerWizardStep):
    name = 'Overlay'
    glade_file = 'wizard_overlay.glade'
    section = 'Production'
    component_type = 'overlay'
    icon = 'overlay.png'

    def __init__(self, wizard, video_producer):
        WorkerWizardStep.__init__(self, wizard)
        self._video_producer = video_producer
        self._can_overlay = True

    # Wizard Step

    def worker_changed(self):
        self._worker_changed_010()

    def get_state(self):
        options = WorkerWizardStep.get_state(self)
        if self.checkbutton_show_logo.get_active():
            options['show-logo'] = True

        if self.checkbutton_show_text.get_active():
            options['text'] = self.entry_text.get_text()

        options['can-overlay'] = self._can_overlay

        options['width'] = self._video_producer.width
        options['height'] = self._video_producer.height

        return options

    def get_next(self):
        if self.wizard.get_step_option('Source', 'has-audio'):
            return self.wizard.get_step('Source').get_audio_step()

        return None

    # Private API

    def _worker_changed_010(self):
        self._can_overlay = False
        self.set_sensitive(False)

        # first check elements
        d = self.wizard.check_elements(self.worker, 'pngenc',
            'ffmpegcolorspace', 'videomixer')
        yield d

        elements = d.value()
        if elements:
            f = ngettext("Worker '%s' is missing GStreamer element '%s'.",
                "Worker '%s' is missing GStreamer elements '%s'.",
                len(elements))
            message = messages.Warning(
                T_(f, self.worker, "', '".join(elements)), id='overlay')
            message.add(T_(N_("\n\nClick Next to proceed without overlay.")))
            self.wizard.add_msg(message)
        else:
            self.wizard.clear_msg('overlay')

        # now check import
        d = self.wizard.check_import(self.worker, 'PIL')
        yield d
        try:
            d.value()
            self._can_overlay = True
            self.set_sensitive(True)
        except ImportError:
            self.info('could not import PIL')
            message = messages.Warning(T_(N_(
                "Worker '%s' cannot import module '%s'."),
                self.worker, 'PIL'))
            message.add(T_(N_("\nThis module is part of '%s'."),
                           'Python Imaging Library'))
            message.add(T_(N_("\nThe project's homepage is %s"),
                           'http://www.pythonware.com/products/pil/'))
            message.add(T_(N_("\n\nClick Next to proceed without overlay.")))
            message.id = 'module-PIL'
            self.wizard.add_msg(message)
            self._can_overlay = False

    _worker_changed_010 = defer_generator_method(_worker_changed_010)

    def on_checkbutton_show_text_toggled(self, button):
        self.entry_text.set_sensitive(button.get_active())


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


class LicenseStep(WorkerWizardStep):
    name = "Content License"
    glade_file = "wizard_license.glade"
    section = 'License'
    icon = 'licenses.png'
    has_worker = False

    # WizardStep

    def setup(self):
        self.combobox_license.set_enum(LicenseType)

    def get_next(self):
        return None

    # Callbacks

    def on_checkbutton_set_license_toggled(self, button):
        self.combobox_license.set_sensitive(button.get_active())


class SummaryStep(WorkerWizardStep):
    name = "Summary"
    section = "Summary"
    glade_file = "wizard_summary.glade"
    icon = 'summary.png'
    has_worker = False
    last_step = True

    # WizardStep

    def before_show(self):
        self.textview_message.realize()
        normal_bg = self.textview_message.get_style().bg[gtk.STATE_NORMAL]
        self.textview_message.modify_base(gtk.STATE_INSENSITIVE, normal_bg)

    def get_next(self):
        return None


class FirstTimeWizard(SectionWizard):
    gsignal('finished', str)

    sections = [
        WelcomeStep,
        ProductionStep,
        ConversionStep,
        ConsumptionStep,
        LicenseStep,
        SummaryStep]

    def __init__(self, parent=None, admin=None):
        SectionWizard.__init__(self, parent)
        self._admin = admin
        self._save = save.WizardSaver(self)
        self._workerHeavenState = None
        self._last_worker = 0 # combo id last worker from step to step

        self.flow = Flow("default")

        self.worker_list = WorkerList()
        self.top_vbox.pack_start(self.worker_list, False, False)
        self.worker_list.connect('worker-selected',
                                 self.on_combobox_worker_changed)

    # SectionWizard

    def get_first_step(self):
        return WelcomeStep(self)

    def completed(self):
        configuration = self._save.getXML()
        self.emit('finished', configuration)

    def destroy(self):
        SectionWizard.destroy(self)
        del self._admin
        del self._save

    def run(self, interactive, workerHeavenState, main=True):
        self._workerHeavenState = workerHeavenState
        self.worker_list.set_worker_heaven_state(workerHeavenState)

        SectionWizard.run(self, interactive, main)

    def before_show_step(self, step):
        if step.has_worker:
            self.worker_list.show()
            self.worker_list.notify_selected()
        else:
            self.worker_list.hide()

        self._setup_worker(step, self.worker_list.get_worker())

    def show_next_step(self, step):
        self._setup_worker(step, self.worker_list.get_worker())
        SectionWizard.show_next_step(self, step)

    # Public API

    def check_elements(self, workerName, *elementNames):
        """
        Check if the given list of GStreamer elements exist on the given worker.

        @param workerName: name of the worker to check on
        @param elementNames: names of the elements to check

        @returns: a deferred returning a tuple of the missing elements
        """
        if not self._admin:
            self.debug('No admin connected, not checking presence of elements')
            return

        asked = sets.Set(elementNames)
        def _checkElementsCallback(existing, workerName):
            existing = sets.Set(existing)
            self.block_next(False)
            return tuple(asked.difference(existing))

        self.block_next(True)
        d = self._admin.checkElements(workerName, elementNames)
        d.addCallback(_checkElementsCallback, workerName)
        return d

    def require_elements(self, workerName, *elementNames):
        """
        Require that the given list of GStreamer elements exists on the
        given worker. If the elements do not exist, an error message is
        posted and the next button remains blocked.

        @param workerName: name of the worker to check on
        @param elementNames: names of the elements to check
        """
        if not self._admin:
            self.debug('No admin connected, not checking presence of elements')
            return

        self.debug('requiring elements %r' % (elementNames,))
        def got_missing_elements(elements, workerName):
            if elements:
                self.warning('elements %r do not exist' % (elements,))
                f = ngettext("Worker '%s' is missing GStreamer element '%s'.",
                    "Worker '%s' is missing GStreamer elements '%s'.",
                    len(elements))
                message = messages.Error(T_(f, workerName,
                    "', '".join(elements)))
                message.add(T_(N_("\n"
                    "Please install the necessary GStreamer plug-ins that "
                    "provide these elements and restart the worker.")))
                message.add(T_(N_("\n\n"
                    "You will not be able to go forward using this worker.")))
                self.block_next(True)
                message.id = 'element' + '-'.join(elementNames)
                self.add_msg(message)
            return elements

        d = self.check_elements(workerName, *elementNames)
        d.addCallback(got_missing_elements, workerName)

        return d

    def check_import(self, workerName, moduleName):
        """
        Check if the given module can be imported.

        @param workerName:  name of the worker to check on
        @param moduleName:  name of the module to import

        @returns: a deferred returning None or Failure.
        """
        if not self._admin:
            self.debug('No admin connected, not checking presence of elements')
            return

        d = self._admin.checkImport(workerName, moduleName)
        return d


    def require_import(self, workerName, moduleName, projectName=None,
                       projectURL=None):
        """
        Require that the given module can be imported on the given worker.
        If the module cannot be imported, an error message is
        posted and the next button remains blocked.

        @param workerName:  name of the worker to check on
        @param moduleName:  name of the module to import
        @param projectName: name of the module to import
        @param projectURL:  URL of the project
        """
        if not self._admin:
            self.debug('No admin connected, not checking presence of elements')
            return

        self.debug('requiring module %s' % moduleName)
        def _checkImportErrback(failure):
            self.warning('could not import %s', moduleName)
            message = messages.Error(T_(N_(
                "Worker '%s' cannot import module '%s'."),
                workerName, moduleName))
            if projectName:
                message.add(T_(N_("\n"
                    "This module is part of '%s'."), projectName))
            if projectURL:
                message.add(T_(N_("\n"
                    "The project's homepage is %s"), projectURL))
            message.add(T_(N_("\n\n"
                "You will not be able to go forward using this worker.")))
            self.block_next(True)
            message.id = 'module-%s' % moduleName
            self.add_msg(message)

        d = self.check_import(workerName, moduleName)
        d.addErrback(_checkImportErrback)
        return d

    # FIXME: maybe add id here for return messages ?
    def run_in_worker(self, worker, module, function, *args, **kwargs):
        """
        Run the given function and arguments on the selected worker.

        @param worker:
        @param module:
        @param function:
        @returns: L{twisted.internet.defer.Deferred}
        """
        self.debug('run_in_worker(module=%r, function=%r)' % (module, function))
        admin = self._admin
        if not admin:
            self.warning('skipping run_in_worker, no admin')
            return defer.fail(errors.FlumotionError('no admin'))

        if not worker:
            self.warning('skipping run_in_worker, no worker')
            return defer.fail(errors.FlumotionError('no worker'))

        d = admin.workerRun(worker, module, function, *args, **kwargs)

        def callback(result):
            self.debug('run_in_worker callbacked a result')
            self.clear_msg(function)

            if not isinstance(result, messages.Result):
                msg = messages.Error(T_(
                    N_("Internal error: could not run check code on worker.")),
                    debug=('function %r returned a non-Result %r'
                           % (function, result)))
                self.add_msg(msg)
                raise errors.RemoteRunError(function, 'Internal error.')

            for m in result.messages:
                self.debug('showing msg %r' % m)
                self.add_msg(m)

            if result.failed:
                self.debug('... that failed')
                raise errors.RemoteRunFailure(function, 'Result failed')
            self.debug('... that succeeded')
            return result.value

        def errback(failure):
            self.debug('run_in_worker errbacked, showing error msg')
            if failure.check(errors.RemoteRunError):
                debug = failure.value
            else:
                debug = "Failure while running %s.%s:\n%s" % (
                    module, function, failure.getTraceback())

            msg = messages.Error(T_(
                N_("Internal error: could not run check code on worker.")),
                debug=debug)
            self.add_msg(msg)
            raise errors.RemoteRunError(function, 'Internal error.')

        d.addErrback(errback)
        d.addCallback(callback)
        return d

    # Private

    def _setup_worker(self, step, worker):
        # get name of active worker
        self.debug('%r setting worker to %s' % (step, worker))
        step.worker = worker

    def _set_worker_from_step(self, step):
        if not hasattr(step, 'worker'):
            return

        model = self.combobox_worker.get_model()
        current_text = step.worker
        for row in model:
            text = model.get(row.iter, 0)[0]
            if current_text == text:
                self.combobox_worker.set_active_iter(row.iter)
                break

    # Callbacks

    def on_combobox_worker_changed(self, combobox, worker):
        self.debug('combobox_worker_changed, worker %r' % worker)
        if worker:
            self.clear_msg('worker-error')
            self._last_worker = worker
            if self._current_step:
                self._setup_worker(self._current_step, worker)
                self.debug('calling %r.worker_changed' % self._current_step)
                self._current_step.worker_changed()
        else:
            msg = messages.Error(T_(
                    N_('All workers have logged out.\n'
                    'Make sure your Flumotion network is running '
                    'properly and try again.')),
                id='worker-error')
            self.add_msg(msg)

