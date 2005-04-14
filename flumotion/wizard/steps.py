# -*- Mode: Python -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# Flumotion - a streaming media server
# Copyright (C) 2004,2005 Fluendo, S.L. (www.fluendo.com). All rights reserved.

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

import math

import gtk
        
from twisted.internet import defer

from flumotion.common import errors
from flumotion.configure import configure
from flumotion.wizard import wizard
from flumotion.wizard.enums import AudioDevice, EncodingAudio, \
     EncodingFormat, EncodingVideo, \
     LicenseType, RotateSize, RotateTime, SoundcardBitdepth, \
     SoundcardChannels, SoundcardSystem, SoundcardAlsaDevice, \
     SoundcardOSSDevice, SoundcardInput, SoundcardSamplerate, \
     AudioTestSamplerate, TVCardDevice, TVCardSignal, \
     VideoDevice, VideoTestFormat, VideoTestPattern

# pychecker doesn't like the auto-generated widget attrs
# or the extra args we name in callbacks
__pychecker__ = 'no-classattr no-argsused'

class Welcome(wizard.WizardStep):
    step_name = 'Welcome'
    glade_file = 'wizard_welcome.glade'
    section = 'Welcome'
    section_name = 'Welcome'
    icon = 'wizard.png'
    has_worker = False
    def get_next(self):
        return 'Source'
wizard.register_step(Welcome, initial=True)

class Source(wizard.WizardStep):
    step_name = 'Source'
    glade_file = 'wizard_source.glade'
    section = 'Production'
    section_name = 'Production'
    icon = 'source.png'
    
    def setup(self):
        self.combobox_video.set_enum(VideoDevice)
        self.combobox_audio.set_enum(AudioDevice)
        tips = gtk.Tooltips()
        tips.set_tip(self.checkbutton_has_video,
                     'If you want to stream video')
        tips.set_tip(self.checkbutton_has_audio,
                     'If you want to stream audio')
        
        self.combobox_video.set_active(VideoDevice.Test)
        self.combobox_audio.set_active(AudioDevice.Test)

    def activated(self):
        self.verify()
        
    def on_checkbutton_has_video_toggled(self, button):
        self.combobox_video.set_sensitive(button.get_active())
        self.verify()
        
    def on_checkbutton_has_audio_toggled(self, button):
        self.combobox_audio.set_sensitive(button.get_active())
        self.verify()

    def on_combobox_video_changed(self, button):
        self.verify()
        
    def on_combobox_audio_changed(self, button):
        self.verify()
        
    def verify(self):
        if not hasattr(self.wizard, 'combobox_worker'):
            return
        
        has_audio = self.checkbutton_has_audio
        has_video = self.checkbutton_has_video
        if (not has_audio and not has_video):
            self.wizard.block_next(True)
            self.wizard.combobox_worker.set_sensitive(False)
            return
        else:
            self.wizard.block_next(False)

        video_source = self.combobox_video.get_active()
        audio_source = self.combobox_audio.get_active()
        if (has_audio and audio_source == AudioDevice.Firewire and not
            has_video and video_source == VideoDevice.Firewire):
            self.wizard.combobox_worker.set_sensitive(True)
        else:
            self.wizard.combobox_worker.set_sensitive(False)

    def get_next(self):
        if self.checkbutton_has_video:
            video_source = self.combobox_video.get_active()
            return video_source.step
        elif self.checkbutton_has_audio:
            audio_source = self.combobox_audio.get_active()
            return audio_source.step
            
        raise AssertionError
wizard.register_step(Source)

class VideoSource(wizard.WizardStep):
    section = 'Production'
    icon = 'widget_doc.png'
   
    def get_next(self):
        return 'Overlay'

    def get_state(self):
        options = wizard.WizardStep.get_state(self)
        options['width'] = int(options['width'])
        options['height'] = int(options['height'])
        return options

