# -*- Mode: Python -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# flumotion/wizard/steps.py: a step in the wizard
#
# Flumotion - a streaming media server
# Copyright (C) 2004 Fluendo, S.L. (www.fluendo.com). All rights reserved.

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

import gtk
        
from twisted.internet import defer

from flumotion.common import errors
from flumotion.configure import configure
from flumotion.wizard import wizard
from flumotion.wizard.enums import AudioDevice, EncodingAudio, \
     EncodingFormat, EncodingVideo, Enum, EnumClass, EnumMetaClass, \
     LicenseType, RotateSize, RotateTime, SoundcardBitdepth, \
     SoundcardChannels, SoundcardSystem, SoundcardAlsaDevice, SoundcardOSSDevice, \
     SoundcardInput, SoundcardSamplerate, TVCardDevice, TVCardSignal, \
     VideoDevice, VideoTestFormat, VideoTestPattern



class Welcome(wizard.WizardStep):
    step_name = 'Welcome'
    glade_file = 'wizard_welcome.glade'
    section = 'Welcome'
    section_name = 'Welcome'
    icon = 'wizard.png'
    has_worker = False
    def get_next(self):
        return 'Source'
wizard.register_step(Welcome)



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
            if audio_source == AudioDevice.Soundcard:
                return 'Soundcard'
            else:
                return 'Encoding'
        raise AssertionError
wizard.register_step(Source)



class VideoSource(wizard.WizardStep):
    section = 'Production'
    icon = 'widget_doc.png'
   
    def get_next(self):
        return 'Overlay'

    def get_component_properties(self):
        options = self.wizard.get_step_state(self)
        options['width'] = int(options['width'])
        options['height'] = int(options['height'])
        return options


def _checkChannels(device):
    # check channels on a v4lsrc element with the given device
    # returns: a deferred returning a tuple of (deviceName, channels, norms)
    # or a failure
    from twisted.internet import defer, reactor
    import gst
    import gst.interfaces
    
    class Result:
        def __init__(self):
            self.d = defer.Deferred()
            self.returned = False
    
    # gst, defer and errors are already in the namespace 
    def state_changed_cb(pipeline, old, new, res):
        if not (old == gst.STATE_NULL and new == gst.STATE_READY):
            return
        element = pipeline.get_by_name('source')
        deviceName = element.get_property('device-name')
        channels = [channel.label for channel in element.list_channels()]
        norms = [norm.label for norm in element.list_norms()]
        reactor.callLater(0, pipeline.set_state, gst.STATE_NULL)
        if not res.returned:
            res.returned = True
            res.d.callback((deviceName, channels, norms))
                
    def error_cb(pipeline, element, error, _, res):
        if not res.returned:
            res.returned = True
            res.d.errback(errors.GstError(error.message))

    pipeline = 'v4lsrc name=source device=%s ! fakesink' % device
    bin = gst.parse_launch(pipeline)
    result = Result()
    bin.connect('state-change', state_changed_cb, result)
    bin.connect('error', error_cb, result)
    bin.set_state(gst.STATE_PLAYING)

    return result.d


class TVCard(VideoSource):
    step_name = 'TV Card'
    glade_file = 'wizard_tvcard.glade'
    component_type = 'bttv'
    icon = 'tv.png'

        
    def on_combobox_device_changed(self, combo):
        self.update_channels()

    def worker_changed(self):
        self.clear_combos()
        self.update_channels()
        
    def before_show(self):
        self.clear_combos()
        self.update_channels()
        
    def clear_combos(self):
        self.combobox_signal.clear()
        self.combobox_signal.set_sensitive(False)
        self.combobox_channel.clear()
        self.combobox_channel.set_sensitive(False)
        
    def _queryCallback(self, (deviceName, channels, norms)):
        self.wizard.block_next(False)
        self.combobox_signal.set_list(norms)
        self.combobox_signal.set_sensitive(True)
        self.combobox_channel.set_list(channels)
        self.combobox_channel.set_sensitive(True)

    def _queryGstErrorErrback(self, failure):
        failure.trap(errors.GstError)
        self.clear_combos()
        self.wizard.error_dialog('GStreamer error: %s' % failure.value)

    def _unknownDeviceErrback(self, failure):
        failure.trap(errors.UnknownDeviceError)
        self.clear_combos()
        
    def update_channels(self):
        self.wizard.block_next(True)
        
        device = self.combobox_device.get_string()
        d = self.workerRun(_checkChannels, device)
        d.addCallback(self._queryCallback)
        d.addErrback(self._queryGstErrorErrback)
        d.addErrback(self._unknownDeviceErrback)
        
    def get_component_properties(self):
        options = {}
        options['device'] = self.combobox_device.get_string()
        options['signal'] = self.combobox_signal.get_string()
        options['channel'] = self.combobox_channel.get_string()
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
wizard.register_step(FireWire)


