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
from flumotion.common.messages import N_, ngettext
from flumotion.common.python import sorted, any
from flumotion.configure import configure
from flumotion.wizard.step import WizardStep, WizardSection
from flumotion.wizard.enums import AudioDevice, EncodingAudio, \
     EncodingFormat, EncodingVideo, LicenseType, RotateSize, \
     RotateTime, SoundcardBitdepth, SoundcardChannels, SoundcardSystem, \
     SoundcardAlsaDevice, SoundcardOSSDevice, SoundcardSamplerate, \
     AudioTestSamplerate, VideoDevice, VideoTestFormat, VideoTestPattern
from flumotion.wizard.models import AudioProducer, VideoProducer, \
    AudioEncoder, VideoEncoder, Muxer

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


class AudioSourceStep(WizardStep):
    def __init__(self, wizard, model):
        self.model = model
        WizardStep.__init__(self, wizard)


class VideoSourceStep(WizardStep):
    section = 'Production'
    icon = 'widget_doc.png'

    def __init__(self, wizard, model):
        self.model = model
        WizardStep.__init__(self, wizard)

    def get_next(self):
        return OverlayStep(self.wizard, self.model)

    def get_state(self):
        options = WizardStep.get_state(self)
        options['width'] = int(options['width'])
        options['height'] = int(options['height'])
        return options


class VideoEncoderStep(WizardStep):
    section = 'Conversion'

    def __init__(self, wizard, model):
        self.model = model
        WizardStep.__init__(self, wizard)


class AudioEncoderStep(WizardStep):
    glade_file = 'wizard_audio_encoder.glade'
    section = 'Conversion'

    def __init__(self, wizard, model):
        self.model = model
        WizardStep.__init__(self, wizard)

    def get_next(self):
        return None


class WelcomeStep(WizardSection):
    glade_file = 'wizard_welcome.glade'
    section = 'Welcome'
    icon = 'wizard.png'
    has_worker = False

    def before_show(self):
        self.textview_message.realize()
        normal_bg = self.textview_message.get_style().bg[gtk.STATE_NORMAL]
        self.textview_message.modify_base(gtk.STATE_INSENSITIVE, normal_bg)

    def get_next(self):
        return None


class ProductionStep(WizardSection):
    glade_file = 'wizard_source.glade'
    name = 'Source'
    section = 'Production'
    icon = 'source.png'

    def __init__(self, wizard):
        WizardSection.__init__(self, wizard)
        self._audio_producer = None
        self._video_producer = None
        # FIXME: Why isn't setup() called for WizardSections?
        self._setup()

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

    in_setup = False

    def setup(self):
        self.in_setup = True
        self.combobox_device.set_list(('/dev/video0',
                                       '/dev/video1',
                                       '/dev/video2',
                                       '/dev/video3'))
        self.in_setup = False

    def on_combobox_device_changed(self, combo):
        self.run_checks()

    def worker_changed(self):
        self.clear_combos()
        self.run_checks()

    def clear_combos(self):
        self.combobox_tvnorm.clear()
        self.combobox_tvnorm.set_sensitive(False)
        self.combobox_source.clear()
        self.combobox_source.set_sensitive(False)

    def run_checks(self):
        if self.in_setup:
            yield None

        self.wizard.block_next(True)

        device = self.combobox_device.get_string()
        assert device
        d = self.workerRun('flumotion.worker.checks.video', 'checkTVCard',
                           device, id='tvcard-check')
        yield d
        try:
            value = d.value()
            if not value:
                yield None

            deviceName, channels, norms = value
            self.clear_msg('tvcard-check')
            self.wizard.block_next(False)
            self.combobox_tvnorm.set_list(norms)
            self.combobox_tvnorm.set_sensitive(True)
            self.combobox_source.set_list(channels)
            self.combobox_source.set_sensitive(True)
        except errors.RemoteRunFailure, e:
            pass
    run_checks = defer_generator_method(run_checks)

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