# note:
# v4l talks about "signal" (PAL/...) and "channel" (TV/Composite/...)
# and frequency
# gst talks about "norm" and "channel"
# and frequency
# apps (and flumotion) talk about "TV Norm" and "source",
# and channel (corresponding to frequency)
class TVCard(VideoSource):
    step_name = 'TV Card'
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
        self.update_sources()

    def worker_changed(self):
        self.clear_combos()
        self.update_sources()
        
    def before_show(self):
        self.clear_combos()
        self.update_sources()
        
    def clear_combos(self):
        self.combobox_tvnorm.clear()
        self.combobox_tvnorm.set_sensitive(False)
        self.combobox_source.clear()
        self.combobox_source.set_sensitive(False)
        
    def _queryCallback(self, (deviceName, channels, norms)):
        self.wizard.block_next(False)
        self.combobox_tvnorm.set_list(norms)
        self.combobox_tvnorm.set_sensitive(True)
        self.combobox_source.set_list(channels)
        self.combobox_source.set_sensitive(True)

    def _queryGstErrorErrback(self, failure):
        failure.trap(errors.GstError)
        self.clear_combos()
        self.wizard.error_dialog('GStreamer error: %s' % failure.value)

    def _unknownDeviceErrback(self, failure):
        failure.trap(errors.UnknownDeviceError)
        self.clear_combos()

    def _queryRemoteRunErrback(self, failure):
        failure.trap(errors.RemoteRunError)
        self.wizard.error_dialog('General error: %s' % failure.value)
        
    def update_sources(self):
        if self.in_setup:
            return

        self.wizard.block_next(True)
        
        device = self.combobox_device.get_string()
        if not device:
            print "ERROR: no device selected"
        d = self.workerRun('flumotion.worker.checks.video', 'checkTVCard',
                           device)
        d.addCallback(self._queryCallback)
        d.addErrback(self._queryGstErrorErrback)
        d.addErrback(self._unknownDeviceErrback)
        d.addErrback(self._queryRemoteRunErrback)
        
    def get_state(self):
        options = {}
        options['device'] = self.combobox_device.get_string()
        options['signal'] = self.combobox_tvnorm.get_string()
        options['channel'] = self.combobox_source.get_string()
        options['width'] = int(self.spinbutton_width.get_value())
        options['height'] = int(self.spinbutton_height.get_value())
        options['framerate'] = self.spinbutton_framerate.get_value()
        return options
wizard.register_step(TVCard)

class FireWire(VideoSource):
    step_name = 'Firewire'
    glade_file = 'wizard_firewire.glade'
    component_type = 'firewire'
    icon = 'firewire.png'
    width_corrections = ['none', 'pad', 'stretch']

    # options detected from the device:
    dims = None
    factors = (1,2,3,4,6,8)
    input_heights = None
    input_widths = None
    par = None

    # these are instance state variables:
    is_square = None
    factor_i = None             # index into self.factors
    width_correction = None     # currently chosen item from width_corrections
    
    def set_sensitive(self, is_sensitive):
        if is_sensitive:
            self.vbox_controls.show()
            self.textview_status.hide()
        else:
            self.vbox_controls.hide()
            self.textview_status.show()
        self.wizard.block_next(not is_sensitive)
        
    def _queryCallback(self, options):
        # if we are here, then it was successful
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

    def _queryErrback(self, failure):
        buf = self.textview_status.get_buffer()
        buf.set_text('No Firewire device detected.\n(%s)' % failure.value)

    def on_update_output_format(self, *args):
        # update label_camera_settings
        type = 'Unknown'
        aspect = 'Unknown'
        h = self.dims[1]
        if h == 576:
            type = 'PAL'
        elif h == 480:
            type = 'NTSC'
        else:
            self.warning('Unknown capture type for height %d' % h)

        nom = self.par[0]
        den = self.par[1]
        if nom == 59 or nom == 10:
            aspect = '4:3'
        elif nom == 118 or nom == 40:
            aspect = '16:9'
        else:
            self.warning('Unknown pixel aspect ratio %d/%d' % (nom, den))

        text = '%s, %s (%d/%d pixel aspect ratio)' % (type, aspect, nom, den)
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
        if self.is_square:
            msg = ('%dx%d, 1/1 pixel aspect ratio' % (d['ow'], d['oh']))
        else:
            msg = ('%dx%d, %d/%d pixel aspect ratio'
                   % (d['ow'], d['oh'], self.par[0], self.par[1]))
        self.label_output_format.set_markup(msg)
        
    def get_state(self):
        options = {} # VideoSource.get_state(self)
        d = self._get_width_height()
        options['height'] = d['oh']
        options['scaled_width'] = d['sw']
        options['width'] = d['ow']
        options['is_square'] = self.is_square
        options['framerate'] = self.spinbutton_framerate.get_value()
        return options

    def worker_changed(self):
        self.clear()
        self.update()
        
    def before_show(self):
        self.clear()
        self.update()

    def clear(self):
        buf = self.textview_status.get_buffer()
        buf.set_text('')
 
    def update(self):
        self.textview_status.realize()
        normal_bg = self.textview_status.get_style().bg[gtk.STATE_NORMAL]
        self.textview_status.modify_base(gtk.STATE_INSENSITIVE, normal_bg)
        buf = self.textview_status.get_buffer()
        buf.set_text('Detecting Firewire device...')
        self.set_sensitive(False)
        d = self.workerRun('flumotion.worker.checks.video', 'check1394')
        d.addCallback(self._queryCallback)
        d.addErrback(self._queryErrback)

