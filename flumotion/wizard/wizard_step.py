# -*- Mode: Python -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# flumotion/common/launcher.py: launch grids
#
# Flumotion - a streaming media server
# Copyright (C) 2004 Fluendo (www.fluendo.com)

# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
# See "LICENSE.GPL" in the source distribution for more information.

# This program is also licensed under the Flumotion license.
# See "LICENSE.Flumotion" in the source distribution for more information.

from flumotion.wizard.enums import * # XXX: fix later
from flumotion.wizard import wizard



class WizardStepSource(wizard.WizardStep):
    step_name = 'Source'
    glade_file = 'wizard_source.glade'
    section = 'Production'
    
    def setup(self):
        self.combobox_video.set_enum(VideoDevice)
        self.combobox_audio.set_enum(AudioDevice)
        
    def on_checkbutton_has_video_toggled(self, button):
        self.combobox_video.set_sensitive(button.get_active())
        self.verify()
        
    def on_checkbutton_has_audio_toggled(self, button):
        self.combobox_audio.set_sensitive(button.get_active())
        self.verify()

    def verify(self):
        if (not self.checkbutton_has_audio and not self.checkbutton_has_video):
            self.wizard.block_next(True)
        else:
            self.wizard.block_next(False)

    def get_next(self):
        if self.checkbutton_has_video:
            video_source = self.combobox_video.get_active()
            if video_source == VideoDevice.TVCard:
                return 'TV Card'
            elif video_source == VideoDevice.Firewire:
                return 'Firewire'
            elif video_source == VideoDevice.Webcam:
                return 'Webcam'
            elif video_source == VideoDevice.Test:
                return 'Test Source'
            raise AssertionError
        elif self.checkbutton_has_audio:
            return 'Audio Source'
        raise AssertionError



class WizardStepVideoSource(wizard.WizardStep):
    section = 'Production'
    component_name = 'video-source'
    def get_next(self):
        return 'Overlay'



class WizardStepTVCard(WizardStepVideoSource):
    step_name = 'TV Card'
    glade_file = 'wizard_tvcard.glade'
    component_type = 'bttv'

    def setup(self):
        self.combobox_device.set_enum(TVCardDevice)
        self.combobox_signal.set_enum(TVCardSignal)

    def get_component_properties(self):
        options = self.wizard.get_step_state(self)
        options['device'] = TVCardDevice.get(options['device']).name
        options['signal'] = TVCardSignal.get(options['signal']).name
        return options



class WizardStepFireWirde(WizardStepVideoSource):
    step_name = 'Firewire'
    glade_file = 'wizard_firewire.glade'
    component_type = 'firewire'



class WizardStepWebcam(WizardStepVideoSource):
    step_name = 'Webcam'
    glade_file = 'wizard_webcam.glade'
    component_type = 'video4linux'


    
class WizardStepTestSource(WizardStepVideoSource):
    step_name = 'Test Source'
    glade_file = 'wizard_testsource.glade'
    component_type = 'videotestsrc'

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
        options['pattern'] = self.combobox_pattern.get_string()
        return options



class WizardStepOverlay(wizard.WizardStep):
    step_name = 'Overlay'
    glade_file = 'wizard_overlay.glade'
    section = 'Production'
    component_type = 'overlay'
    component_name = 'overlay'
    
    def get_next(self):
        if self.wizard.get_step_option('Source', 'has_audio'):
            return 'Audio Source'
        else:
            return 'Encoding'



# XXX: Rename to Soundcard
class WizardStepAudioSource(wizard.WizardStep):
    step_name = 'Audio Source'
    glade_file = 'wizard_audiosource.glade'
    section = 'Production'
    component_name = 'audio-source'
    component_type = 'osssrc'

    def setup(self):
        self.combobox_device.set_enum(SoundcardDevice)
        self.combobox_input.set_enum(SoundcardInput)
        self.combobox_channels.set_enum(SoundcardChannels)
        self.combobox_samplerate.set_enum(SoundcardSamplerate)
        self.combobox_bitdepth.set_enum(SoundcardBitdepth)
        
    def get_component_properties(self):
        channels = self.combobox_channels.get_enum()
        if channels == SoundcardChannels.Mono:
            channels = 'mono'
        elif channels == SoundcardChannels.Stereo:
            channels = 'stereo'
            
        return dict(device=self.combobox_device.get_string(),
                    bitdepth=self.combobox_bitdepth.get_string(),
                    samplerate=self.combobox_samplerate.get_string(),
                    channels=channels,
                    input=self.combobox_input.get_string())

    def get_next(self):
        return 'Encoding'



