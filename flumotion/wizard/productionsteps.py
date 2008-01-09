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
import math

import gtk
from twisted.internet.defer import Deferred

from flumotion.common import errors, messages
from flumotion.common.errors import NoBundleError
from flumotion.common.messages import N_
from flumotion.common.python import sorted
from flumotion.wizard.basesteps import WorkerWizardStep, \
    AudioSourceStep, VideoSourceStep
from flumotion.wizard.enums import SoundcardSystem
from flumotion.wizard.models import AudioProducer, VideoProducer

T_ = messages.gettexter('flumotion')
_ = gettext.gettext

# pychecker doesn't like the auto-generated widget attrs
# or the extra args we name in callbacks
__pychecker__ = 'no-classattr no-argsused'

# the denominator arg for all calls of this function was sniffed from
# the glade file's spinbutton adjustment


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
        @rtype: a L{VideoSourceStep} subclass
        """
        step_class = self._get_video_step_class()
        if isinstance(step_class, Deferred):
            return self._load_step(step_class, self._video_producer)

        return step_class(self.wizard, self._video_producer)

    def get_audio_step(self):
        """Return the audio step to be shown, given the currently
        selected values in this step
        @returns: audio step
        @rtype: a L{AudioSourceStep} subclass
        """
        step_class = self._get_audio_step_class()
        if isinstance(step_class, Deferred):
            return self._load_step(step_class, self._audio_producer)

        return step_class(self.wizard, self._audio_producer)

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

    def worker_changed(self):
        if self.audio.get_selected() not in ['audiotest-producer']:
            if not isinstance(self._get_audio_step_class(), WorkerWizardStep):
                self._audio_producer.worker = self.worker
        if self.video.get_selected() not in ['videotest-producer']:
            if not isinstance(self._get_video_step_class(), WorkerWizardStep):
                self._video_producer.worker = self.worker

    # Private API

    def _get_audio_step_class(self):
        source = self.audio.get_selected()
        if source == 'soundcard-producer':
            step_class = SoundcardStep
        elif source == 'firewire-producer':
            # Only show firewire audio if we're using firewire video
            if self.video.get_active() == 'firewire-producer':
                return
            step_class = FireWireAudioStep
        else:
            step_class = self._load_plugin(source)
        return step_class

    def _get_video_step_class(self):
        source = self.video.get_selected()
        if source == 'webcam-producer':
            step_class = WebcamStep
        elif source == 'tvcard-producer':
            step_class = TVCardStep
        elif source == 'firewire-producer':
            step_class = FireWireStep
        else:
            step_class = self._load_plugin(source)
        return step_class

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

        self.video.prefill([
            (_('Test video source'), 'videotest-producer'),
            (_('Web camera'), 'webcam-producer'),
            (_('TV card'), 'tvcard-producer'),
            (_('Firewire video'), 'firewire-producer')])
        self.audio.prefill([
            (_('Test audio source'), 'audiotest-producer'),
            (_('Sound card'), 'soundcard-producer'),
            (_('Firewire audio'), 'firewire-producer'),
            ])

    def _load_plugin(self, component_type):
        def got_factory(factory):
            plugin = factory(self.wizard)
            return plugin.get_production_step()

        def noBundle(failure):
            failure.trap(NoBundleError)

        d = self.wizard.get_wizard_entry(component_type)
        d.addCallback(got_factory)
        d.addErrback(noBundle)

        return d

    def _load_step(self, d, producer):
        def get_step_class(step_class):
            step = step_class(self.wizard, producer)
            if isinstance(step, WorkerWizardStep):
                step.worker = self.worker
                step.worker_changed()
            return step
        d.addCallback(get_step_class)
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




class WebcamStep(VideoSourceStep):
    name = _('Webcam')
    glade_file = 'wizard_webcam.glade'
    component_type = 'video4linux'
    icon = 'webcam.png'

    def __init__(self, wizard, model):
        VideoSourceStep.__init__(self, wizard, model)
        self._in_setup = False
        # _sizes is probed, not set from the UI
        self._sizes = None

    # WizardStep

    def setup(self):
        self._in_setup = True
        self.device.data_type = str
        self.framerate.data_type = object

        self.device.prefill(['/dev/video0',
                             '/dev/video1',
                             '/dev/video2',
                             '/dev/video3'])

        self.add_proxy(self.model.properties,['device'])

        self._in_setup = False

    def worker_changed(self):
        self._clear()
        self._run_checks()

    # Private

    def _clear(self):
        self.size.set_sensitive(False)
        self.framerate.set_sensitive(False)
        self.label_name.set_label("")
        self.wizard.block_next(True)

    def _run_checks(self):
        if self._in_setup:
            return None

        self.wizard.block_next(True)

        device = self.device.get_selected()
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
            self.model.properties.element_factory = factoryName
            self._populate_sizes(sizes)
            self.wizard.clear_msg('webcam-check')
            self.label_name.set_label(deviceName)
            self.wizard.block_next(False)
            self.size.set_sensitive(True)
            self.framerate.set_sensitive(True)

        d.addCallback(deviceFound)
        d.addErrback(errRemoteRunFailure)
        d.addErrback(errRemoteRunError)

    def _populate_sizes(self, sizes):
        # Set sizes before populating the values, since
        # it trigger size_changed which depends on this
        # to be set
        self._sizes = sizes

        values = []
        for w, h in sorted(sizes.keys(), reverse=True):
            values.append(['%d x %d' % (w, h), (w, h)])
        self.size.prefill(values)

    def _populate_framerates(self, size):
        values = []
        for d in self._sizes[size]:
            num, denom = d['framerate']
            values.append(('%.2f fps' % (1.0*num/denom), d))
        self.framerate.prefill(values)

    def _update_size(self):
        size = self.size.get_selected()
        if size:
            self._populate_framerates(size)
            width, height = size
        else:
            self.warning('something bad happened: no height/width selected?')
            width, height = 320, 240

        self.model.properties.width = width
        self.model.properties.height = height

    def _update_framerate(self):
        if self._in_setup:
            return None

        framerate = self.framerate.get_selected()
        if framerate:
            num, denom = framerate['framerate']
            mime = framerate['mime']
            format = framerate.get('format', None)
        else:
            self.warning('something bad happened: no framerate selected?')
            num, denom = 15, 2
            mime = 'video/x-raw-yuv'
            format = None

        self.model.properties.mime = mime
        self.model.properties.framerate = '%d/%d' % (num, denom)
        if format:
            self.model.properties.format = format

    # Callbacks

    def on_device_changed(self, combo):
        self._run_checks()

    def on_size_changed(self, combo):
        self._update_size()

    def on_framerate_changed(self, combo):
        self._update_framerate()


# note:
# v4l talks about "signal" (PAL/...) and "channel" (TV/Composite/...)
# and frequency
# gst talks about "norm" and "channel"
# and frequency
# apps (and flumotion) talk about "TV Norm" and "source",
# and channel (corresponding to frequency)
class TVCardStep(VideoSourceStep):
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

        self.device.data_type = str
        self.width.data_type = int
        self.height.data_type = int
        self.framerate.data_type = float

        self.device.prefill(['/dev/video0',
                             '/dev/video1',
                             '/dev/video2',
                             '/dev/video3'])

        self.add_proxy(self.model.properties,
                       ['device', 'height', 'width',
                        'framerate'])

        self._in_setup = False

    def worker_changed(self):
        self._clear_combos()
        self._run_checks()

    # Private

    def _clear_combos(self):
        self.tvnorm.clear()
        self.tvnorm.set_sensitive(False)
        self.source.clear()
        self.source.set_sensitive(False)

    def _run_checks(self):
        if self._in_setup:
            return None

        self.wizard.block_next(True)

        device = self.device.get_selected()
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
            self.tvnorm.prefill(norms)
            self.tvnorm.set_sensitive(True)
            self.source.prefill(channels)
            self.source.set_sensitive(True)

        d.addCallback(deviceFound)
        d.addErrback(errRemoteRunFailure)
        d.addErrback(errRemoteRunError)

    # Callbacks

    def on_device__changed(self, combo):
        self._run_checks()




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
    name = _('Soundcard')
    glade_file = 'wizard_soundcard.glade'
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
        self.input_track.data_type = str
        self.channels.data_type = int
        self.rate.data_type = int
        self.depth.data_type = int
        self.device.data_type = str
        self.source_element.data_type = str

        self.add_proxy(self.model.properties,
                       ['input_track',
                        'channels',
                        'rate',
                        'depth',
                        'device',
                        'source_element'])

        self.source_element.prefill(
            [(enum.nick, enum.element_name) for enum in SoundcardSystem])
        self.channels.prefill(CHANNELS)
        self.rate.prefill([(str(r), r) for r in SAMPLE_RATES])
        self.depth.prefill(BITDEPTHS)
        self._block_update = False

    def worker_changed(self):
        self._clear_combos()
        self._update_devices()
        self._update_inputs()

    def get_next(self):
        return None

    # Private

    def _clear_combos(self):
        self.input_track.clear()
        self.input_track.set_sensitive(False)
        self.channels.set_sensitive(False)
        self.rate.set_sensitive(False)
        self.depth.set_sensitive(False)

    def _update_devices(self):
        self._block_update = True
        self.device.clear()
        enum = self.source_element.get_selected()
        if enum == SoundcardSystem.Alsa.element_name:
            self.device.prefill(ALSA_DEVICES)
        elif enum == SoundcardSystem.OSS.element_name:
            self.device.prefill(OSS_DEVICES)
        else:
            raise AssertionError
        self._block_update = False

    def _update_inputs(self):
        if self._block_update:
            return
        self.wizard.block_next(True)

        device = self.device.get_selected()
        element_name = self.source_element.get_selected()
        channels = self.channels.get_selected() or 2
        assert device
        assert element_name
        assert channels
        msg = messages.Info(T_(
            N_("Probing soundcard, this can take a while...")),
                            id='soundcard-check')
        self.wizard.add_msg(msg)
        d = self.run_in_worker('flumotion.worker.checks.audio', 'checkMixerTracks',
                               element_name,
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
            self.channels.set_sensitive(True)
            self.rate.set_sensitive(True)
            self.depth.set_sensitive(True)
            self.input_track.prefill(tracks)
            self.input_track.set_sensitive(bool(tracks))
            self._block_update = False

        d.addCallback(soundcardCheckComplete)
        d.addErrback(checkFailed)

        return d

    # Callbacks

    def on_source_element__changed(self, combo):
        if not self._block_update:
            self._update_devices()
            self._update_inputs()

    def on_device__changed(self, combo):
        self._update_inputs()

    def on_channels__changed(self, combo):
        # FIXME: make it so that the number of channels can be changed
        # and the check gets executed with the new number
        # self.update_inputs()
        pass


class _FireWireCommon:
    glade_file = 'wizard_firewire.glade'
    component_type = 'firewire'
    icon = 'firewire.png'
    width_corrections = ['none', 'pad', 'stretch']

    def __init__(self):
        # options detected from the device:
        self._dims = None
        self._factors = [1, 2, 3, 4, 6, 8]
        self._input_heights = None
        self._input_widths = None
        self._par = None

        # these are instance state variables:
        self._factor_i = None             # index into self.factors
        self._width_correction = None     # currently chosen item from
                                          # width_corrections
        self.model.properties.is_square = False

    # WizardStep

    def worker_changed(self):
        self._run_checks()

    # Private

    def _set_sensitive(self, is_sensitive):
        self.vbox_controls.set_sensitive(is_sensitive)
        self.wizard.block_next(not is_sensitive)

    def _update_output_format(self):
        d = self._get_width_height()
        self.model.properties.is_square = (
            self.checkbutton_square_pixels.get_active())
        self.model.properties.width = d['ow']
        self.model.properties.height = d['oh']
        self.model.properties.scaled_width = d['sw']
        self.model.properties.framerate = self.spinbutton_framerate.get_value()
        num, den = 1, 1
        if not self.model.properties.is_square:
            num, den = self._par[0], self._par[1]

        msg = _('%dx%d, %d/%d pixel aspect ratio') % (
                   d['ow'], d['oh'], num, den)
        self.label_output_format.set_markup(msg)

    def _get_width_height(self):
        # returns dict with sw, sh, ow, oh
        # which are scaled width and height, and output width and height
        sh = self._input_heights[self._factor_i]
        sw = self._input_widths[self._factor_i]
        par = 1. * self._par[0] / self._par[1]

        if self.model.properties.is_square:
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
            values = []
            for i, height in enumerate(self._input_heights):
                values.append(('%d pixels' % height, i))
            self.combobox_scaled_height.prefill(values)
            self._set_sensitive(True)
            self.on_update_output_format()

        def trapRemote(failure):
            failure.trap(errors.RemoteRunError)
        d.addCallback(firewireCheckDone)
        d.addErrback(trapRemote)
        return d

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
        self._factor_i = self.combobox_scaled_height.get_selected()

        self._width_correction = None
        for i in type(self).width_corrections:
            if getattr(self,'radiobutton_width_'+i).get_active():
                self._width_correction = i
                break
        assert self._width_correction

        self._update_output_format()


class FireWireStep(_FireWireCommon, VideoSourceStep):
    name = _('Firewire')
    def __init__(self, wizard, model):
        VideoSourceStep.__init__(self, wizard, model)
        _FireWireCommon.__init__(self)


class FireWireAudioStep(_FireWireCommon, AudioSourceStep):
    name = _('Firewire audio')

    def __init__(self, wizard, model):
        AudioSourceStep.__init__(self, wizard, model)
        _FireWireCommon.__init__(self)

    # WizardStep

    def setup(self):
        self.frame_scaling.hide()
        self.frame_width_correction.hide()
        self.frame_capture.hide()
        self.frame_output_format.hide()

    def get_next(self):
        return None