wizard.register_step(FireWire)

class Webcam(VideoSource):
    step_name = 'Webcam'
    glade_file = 'wizard_webcam.glade'
    component_type = 'video4linux'
    icon = 'webcam.png'
    
    in_setup = False

    def setup(self):
        self.in_setup = True
        self.combobox_device.set_list(('/dev/video0',
                                       '/dev/video1',
                                       '/dev/video2',
                                       '/dev/video3'))
        self.in_setup = False

    def on_combobox_device_changed(self, combo):
        self.update()

    def worker_changed(self):
        self.clear()
        self.update()
        
    def before_show(self):
        self.clear()
        self.update()
        
    def clear(self):
        self.spinbutton_width.set_sensitive(False)
        self.spinbutton_height.set_sensitive(False)
        self.spinbutton_framerate.set_sensitive(False)
        self.label_name.set_label("")
        
    def _queryCallback(self, deviceName):
        self.label_name.set_label(deviceName)
        self.wizard.block_next(False)
        self.spinbutton_width.set_sensitive(True)
        self.spinbutton_height.set_sensitive(True)
        self.spinbutton_framerate.set_sensitive(True)

    def _queryGstErrorErrback(self, failure):
        failure.trap(errors.GstError)
        self.clear()
        self.wizard.error_dialog('GStreamer error: %s' % failure.value)

    def _unknownDeviceErrback(self, failure):
        failure.trap(errors.UnknownDeviceError)
        self.clear()

    def _queryRemoteRunErrback(self, failure):
        failure.trap(errors.RemoteRunError)
        self.wizard.error_dialog('General error: %s' % failure.value)

    def update(self):
        if self.in_setup:
            return
        
        self.wizard.block_next(True)
        
        device = self.combobox_device.get_string()
        d = self.workerRun('flumotion.worker.checks.video', 'checkWebcam',
                           device)
        d.addCallback(self._queryCallback)
        d.addErrback(self._queryGstErrorErrback)
        d.addErrback(self._unknownDeviceErrback)
        d.addErrback(self._queryRemoteRunErrback)

    def get_state(self):
        options = {}
        options['device'] = self.combobox_device.get_string()
        options['width'] = int(self.spinbutton_width.get_value())
        options['height'] = int(self.spinbutton_height.get_value())
        options['framerate'] = self.spinbutton_framerate.get_value()
        return options
wizard.register_step(Webcam)