class WizardStepEncoding(wizard.WizardStep):
    step_name = 'Encoding'
    glade_file = 'wizard_encoding.glade'
    section = 'Conversion'
    
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
            self.combobox_video.set_multi_active(EncodingVideo.Smoke,
                                                 EncodingVideo.Theora)
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
            codec = self.combobox_audio.get_value()
            if codec == EncodingAudio.Vorbis:
                return 'Vorbis'
            elif codec == EncodingAudio.Speex:
                return 'Speex'
            elif codec == EncodingAudio.Mulaw:
                return 'Mulaw'
            
        return 'Consumption'
        
    def get_next(self):
        if self.wizard.get_step_option('Source', 'has_video'):
            codec = self.combobox_video.get_value()
            if codec == EncodingVideo.Theora:
                return 'Theora'
            elif codec == EncodingVideo.Smoke:
                return 'Smoke'
            elif codec == EncodingVideo.JPEG:
                return 'JPEG'
            
        return 'Consumption'



class WizardStepVideoEncoder(wizard.WizardStep):
    section = 'Conversion'
    component_name = 'video-encoder'



class WizardStepTheora(WizardStepVideoEncoder):
    step_name = 'Theora'
    glade_file = 'wizard_theora.glade'
    component_type = 'theora'
    
    # This is bound to both radiobutton_bitrate and radiobutton_quality
    def on_radiobutton_toggled(self, button):
        self.spinbutton_bitrate.set_sensitive(
            self.radiobutton_bitrate.get_active())
        self.spinbutton_quality.set_sensitive(
            self.radiobutton_quality.get_active())

    def get_next(self):
        return self.wizard['Encoding'].get_audio_page()



class WizardStepSmoke(WizardStepVideoEncoder):
    step_name = 'Smoke'
    glade_file = 'wizard_smoke.glade'
    section = 'Conversion'
    component_type = 'smoke'

    def get_next(self):
        return self.wizard['Encoding'].get_audio_page()



class WizardStepJPEG(WizardStepVideoEncoder):
    step_name = 'JPEG'
    glade_file = 'wizard_jpeg.glade'
    section = 'Conversion'
    component_type = 'jpeg'

    def get_next(self):
        return self.wizard['Encoding'].get_audio_page()



class WizardStepAudioEncoder(wizard.WizardStep):
    glade_file = 'wizard_audio_encoder.glade'
    section = 'Conversion'
    component_name = 'audio-encoder'
    
    def get_next(self):
        return 'Consumption'



class WizardStepVorbis(WizardStepAudioEncoder):
    step_name = 'Vorbis'
    component_type = 'vorbis'



class WizardStepSpeex(WizardStepAudioEncoder):
    step_name = 'Speex'
    component_type = 'speex'



class WizardStepMulaw(WizardStepAudioEncoder):
    step_name = 'Mulaw'
    component_type = 'Mulaw'



class WizardStepConsumption(wizard.WizardStep):
    step_name = 'Consumption'
    glade_file = 'wizard_consumption.glade'
    section = 'Consumption'
    
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
            stepname = step.step_name
            if stepname in items and items[-1] != stepname:
                return items[items.index(stepname)+1]
            else:
                return 'Content License'



class WizardStepHTTP(wizard.WizardStep):
    glade_file = 'wizard_http.glade'
    section = 'Consumption'
    component_type = 'http-streamer'

    def get_next(self):
        return self.wizard['Consumption'].get_next(self)

    def get_component_properties(self):
        options = self.wizard.get_step_state(self)
        
        # XXX: Why ?? spinbutton.get_value ??
        options['bandwidth_limit'] = int(options['bandwidth_limit'])
        options['user_limit'] = int(options['user_limit'])
        options['port'] = int(options['port'])

        # XXX: Hack
        if options['worker'] == 0:
            options['worker'] = 'Local'
            
        return options


    
class WizardStepHTTPBoth(WizardStepHTTP):
    step_name = 'HTTP Streamer (audio & video)'
    component_name = 'http-streamer-audio+video'


                  
class WizardStepHTTPAudio(WizardStepHTTP):
    step_name = 'HTTP Streamer (audio only)'
    component_name = 'http-streamer-audio'



class WizardStepHTTPVideo(WizardStepHTTP):
    step_name = 'HTTP Streamer (video only)'
    component_name = 'http-streamer-video'

    

class WizardStepDisk(wizard.WizardStep):
    glade_file = 'wizard_disk.glade'
    section = 'Consumption'

    def setup(self):
        self.combobox_time_list.set_enum(RotateTime)
        self.combobox_size_list.set_enum(RotateSize)
        self.combobox_size_list.set_active(RotateSize.MB)
        
    def on_button_browse_clicked(self, button):
        pass
    
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
        
    def get_next(self):
        return self.wizard['Consumption'].get_next(self)



class WizardStepDiskBoth(WizardStepDisk):
    step_name = 'Disk (audio & video)'



class WizardStepDiskAudio(WizardStepDisk):
    step_name = 'Disk (audio only)'



class WizardStepDiskVideo(WizardStepDisk):
    step_name = 'Disk (video only)'



class WizardStepLicence(wizard.WizardStep):
    step_name = "Content License"
    glade_file = "wizard_license.glade"
    section = 'License'

    def on_checkbutton_set_license_toggled(self, button):
        self.combobox_license.set_sensitive(button.get_active())
        
    def get_next(self):
        return # WOHO, Finished!