class FireWireStep(VideoSourceStep):
    name = 'Firewire'
    glade_file = 'wizard_firewire.glade'
    component_type = 'firewire'
    icon = 'firewire.png'
    width_corrections = ['none', 'pad', 'stretch']

    # options detected from the device:
    dims = None
    factors = (1, 2, 3, 4, 6, 8)
    input_heights = None
    input_widths = None
    par = None

    # these are instance state variables:
    is_square = None
    factor_i = None             # index into self.factors
    width_correction = None     # currently chosen item from width_corrections

    def set_sensitive(self, is_sensitive):
        self.vbox_controls.set_sensitive(is_sensitive)
        self.wizard.block_next(not is_sensitive)

    def on_update_output_format(self, *args):
        # update label_camera_settings
        standard = 'Unknown'
        aspect = 'Unknown'
        h = self.dims[1]
        if h == 576:
            standard = 'PAL'
        elif h == 480:
            standard = 'NTSC'
        else:
            self.warning('Unknown capture standard for height %d' % h)

        nom = self.par[0]
        den = self.par[1]
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
        self.factor_i = self.combobox_scaled_height.get_active()
        self.is_square = self.checkbutton_square_pixels.get_active()

        self.width_correction = None
        for i in self.width_corrections:
            if getattr(self,'radiobutton_width_'+i).get_active():
                self.width_correction = i
                break
        assert self.width_correction

        self.update_output_format()

    def _get_width_height(self):
        # returns dict with sw, sh, ow, oh
        # which are scaled width and height, and output width and height
        sh = self.input_heights[self.factor_i]
        sw = self.input_widths[self.factor_i]
        par = 1. * self.par[0] / self.par[1]

        if self.is_square:
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
        if self.width_correction == 'pad':
            ow = sw + (8 - (sw % 8)) % 8
        elif self.width_correction == 'stretch':
            ow = sw + (8 - (sw % 8)) % 8
            sw = ow

        return dict(sw=sw,sh=sh,ow=ow,oh=oh)

    def update_output_format(self):
        d = self._get_width_height()
        num, den = 1, 1
        if not self.is_square:
            num, den = self.par[0], self.par[1]

        msg = _('%dx%d, %d/%d pixel aspect ratio') % (
                   d['ow'], d['oh'], num, den)
        self.label_output_format.set_markup(msg)

    def get_state(self):
        options = {} # VideoSourceStep.get_state(self)
        d = self._get_width_height()
        options['height'] = d['oh']
        options['scaled-width'] = d['sw']
        options['width'] = d['ow']
        options['is-square'] = self.is_square
        options['framerate'] = \
            _fraction_from_float(self.spinbutton_framerate.get_value(), 2)
        return options

    def worker_changed(self):
        self.run_checks()

    def run_checks(self):
        self.set_sensitive(False)
        msg = messages.Info(T_(N_('Checking for Firewire device...')),
            id='firewire-check')
        self.add_msg(msg)
        d = self.workerRun('flumotion.worker.checks.video', 'check1394',
            id='firewire-check')
        yield d
        try:
            options = d.value()
            self.clear_msg('firewire-check')
            self.dims = (options['width'], options['height'])
            self.par = options['par']
            self.input_heights = [self.dims[1]/i for i in self.factors]
            self.input_widths = [self.dims[0]/i for i in self.factors]
            store = gtk.ListStore(str)
            for i in self.input_heights:
                store.set(store.append(), 0, '%d pixels' % i)
            self.combobox_scaled_height.set_model(store)
            self.combobox_scaled_height.set_active(1)
            self.set_sensitive(True)
            self.on_update_output_format()
        except errors.RemoteRunFailure:
            pass
    run_checks = defer_generator_method(run_checks)