class TestVideoSource(VideoSource):
    step_name = 'Test Video Source'
    glade_file = 'wizard_testsource.glade'
    component_type = 'videotestsrc'
    icon = 'testsource.png'
    
    def before_show(self):
        self.wizard.check_elements(self.worker, 'videotestsrc')

    def setup(self):
        self.combobox_pattern.set_enum(VideoTestPattern)
        self.combobox_format.set_enum(VideoTestFormat)

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
        options['framerate'] = self.spinbutton_framerate.get_value()
        return options
wizard.register_step(TestVideoSource)

class Overlay(wizard.WizardStep):
    step_name = 'Overlay'
    glade_file = 'wizard_overlay.glade'
    section = 'Production'
    component_type = 'overlay'
    icon = 'overlay.png'

    def before_show(self):
        d = self.workerRun('flumotion.worker.checks.video',
            'check_ffmpegcolorspace_AYUV')
        d.addCallback(self._queryCallback)
        #d.addErrback(self._queryRemoteRunErrback)
        d.addErrback(self._queryErrback)

        self.wizard.check_elements(self.worker, 'pngdec', 'alphacolor',
            'videomixer', 'alpha')

        # FIXME: add a PIL check here

    def _queryCallback(self, result):
        if result:
            self.wizard.check_elements(self.worker, 'pngdec',
                'ffmpegcolorspace', 'videomixer')
        else:
            # throw up an informational dialog
            msg = """This worker's ffmpegcolorspace plugin is older than 0.8.5.
Please consider upgrading if your output video has a diagonal line in the
image."""
            self.debug(msg)
            self.wizard.info_dialog(msg)
            self.wizard.check_elements(self.worker, 'pngdec', 'alphacolor',
                'videomixer', 'alpha', 'ffmpegcolorspace')
            
    def _queryErrback(self, failure):
        msg = ('Could not check ffmpegcolorspace features.\n(%s)' %
            failure.value)
        self.wizard.block_next(True)
        self.wizard.error_dialog(msg)
        
    def on_checkbutton_show_text_toggled(self, button):
        self.entry_text.set_sensitive(button.get_active())

    def get_state(self):
        options = wizard.WizardStep.get_state(self)
        if self.checkbutton_show_logo:
            options['logo'] = True
            
        if self.checkbutton_show_text:
            options['text'] = self.entry_text.get_text()

        # XXX: Serious refactoring needed.
        video_options = self.wizard.get_step_options('Source')
        video_source = video_options['video']
        video_step = self.wizard[video_source.step]
        video_props = video_step.get_state()
        
        options['width'] = video_props['width']
        options['height'] = video_props['height']

        return options

    def get_next(self):
        if self.wizard.get_step_option('Source', 'has_audio'):
            audio_source = self.wizard.get_step_option('Source', 'audio')            
            if audio_source == AudioDevice.Soundcard:
                return 'Soundcard'
            elif audio_source == AudioDevice.Test:
                return 'Test Audio Source'
            
        return 'Encoding'
wizard.register_step(Overlay)