# FIXME: rename, only for v4l stuff
def _checkDeviceName(device):
    # this function gets sent to and executed on the worker
    # it will fire a deferred returning the deviceName, or a failure
    from twisted.internet import defer, reactor
    import gst

    class Result:
        def __init__(self):
            self.d = defer.Deferred()
            self.returned = False
    
    # gst, defer and errors are already in the namespace 
    def state_changed_cb(pipeline, old, new, res):
        if not (old == gst.STATE_NULL and new == gst.STATE_READY):
            return
        element = pipeline.get_by_name('source')
        deviceName = element.get_property('device-name')
        reactor.callLater(0, pipeline.set_state, gst.STATE_NULL)
        if not res.returned:
            res.returned = True
            res.d.callback(deviceName)
                
    def error_cb(pipeline, element, error, _, res):
        if not res.returned:
            res.returned = True
            res.d.errback(errors.GstError(error.message))

    pipeline = 'v4lsrc name=source device=%s autoprobe=false ! fakesink' % device
    bin = gst.parse_launch(pipeline)
    result = Result()
    bin.connect('state-change', state_changed_cb, result)
    bin.connect('error', error_cb, result)
    bin.set_state(gst.STATE_PLAYING)

    return result.d


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

    def update(self):
        if self.in_setup:
            return
        
        self.wizard.block_next(True)
        
        device = self.combobox_device.get_string()
        d = self.workerRun(_checkDeviceName, device)
        d.addCallback(self._queryCallback)
        d.addErrback(self._queryGstErrorErrback)
        d.addErrback(self._unknownDeviceErrback)
        
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

    def get_component_properties(self):
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
        self.wizard.check_elements(self.worker, 'pngdec', 'alphacolor',
                                  'videomixer', 'alpha')
        
    def on_checkbutton_show_text_toggled(self, button):
        self.entry_text.set_sensitive(button.get_active())

    def get_component_properties(self):
        options = {}
        if self.checkbutton_show_logo:
            options['logo'] = True
            
        if self.checkbutton_show_text:
            options['text'] = self.entry_text.get_text()

        # XXX: Serious refactoring needed.
        video_options = self.wizard.get_step_options('Source')
        video_source = video_options['video']
        video_step = self.wizard[video_source.step]
        video_props = video_step.get_component_properties()
        
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


def _checkTracks(source_element, device):
    from twisted.internet import defer, reactor
    import gst
    import gst.interfaces
    
    class Result:
        def __init__(self):
            self.d = defer.Deferred()
            self.returned = False
    
    # gst, defer and errors are already in the namespace 
    def state_changed_cb(pipeline, old, new, res):
        if not (old == gst.STATE_NULL and new == gst.STATE_READY):
            return
        element = pipeline.get_by_name('source')
        deviceName = element.get_property('device-name')
        try:
            tracks = [track.label for track in element.list_tracks()]
        except AttributeError:
            # list_tracks was added in gst-python 0.7.94
            if not res.returned:
                res.returned = True
                version = " ".join([str(number) for number in gst.pygst_version])
                message = 'Your version of gstreamer-python is %d.%d.%d. ' % \
                    gst.pygst_version + \
                    'Please upgrade gstreamer-python to 0.7.94 or higher.'
                res.d.errback(errors.GstError(message))
            
        reactor.callLater(0, pipeline.set_state, gst.STATE_NULL)
        if not res.returned:
            res.returned = True
            res.d.callback((deviceName, tracks))
                
    def error_cb(pipeline, element, error, _, res):
        if not res.returned:
            res.returned = True
            res.d.errback(errors.GstError(error.message))

    pipeline = '%s name=source device=%s ! fakesink' % (source_element, device)
    bin = gst.parse_launch(pipeline)
    result = Result()
    bin.connect('state-change', state_changed_cb, result)
    bin.connect('error', error_cb, result)
    bin.set_state(gst.STATE_PLAYING)

    return result.d


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

    def update_inputs(self):
        if self.block_update:
            return
        self.wizard.block_next(True)
        
        enum = self.combobox_system.get_enum()
        device = self.combobox_device.get_string()
        d = self.workerRun(_checkTracks, enum.element, device)
        d.addCallback(self._queryCallback)
        d.addErrback(self._queryGstErrorErrback)
        #d.addErrback(self._unknownDeviceErrback)
        #d.addErrback(self._permissionDeniedErrback)
        
    def get_component_properties(self):
        channels = self.combobox_channels.get_enum().intvalue
        element = self.combobox_system.get_enum().element

        d = dict(device=self.combobox_device.get_string(),
                    depth=int(self.combobox_bitdepth.get_string()),
                    rate=int(self.combobox_samplerate.get_string()),
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

    def get_component_properties(self):
        return {'freq': int(self.spinbutton_freq.get_value()) }
    
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
    
    def get_component_properties(self):
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
    
    def get_component_properties(self):
        options = self.wizard.get_step_state(self)
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
    
    def get_component_properties(self):
        options = self.wizard.get_step_state(self)
        options['quality'] = int(options['quality'])
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
        
    def before_show(self):
        self.wizard.check_elements(self.worker, 'rawvorbisenc')
        
    # This is bound to both radiobutton_bitrate and radiobutton_quality
    def on_radiobutton_toggled(self, button):
        self.spinbutton_bitrate.set_sensitive(
            self.radiobutton_bitrate.get_active())
        self.spinbutton_quality.set_sensitive(
            self.radiobutton_quality.get_active())
        
    def get_component_properties(self):
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
        
    def get_component_properties(self):
        options = self.wizard.get_step_state(self)
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

    def get_component_properties(self):
        options = self.wizard.get_step_state(self)

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

    def get_component_properties(self):
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
    def get_next(self):
        return
    
wizard.register_step(Summary)