class FireWireAudioStep(AudioSourceStep):
    name = 'Firewire audio'
    glade_file = 'wizard_firewire.glade'
    component_type = 'firewire'
    icon = 'firewire.png'
    width_corrections = ['none', 'pad', 'stretch']
    section = 'Production'

    # options detected from the device:
    dims = None
    factors = (1, 2, 3, 4, 6, 8)
    input_heights = None
    input_widths = None
    par = None

    # these are instance state variables:
    is_square = None
    factor_i = None             # index into self.factors
    width_correction = None     # currently chosen item from width_corrections

    def setup(self):
        self.frame_scaling.hide()
        self.frame_width_correction.hide()
        self.frame_capture.hide()
        self.frame_output_format.hide()

    def set_sensitive(self, is_sensitive):
        self.vbox_controls.set_sensitive(is_sensitive)
        self.wizard.block_next(not is_sensitive)

    def on_update_output_format(self, *args):
        # update label_camera_settings
        standard = 'Unknown'
        aspect = 'Unknown'
        h = self.dims[1]
        if h == 576:
            standard = 'PAL'
        elif h == 480:
            standard = 'NTSC'
        else:
            self.warning('Unknown capture standard for height %d' % h)

        nom = self.par[0]
        den = self.par[1]
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
        self.factor_i = self.combobox_scaled_height.get_active()
        self.is_square = self.checkbutton_square_pixels.get_active()

        self.width_correction = None
        for i in self.width_corrections:
            if getattr(self,'radiobutton_width_'+i).get_active():
                self.width_correction = i
                break
        assert self.width_correction

        self.update_output_format()

    def _get_width_height(self):
        # returns dict with sw, sh, ow, oh
        # which are scaled width and height, and output width and height
        sh = self.input_heights[self.factor_i]
        sw = self.input_widths[self.factor_i]
        par = 1. * self.par[0] / self.par[1]

        if self.is_square:
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
        if self.width_correction == 'pad':
            ow = sw + (8 - (sw % 8)) % 8
        elif self.width_correction == 'stretch':
            ow = sw + (8 - (sw % 8)) % 8
            sw = ow

        return dict(sw=sw,sh=sh,ow=ow,oh=oh)

    def update_output_format(self):
        d = self._get_width_height()
        num, den = 1, 1
        if not self.is_square:
            num, den = self.par[0], self.par[1]

        msg = _('%dx%d, %d/%d pixel aspect ratio') % (
                   d['ow'], d['oh'], num, den)
        self.label_output_format.set_markup(msg)

    def get_state(self):
        options = {} # VideoSourceStep.get_state(self)
        d = self._get_width_height()
        options['height'] = d['oh']
        options['scaled-width'] = d['sw']
        options['width'] = d['ow']
        options['is-square'] = self.is_square
        options['framerate'] = \
            _fraction_from_float(self.spinbutton_framerate.get_value(), 2)
        return options

    def worker_changed(self):
        self.run_checks()

    def run_checks(self):
        self.set_sensitive(False)
        msg = messages.Info(T_(N_('Checking for Firewire device...')),
            id='firewire-check')
        self.add_msg(msg)
        d = self.workerRun('flumotion.worker.checks.video', 'check1394',
            id='firewire-check')
        def firewireCheckDone(options):
            self.clear_msg('firewire-check')
            self.dims = (options['width'], options['height'])
            self.par = options['par']
            self.input_heights = [self.dims[1]/i for i in self.factors]
            self.input_widths = [self.dims[0]/i for i in self.factors]
            store = gtk.ListStore(str)
            for i in self.input_heights:
                store.set(store.append(), 0, '%d pixels' % i)
            self.combobox_scaled_height.set_model(store)
            self.combobox_scaled_height.set_active(1)
            self.set_sensitive(True)
            self.on_update_output_format()
        d.addCallback(firewireCheckDone)
        return d

    def get_next(self):
        return None