class Soundcard(wizard.WizardStep):
    step_name = 'Soundcard'
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

    def worker_changed(self):
        self.clear_combos()
        self.update_devices()
        self.update_inputs()

    def before_show(self):
        # block updates, because populating a shown combobox will of course
        # trigger the callback
        self.block_update = True
        self.combobox_system.set_enum(SoundcardSystem)
        self.block_update = False
        
        self.clear_combos()
        
        self.update_devices()
        self.update_inputs()

    def clear_combos(self):
        self.combobox_input.clear()
        self.combobox_input.set_sensitive(False)
        self.combobox_channels.clear()
        self.combobox_channels.set_sensitive(False)
        self.combobox_samplerate.clear()
        self.combobox_samplerate.set_sensitive(False)
        self.combobox_bitdepth.clear()
        self.combobox_bitdepth.set_sensitive(False)
        
    def _queryCallback(self, (deviceName, tracks)):
        self.wizard.block_next(False)
        self.combobox_channels.set_enum(SoundcardChannels)
        self.combobox_channels.set_sensitive(True)
        self.combobox_samplerate.set_enum(SoundcardSamplerate)
        self.combobox_samplerate.set_sensitive(True)
        self.combobox_bitdepth.set_enum(SoundcardBitdepth)
        self.combobox_bitdepth.set_sensitive(True)

        self.combobox_input.set_list(tracks)
        self.combobox_input.set_sensitive(True)

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

    # FIXME: move higher up in hierarchy
    def _queryGstErrorErrback(self, failure):
        failure.trap(errors.GstError)
        self.clear_combos()
        self.wizard.error_dialog('GStreamer error: %s' % failure.value)

    def _queryRemoteRunErrback(self, failure):
        failure.trap(errors.RemoteRunError)
        self.wizard.error_dialog('%s' % failure.value)

    def update_inputs(self):
        if self.block_update:
            return
        self.wizard.block_next(True)
        
        enum = self.combobox_system.get_enum()
        device = self.combobox_device.get_string()
        d = self.workerRun('flumotion.worker.checks.video', 'checkMixerTracks',
                           enum.element, device)
        d.addCallback(self._queryCallback)
        d.addErrback(self._queryGstErrorErrback)
        d.addErrback(self._queryRemoteRunErrback)
        #d.addErrback(self._unknownDeviceErrback)
        #d.addErrback(self._permissionDeniedErrback)
        
    def get_state(self):
        # FIXME: this can't be called if the soundcard hasn't been probed yet
        # for example, when going through the testsuite
        try:
            channels = self.combobox_channels.get_enum().intvalue
            element = self.combobox_system.get_enum().element
            bitdepth = self.combobox_bitdepth.get_string()
            samplerate = self.combobox_samplerate.get_string()
        except AttributeError:
            # when called without enum setup
            channels = 0
            element = "fakesrc"
            bitdepth = "9"
            samplerate = "12345"

        d = dict(device=self.combobox_device.get_string(),
                    depth=int(bitdepth),
                    rate=int(samplerate),
                    channels=channels,
                    input=self.combobox_input.get_string())
        # FIXME: can a key with a dash be specified ?
        d['source-element'] = element
        return d

    def get_next(self):
        return 'Encoding'
wizard.register_step(Soundcard)

class TestAudioSource(wizard.WizardStep):
    step_name = 'Test Audio Source'
    glade_file = 'wizard_audiotest.glade'
    section = 'Production'
    icon = 'soundcard.png'
    
    def before_show(self):
        self.wizard.check_elements(self.worker, 'sinesrc')
        self.combobox_samplerate.set_enum(AudioTestSamplerate)
        self.combobox_samplerate.set_sensitive(True)

    def get_state(self):
        return {
            'freq': int(self.spinbutton_freq.get_value()),
            'volume': float(self.spinbutton_volume.get_value()),
            'rate': self.combobox_samplerate.get_int()
        }
    
    def get_next(self):
        return 'Encoding'
wizard.register_step(TestAudioSource)

class Encoding(wizard.WizardStep):
    step_name = 'Encoding'
    glade_file = 'wizard_encoding.glade'
    section = 'Conversion'
    section_name = 'Conversion'
    
    setup_finished = False

    def setup(self):
        self.combobox_format.set_enum(EncodingFormat)
        self.combobox_audio.set_enum(EncodingAudio)
        self.combobox_video.set_enum(EncodingVideo)
        self.setup_finished = True
        
    def on_combobox_format_changed(self, combo):
        self.verify()
        
    def verify(self):
        # XXX: isn't there a better way of doing this, like blocking
        #      the signal
        if not self.setup_finished:
            return
        
        format = self.combobox_format.get_active()
        if format == EncodingFormat.Ogg:
            # XXX: Smoke can't be put in ogg. Poke Wim to fix
            self.combobox_video.set_multi_active(EncodingVideo.Theora)
            self.combobox_audio.set_multi_active(EncodingAudio.Speex,
                                                 EncodingAudio.Vorbis)
        elif format == EncodingFormat.Multipart:
            self.combobox_video.set_multi_active(EncodingVideo.Smoke,
                                                 EncodingVideo.JPEG)
            self.combobox_audio.set_multi_active(EncodingAudio.Mulaw)

        has_audio = self.wizard.get_step_option('Source', 'has_audio')
        self.combobox_audio.set_property('visible', has_audio)
        self.label_audio.set_property('visible', has_audio)
            
        has_video = self.wizard.get_step_option('Source', 'has_video')
        self.combobox_video.set_property('visible', has_video)
        self.label_video.set_property('visible', has_video)
    
    def activated(self):
        self.verify()

    def get_audio_page(self):
        if self.wizard.get_step_option('Source', 'has_audio'):
            codec = self.combobox_audio.get_enum()
            if codec == EncodingAudio.Vorbis:
                return 'Vorbis'
            elif codec == EncodingAudio.Speex:
                return 'Speex'
            elif codec == EncodingAudio.Mulaw:
                return 'Consumption'
            
        return 'Consumption'
        
    def get_next(self):
        if self.wizard.get_step_option('Source', 'has_video'):
            codec = self.combobox_video.get_enum()
            if codec == EncodingVideo.Theora:
                return 'Theora'
            elif codec == EncodingVideo.Smoke:
                return 'Smoke'
            elif codec == EncodingVideo.JPEG:
                return 'JPEG'
        elif self.wizard.get_step_option('Source', 'has_audio'):
            return self.get_audio_page()
        else:
            return 'Consumption'
wizard.register_step(Encoding)

class VideoEncoder(wizard.WizardStep):
    section = 'Conversion'
wizard.register_step(VideoEncoder)

class Theora(VideoEncoder):
    step_name = 'Theora'
    glade_file = 'wizard_theora.glade'
    component_type = 'theora'
    icon = 'xiphfish.png'
    
    def setup(self):
        # XXX: move to glade file
        self.spinbutton_bitrate.set_range(0, 4000)
        self.spinbutton_bitrate.set_value(400)
        self.spinbutton_quality.set_range(0, 63)
        self.spinbutton_quality.set_value(16)

    def before_show(self):
        self.wizard.check_elements(self.worker, 'theoraenc')
        
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
            options['bitrate'] = int(self.spinbutton_bitrate.get_value())
        elif self.radiobutton_quality:
            options['quality'] = int(self.spinbutton_quality.get_value())

        return options
    
wizard.register_step(Theora)

class Smoke(VideoEncoder):
    step_name = 'Smoke'
    glade_file = 'wizard_smoke.glade'
    section = 'Conversion'
    component_type = 'smoke'

    def before_show(self):
        self.wizard.check_elements(self.worker, 'smokeenc')
        
    def get_next(self):
        return self.wizard['Encoding'].get_audio_page()
    
    def get_state(self):
        options = VideoEncoder.get_state(self)
        options['qmin'] = int(options['qmin'])
        options['qmax'] = int(options['qmax'])
        options['threshold'] = int(options['threshold'])
        options['keyframe'] = int(options['keyframe'])
        return options

wizard.register_step(Smoke)

class JPEG(VideoEncoder):
    step_name = 'JPEG'
    glade_file = 'wizard_jpeg.glade'
    section = 'Conversion'
    component_type = 'jpeg'

    def before_show(self):
        self.wizard.check_elements(self.worker, 'jpegenc')

    def get_next(self):
        return self.wizard['Encoding'].get_audio_page()
    
    def get_state(self):
        options = VideoEncoder.get_state(self)
        options['quality'] = int(options['quality'])
        options['framerate'] = float(options['framerate'])
        return options
    
wizard.register_step(JPEG)

class AudioEncoder(wizard.WizardStep):
    glade_file = 'wizard_audio_encoder.glade'
    section = 'Conversion'
    
    def get_next(self):
        return 'Consumption'