class WebcamStep(VideoSourceStep):
    name = 'Webcam'
    glade_file = 'wizard_webcam.glade'
    component_type = 'video4linux'
    icon = 'webcam.png'

    in_setup = False

    # _sizes is probed, not set from the UI
    _sizes = None
    _factoryName = None

    def setup(self):
        self.in_setup = True
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
        self.in_setup = False

    def on_combobox_device_changed(self, combo):
        self.run_checks()

    def on_combobox_size_changed(self, combo):
        # check for custom
        i = self.combobox_size.get_active_iter()
        if i:
            w, h = self.combobox_size.get_model().get(i, 1, 2)
            store = gtk.ListStore(str, object)
            for d in self._sizes[(w,h)]:
                num, denom = d['framerate']
                store.append(['%.2f fps' % (1.0*num/denom), 1])
            # add custom
            self.combobox_framerate.set_model(store)
            self.combobox_framerate.set_active(0)

    def worker_changed(self):
        self.clear()
        self.run_checks()

    def clear(self):
        self.combobox_size.set_sensitive(False)
        self.combobox_framerate.set_sensitive(False)
        self.label_name.set_label("")
        self.wizard.block_next(True)

    def run_checks(self):
        if self.in_setup:
            yield None

        self.wizard.block_next(True)

        device = self.combobox_device.get_string()
        msg = messages.Info(T_(
                N_("Probing webcam, this can take a while...")),
            id='webcam-check')
        self.add_msg(msg)
        d = self.workerRun('flumotion.worker.checks.video', 'checkWebcam',
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
            self.clear_msg('webcam-check')
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
            self.clear()
    run_checks = defer_generator_method (run_checks)

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


class TestVideoSourceStep(VideoSourceStep):
    name = 'Test Video Source'
    glade_file = 'wizard_testsource.glade'
    component_type = 'videotestsrc'
    icon = 'testsource.png'

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

    def on_spinbutton_height_value_changed(self, spinbutton):
        self.model.height = spinbutton.get_value()

    def on_spinbutton_width_value_changed(self, spinbutton):
        self.model.width = spinbutton.get_value()


class OverlayStep(WizardStep):
    name = 'Overlay'
    glade_file = 'wizard_overlay.glade'
    section = 'Production'
    component_type = 'overlay'
    icon = 'overlay.png'

    can_overlay = True

    def __init__(self, wizard, video_producer):
        WizardStep.__init__(self, wizard)
        self._video_producer = video_producer

    # Wizard Step

    def get_state(self):
        options = WizardStep.get_state(self)
        if self.checkbutton_show_logo.get_active():
            options['show-logo'] = True

        if self.checkbutton_show_text.get_active():
            options['text'] = self.entry_text.get_text()

        options['can-overlay'] = self.can_overlay

        options['width'] = self._video_producer.width
        options['height'] = self._video_producer.height

        return options

    def get_next(self):
        if self.wizard.get_step_option('Source', 'has-audio'):
            return self.wizard['Source'].get_audio_step()

        return None

    def worker_changed(self):
        self._worker_changed_010()

    # Private API

    def _worker_changed_010(self):
        self.can_overlay = False
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
            self.add_msg(message)
        else:
            self.clear_msg('overlay')

        # now check import
        d = self.wizard.check_import(self.worker, 'PIL')
        yield d
        try:
            d.value()
            self.can_overlay = True
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
            self.add_msg(message)
            self.can_overlay = False

    _worker_changed_010 = defer_generator_method(_worker_changed_010)

    def on_checkbutton_show_text_toggled(self, button):
        self.entry_text.set_sensitive(button.get_active())


class SoundcardStep(AudioSourceStep):
    name = 'Soundcard'
    glade_file = 'wizard_soundcard.glade'
    section = 'Production'
    component_type = 'osssrc'
    icon = 'soundcard.png'

    block_update = False

    def on_combobox_system_changed(self, combo):
        if not self.block_update:
            self.update_devices()
            self.update_inputs()

    def on_combobox_device_changed(self, combo):
        self.update_inputs()

    def on_combobox_channels_changed(self, combo):
        # FIXME: make it so that the number of channels can be changed
        # and the check gets executed with the new number
        # self.update_inputs()
        pass

    def worker_changed(self):
        self.clear_combos()
        self.update_devices()
        self.update_inputs()

    def setup(self):
        # block updates, because populating a shown combobox will of course
        # trigger the callback
        self.block_update = True
        self.combobox_system.set_enum(SoundcardSystem)
        self.block_update = False

    def clear_combos(self):
        self.combobox_input.clear()
        self.combobox_input.set_sensitive(False)
        self.combobox_channels.clear()
        self.combobox_channels.set_sensitive(False)
        self.combobox_samplerate.clear()
        self.combobox_samplerate.set_sensitive(False)
        self.combobox_bitdepth.clear()
        self.combobox_bitdepth.set_sensitive(False)

    def update_devices(self):
        self.block_update = True
        enum = self.combobox_system.get_enum()
        if enum == SoundcardSystem.Alsa:
            self.combobox_device.set_enum(SoundcardAlsaDevice)
        elif enum == SoundcardSystem.OSS:
            self.combobox_device.set_enum(SoundcardOSSDevice)
        else:
            raise AssertionError
        self.block_update = False

    def update_inputs(self):
        if self.block_update:
            return
        self.wizard.block_next(True)

        enum = self.combobox_system.get_enum()
        device = self.combobox_device.get_string()
        e = self.combobox_channels.get_enum()
        channels = 2
        if e: channels = e.intvalue
        d = self.workerRun('flumotion.worker.checks.audio', 'checkMixerTracks',
                           enum.element, device, channels, id='soundcard-check')
        def soundcardCheckComplete((deviceName, tracks)):
            self.clear_msg('soundcard-check')
            self.wizard.block_next(False)
            self.label_devicename.set_label(deviceName)
            self.block_update = True
            self.combobox_channels.set_enum(SoundcardChannels)
            self.combobox_channels.set_sensitive(True)
            self.combobox_samplerate.set_enum(SoundcardSamplerate)
            self.combobox_samplerate.set_sensitive(True)
            self.combobox_bitdepth.set_enum(SoundcardBitdepth)
            self.combobox_bitdepth.set_sensitive(True)
            self.block_update = False

            self.combobox_input.set_list(tracks)
            self.combobox_input.set_sensitive(True)

        d.addCallback(soundcardCheckComplete)
        # FIXME: when probing failed, do
        # self.clear_combos()
        return d

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


class TestAudioSourceStep(AudioSourceStep):
    name = 'Test Audio Source'
    glade_file = 'wizard_audiotest.glade'
    section = 'Production'
    icon = 'soundcard.png'

    def worker_changed(self):
        self.wizard.require_elements(self.worker, 'audiotestsrc')

    def before_show(self):
        self.combobox_samplerate.set_enum(AudioTestSamplerate)
        self.combobox_samplerate.set_sensitive(True)

    def get_state(self):
        return dict(frequency=int(self.spinbutton_freq.get_value()),
                    volume=float(self.spinbutton_volume.get_value()),
                    rate=self.combobox_samplerate.get_int())

    def get_next(self):
        return None


class ConversionStep(WizardSection):
    glade_file = 'wizard_encoding.glade'
    name = 'Encoding'
    section = 'Conversion'

    def __init__(self, wizard):
        WizardSection.__init__(self, wizard)
        self._muxer = Muxer()
        self._audio_encoder = AudioEncoder()
        self._video_encoder = VideoEncoder()
        self.wizard.flow.addComponent(self._muxer)

    def before_show(self):
        self.combobox_format.set_enum(EncodingFormat)
        self.combobox_audio.set_enum(EncodingAudio)
        self.combobox_video.set_enum(EncodingVideo)

        flow = self.wizard.flow
        production = self.wizard['Source']

        audio_producer = production.get_audio_producer()
        if audio_producer and self._audio_encoder not in flow:
            flow.addComponent(self._audio_encoder)

        video_producer = production.get_video_producer()
        if video_producer and self._video_encoder not in flow:
            flow.addComponent(self._video_encoder)

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

    def _verify(self):
        # XXX: isn't there a better way of doing this, like blocking
        #      the signal

        format = self.combobox_format.get_active()
        if format == EncodingFormat.Ogg:
            self.debug('running Ogg checks')
            d = self.wizard.require_elements(self.worker, 'oggmux')

            yield d
            d = self.workerRun('flumotion.component.muxers.checks', 'checkOgg')

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

    def activated(self):
        self._verify()

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


class TheoraStep(VideoEncoderStep):
    name = 'Theora encoder'
    sidebar_name = 'Theora'
    glade_file = 'wizard_theora.glade'
    component_type = 'theora'
    icon = 'xiphfish.png'

    def setup(self):
        # XXX: move to glade file
        self.spinbutton_bitrate.set_range(0, 4000)
        self.spinbutton_bitrate.set_value(400)
        self.spinbutton_quality.set_range(0, 63)
        self.spinbutton_quality.set_value(16)

    def worker_changed(self):
        d = self.wizard.require_elements(self.worker, 'theoraenc')

        yield d

        d = self.workerRun('flumotion.worker.checks.encoder', 'checkTheora')

        yield d
    worker_changed = defer_generator_method(worker_changed)

    # This is bound to both radiobutton_bitrate and radiobutton_quality
    def on_radiobutton_toggled(self, button):
        self.spinbutton_bitrate.set_sensitive(
            self.radiobutton_bitrate.get_active())
        self.spinbutton_quality.set_sensitive(
            self.radiobutton_quality.get_active())

    def get_next(self):
        return self.wizard['Encoding'].get_audio_page()

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


class SmokeStep(VideoEncoderStep):
    name = 'Smoke encoder'
    sidebar_name = 'Smoke'
    glade_file = 'wizard_smoke.glade'
    section = 'Conversion'
    component_type = 'smoke'

    def worker_changed(self):
        self.wizard.require_elements(self.worker, 'smokeenc')

    def get_next(self):
        return self.wizard['Encoding'].get_audio_page()

    def get_state(self):
        options = VideoEncoderStep.get_state(self)
        options['qmin'] = int(options['qmin'])
        options['qmax'] = int(options['qmax'])
        options['threshold'] = int(options['threshold'])
        options['keyframe'] = int(options['keyframe'])
        return options


class JPEGStep(VideoEncoderStep):
    name = 'JPEG encoder'
    sidebar_name = 'JPEG'
    glade_file = 'wizard_jpeg.glade'
    section = 'Conversion'
    component_type = 'jpeg'

    def worker_changed(self):
        self.wizard.require_elements(self.worker, 'jpegenc')

    def get_next(self):
        return self.wizard['Encoding'].get_audio_page()

    def get_state(self):
        options = VideoEncoderStep.get_state(self)
        options['quality'] = int(options['quality'])
        options['framerate'] = _fraction_from_float(options['framerate'], 2)
        return options


# Worker?
class VorbisStep(AudioEncoderStep):
    glade_file = 'wizard_vorbis.glade'
    name = 'Vorbis encoder'
    sidebar_name = 'Vorbis'
    component_type = 'vorbis'
    icon = 'xiphfish.png'

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
        d = self.workerRun('flumotion.worker.checks.encoder', 'checkVorbis')

        yield d
    worker_changed = defer_generator_method(worker_changed)

    # This is bound to both radiobutton_bitrate and radiobutton_quality
    def on_radiobutton_toggled(self, button):
        self.spinbutton_bitrate.set_sensitive(
            self.radiobutton_bitrate.get_active())
        self.spinbutton_quality.set_sensitive(
            self.radiobutton_quality.get_active())

    def get_state(self):
        options = {}
        if self.radiobutton_bitrate:
            options['bitrate'] = int(self.spinbutton_bitrate.get_value()) * 1000
        elif self.radiobutton_quality:
            options['quality'] = self.spinbutton_quality.get_value()
        return options


class SpeexStep(AudioEncoderStep):
    name = 'Speex encoder'
    sidebar_name = 'Speex'
    component_type = 'speex'
    icon = 'xiphfish.png'

    def worker_changed(self):
        self.wizard.require_elements(self.worker, 'speexenc')

    def setup(self):
        # Should be 2150 instead of 3 -> 3000
        self.spinbutton_bitrate.set_range(3, 30)
        self.spinbutton_bitrate.set_value(11)

    def get_state(self):
        options = AudioEncoderStep.get_state(self)
        options['bitrate'] = int(self.spinbutton_bitrate.get_value()) * 1000
        return options


class ConsumptionStep(WizardSection):
    name = 'Consumption'
    glade_file = 'wizard_consumption.glade'
    section = 'Consumption'
    icon = 'consumption.png'
    has_worker = False

    def setup(self):
        pass

    def on_checkbutton_http_toggled(self, button):
        value = self.checkbutton_http.get_active()
        self.checkbutton_http_audio_video.set_sensitive(value)
        self.checkbutton_http_audio.set_sensitive(value)
        self.checkbutton_http_video.set_sensitive(value)

        self.verify()

    def on_checkbutton_disk_toggled(self, button):
        value = self.checkbutton_disk.get_active()
        self.checkbutton_disk_audio_video.set_sensitive(value)
        self.checkbutton_disk_audio.set_sensitive(value)
        self.checkbutton_disk_video.set_sensitive(value)

        self.verify()

    def on_checkbutton_shout2_toggled(self, button):
        value = self.checkbutton_shout2.get_active()
        self.checkbutton_shout2_audio_video.set_sensitive(value)
        self.checkbutton_shout2_audio.set_sensitive(value)
        self.checkbutton_shout2_video.set_sensitive(value)

        self.verify()

    def on_secondary_checkbutton_toggled(self, button):
        self.verify()

    def verify(self):
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

    def activated(self):
        has_audio = self.wizard.get_step_option('Source', 'has-audio')
        has_video = self.wizard.get_step_option('Source', 'has-video')
        has_both = has_audio and has_video

        # Most of the options only makes sense if we selected audio
        # and video in the first page. If we didn't just hide them
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
            if has_audio and has_video and audio_video.get_active():
                items.append("%s (audio & video)" % (name,))
            if has_audio and audio.get_active():
                items.append("%s (audio only)" % (name,))
            if has_video and video.get_active():
                items.append("%s (video only)" % (name,))

        assert items

        if step:
            stepname = step.get_name()
            if stepname in items and items[-1] != stepname:
                step = items[items.index(stepname)+1]
            else:
                step = None
        else:
            step = items[0]
        return step


# XXX: If audio codec is speex, disable java applet option
class HTTPStep(WizardStep):
    glade_file = 'wizard_http.glade'
    section = 'Consumption'
    component_type = 'http-streamer'

    def worker_changed(self):
        def got_missing(missing):
            self._missing_elements = bool(missing)
            self.verify()
        self._missing_elements = True
        d = self.wizard.require_elements(self.worker, 'multifdsink')
        d.addCallback(got_missing)

    def verify(self):
        self.spinbutton_client_limit.set_sensitive(
            self.checkbutton_client_limit.get_active())
        self.spinbutton_bandwidth_limit.set_sensitive(
            self.checkbutton_bandwidth_limit.get_active())
        self.wizard.block_next(self._missing_elements or
                               self.entry_mount_point.get_text() == '')

    def activated(self):
        self.verify()

    def setup(self):
        self.spinbutton_port.set_value(self.port)

    def get_next(self):
        return self.wizard['Consumption'].get_next(self)

    def get_state(self):
        options = WizardStep.get_state(self)

        options['bandwidth-limit'] = int(options['bandwidth-limit'] * 1e6)
        options['client-limit'] = int(options['client-limit'])

        if not self.checkbutton_bandwidth_limit.get_active():
            del options['bandwidth-limit']
        if not self.checkbutton_client_limit.get_active():
            del options['client-limit']

        options['port'] = int(options['port'])

        return options

    def on_entry_mount_point_changed(self, entry):
        self.verify()

    def on_checkbutton_client_limit_toggled(self, *args):
        self.verify()

    def on_checkbutton_bandwidth_limit_toggled(self, *args):
        self.verify()


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


class DiskStep(WizardStep):
    glade_file = 'wizard_disk.glade'
    section = 'Consumption'
    icon = 'kcmdevices.png'

    def setup(self):
        self.combobox_time_list.set_enum(RotateTime)
        self.combobox_size_list.set_enum(RotateSize)
        self.radiobutton_has_time.set_active(True)
        self.spinbutton_time.set_value(12)
        self.combobox_time_list.set_active(RotateTime.Hours)
        self.checkbutton_record_at_startup.set_active(True)

    # This is bound to both radiobutton_has_size and radiobutton_has_time
    def on_radiobutton_rotate_toggled(self, button):
        self.update_radio()

    def update_radio(self):
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

    def on_checkbutton_rotate_toggled(self, button):
        if self.checkbutton_rotate.get_active():
            self.radiobutton_has_size.set_sensitive(True)
            self.radiobutton_has_time.set_sensitive(True)
            self.update_radio()
        else:
            self.radiobutton_has_size.set_sensitive(False)
            self.spinbutton_size.set_sensitive(False)
            self.combobox_size_list.set_sensitive(False)
            self.radiobutton_has_time.set_sensitive(False)
            self.spinbutton_time.set_sensitive(False)
            self.combobox_time_list.set_sensitive(False)

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
        return self.wizard['Consumption'].get_next(self)


class DiskBothStep(DiskStep):
    name = 'Disk (audio & video)'
    sidebar_name = 'Disk audio/video'


class DiskAudioStep(DiskStep):
    name = 'Disk (audio only)'
    sidebar_name = 'Disk audio'


class DiskVideoStep(DiskStep):
    name = 'Disk (video only)'
    sidebar_name = 'Disk video'


class Shout2Step(WizardStep):
    glade_file = 'wizard_shout2.glade'
    section = 'Consumption'
    component_type = 'shout2'

    def before_show(self):
        self.wizard.check_elements(self.worker, 'shout2send')

    def get_next(self):
        return self.wizard['Consumption'].get_next(self)

    def get_state(self):
        options = WizardStep.get_state(self)

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


class LicenseStep(WizardSection):
    name = "Content License"
    glade_file = "wizard_license.glade"
    section = 'License'
    icon = 'licenses.png'
    has_worker = False

    def setup(self):
        self.combobox_license.set_enum(LicenseType)

    def on_checkbutton_set_license_toggled(self, button):
        self.combobox_license.set_sensitive(button.get_active())

    def get_next(self):
        return None


class SummaryStep(WizardSection):
    section = "Summary"
    glade_file = "wizard_summary.glade"
    icon = 'summary.png'
    has_worker = False
    last_step = True
    def before_show(self):
        self.textview_message.realize()
        normal_bg = self.textview_message.get_style().bg[gtk.STATE_NORMAL]
        self.textview_message.modify_base(gtk.STATE_INSENSITIVE, normal_bg)
    def get_next(self):
        return None