# Worker?
class Vorbis(AudioEncoder):
    glade_file = 'wizard_vorbis.glade'
    step_name = 'Vorbis'
    component_type = 'vorbis'
    icon = 'xiphfish.png'

    def setup(self):
        self.spinbutton_bitrate.set_range(6, 250)
        self.spinbutton_bitrate.set_value(64)
        # By choosing quality as a default, we avoid samplerate/bitrate
        # mismatch
        self.radiobutton_bitrate.set_active(False)
        self.radiobutton_quality.set_active(True)
        
    def before_show(self):
        self.wizard.check_elements(self.worker, 'rawvorbisenc')
        
    # This is bound to both radiobutton_bitrate and radiobutton_quality
    def on_radiobutton_toggled(self, button):
        self.spinbutton_bitrate.set_sensitive(
            self.radiobutton_bitrate.get_active())
        self.spinbutton_quality.set_sensitive(
            self.radiobutton_quality.get_active())
        
    def get_state(self):
        options = {}
        if self.radiobutton_bitrate:
            options['bitrate'] = int(self.spinbutton_bitrate.get_value()) * 1024
        elif self.radiobutton_quality:
            options['quality'] = int(self.spinbutton_quality.get_value())
        return options
wizard.register_step(Vorbis)

class Speex(AudioEncoder):
    step_name = 'Speex'
    component_type = 'speex'
    icon = 'xiphfish.png'
    
    def before_show(self):
        self.wizard.check_elements(self.worker, 'speexenc')
        
    def setup(self):
        # Should be 2150 instead of 3 -> 3000
        self.spinbutton_bitrate.set_range(3, 30)
        self.spinbutton_bitrate.set_value(11)
        
    def get_state(self):
        options = AudioEncoder.get_state(self)
        options['bitrate'] = int(self.spinbutton_bitrate.get_value()) * 1024
        return options
wizard.register_step(Speex)

class Consumption(wizard.WizardStep):
    step_name = 'Consumption'
    glade_file = 'wizard_consumption.glade'
    section = 'Consumption'
    section_name = 'Consumption'
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

    def verify(self):
        if (not self.checkbutton_disk and not self.checkbutton_http):
            self.wizard.block_next(True)
        else:
            self.wizard.block_next(False)

    def activated(self):
        has_audio = self.wizard.get_step_option('Source', 'has_audio')
        has_video = self.wizard.get_step_option('Source', 'has_video')
        has_both = has_audio and has_video

        # Most of the options only makes sense if we selected audio
        # and video in the first page. If we didn't just hide them
        self.checkbutton_http_audio_video.set_property('visible', has_both)
        self.checkbutton_http_audio.set_property('visible', has_both)
        self.checkbutton_http_video.set_property('visible', has_both)
        self.checkbutton_disk_audio_video.set_property('visible', has_both)
        self.checkbutton_disk_audio.set_property('visible', has_both)
        self.checkbutton_disk_video.set_property('visible', has_both)

    def get_next(self, step=None):
        items = []
        has_audio = self.wizard.get_step_option('Source', 'has_audio')
        has_video = self.wizard.get_step_option('Source', 'has_video')

        if has_audio and has_video:
            if self.checkbutton_http:
                if self.checkbutton_http_audio_video:
                    items.append('HTTP Streamer (audio & video)')
                if self.checkbutton_http_audio:
                    items.append('HTTP Streamer (audio only)')
                if self.checkbutton_http_video:
                    items.append('HTTP Streamer (video only)')
            if self.checkbutton_disk:
                if self.checkbutton_disk_audio_video:
                    items.append('Disk (audio & video)')
                if self.checkbutton_disk_audio:
                    items.append('Disk (audio only)')
                if self.checkbutton_disk_video:
                    items.append('Disk (video only)')
        elif has_video and not has_audio:
            if self.checkbutton_http:
                items.append('HTTP Streamer (video only)')
            if self.checkbutton_disk:
                items.append('Disk (video only)')
        elif has_audio and not has_video:
            if self.checkbutton_http:
                items.append('HTTP Streamer (audio only)')
            if self.checkbutton_disk:
                items.append('Disk (audio only)')
        else:
            raise AssertionError
        
        assert items
        
        if not step:
            return items[0]
        else:
            stepname = step.get_name()
            if stepname in items and items[-1] != stepname:
                return items[items.index(stepname)+1]
            else:
                return 'Content License'
wizard.register_step(Consumption)

# XXX: If audio codec is speex, disable java applet option
class HTTP(wizard.WizardStep):
    glade_file = 'wizard_http.glade'
    section = 'Consumption'
    component_type = 'http-streamer'

    def before_show(self):
        self.wizard.check_elements(self.worker, 'multifdsink')
        
    def setup(self):
        self.spinbutton_port.set_value(self.port)
        
    def get_next(self):
        return self.wizard['Consumption'].get_next(self)

    def get_state(self):
        options = wizard.WizardStep.get_state(self)

        options['bandwidth_limit'] = int(options['bandwidth_limit'])
        options['user_limit'] = int(options['user_limit'])
        options['port'] = int(options['port'])

        return options

class HTTPBoth(HTTP):
    step_name = 'HTTP Streamer (audio & video)'
    sidebar_name = 'HTTP audio/video'
    port = configure.defaultStreamPortRange[0]
wizard.register_step(HTTPBoth)

class HTTPAudio(HTTP):
    step_name = 'HTTP Streamer (audio only)'
    sidebar_name = 'HTTP audio'
    port = configure.defaultStreamPortRange[1]
wizard.register_step(HTTPAudio)

class HTTPVideo(HTTP):
    step_name = 'HTTP Streamer (video only)'
    sidebar_name = 'HTTP video'
    port = configure.defaultStreamPortRange[2]
wizard.register_step(HTTPVideo)

class Disk(wizard.WizardStep):
    glade_file = 'wizard_disk.glade'
    section = 'Consumption'
    icon = 'kcmdevices.png'
    
    def setup(self):
        self.combobox_time_list.set_enum(RotateTime)
        self.combobox_size_list.set_enum(RotateSize)
        self.radiobutton_has_time.set_active(True)
        self.spinbutton_time.set_value(12)
        self.combobox_time_list.set_active(RotateTime.Hours)

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
        if self.checkbutton_rotate:
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
        if not self.checkbutton_rotate:
            options['rotateType'] = 'none'
        else:
            if self.radiobutton_has_time:
                options['rotateType'] = 'time'
                unit = self.combobox_time_list.get_enum().unit
                options['time'] = long(self.spinbutton_time.get_value() * unit)
            elif self.radiobutton_has_size:
                options['rotateType'] = 'size'
                unit = self.combobox_size_list.get_enum().unit
                options['size'] = long(self.spinbutton_size.get_value() * unit)

        options['directory'] = self.entry_location.get_text()
        
        return options
    
    def get_next(self):
        return self.wizard['Consumption'].get_next(self)

class DiskBoth(Disk):
    step_name = 'Disk (audio & video)'
    sidebar_name = 'Disk audio/video'
wizard.register_step(DiskBoth)

class DiskAudio(Disk):
    step_name = 'Disk (audio only)'
    sidebar_name = 'Disk audio'
wizard.register_step(DiskAudio)

class DiskVideo(Disk):
    step_name = 'Disk (video only)'
    sidebar_name = 'Disk video'
wizard.register_step(DiskVideo)

class Licence(wizard.WizardStep):
    step_name = "Content License"
    glade_file = "wizard_license.glade"
    section = 'License'
    section_name = 'License'
    icon = 'licenses.png'
    has_worker = False
    def setup(self):
        self.combobox_license.set_enum(LicenseType)
        
    def on_checkbutton_set_license_toggled(self, button):
        self.combobox_license.set_sensitive(button.get_active())
        
    def get_next(self):
        return 'Summary'
wizard.register_step(Licence)

class Summary(wizard.WizardStep):
    step_name = "Summary"
    glade_file = "wizard_summary.glade"
    icon = 'summary.png'
    has_worker = False
    last_step = True
    def before_show(self):
        self.textview_message.realize()
        normal_bg = self.textview_message.get_style().bg[gtk.STATE_NORMAL]
        self.textview_message.modify_base(gtk.STATE_INSENSITIVE, normal_bg)
    def get_next(self):
        return
wizard.register_step(Summary)
