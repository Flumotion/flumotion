# -*- Mode: Python -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# flumotion/wizard/steps.py: a step in the wizard
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

import gtk
        
from flumotion.wizard.enums import * # XXX: fix later
from flumotion.wizard import wizard


class Welcome(wizard.WizardStep):
    step_name = 'Welcome'
    glade_file = 'wizard_welcome.glade'
    section = 'Welcome'
    section_name = 'Welcome'
    icon = 'wizard.png'
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
        
        # XXX: Default to something else
        self.combobox_video.set_active(VideoDevice.Test)
        self.combobox_audio.set_active(AudioDevice.Test)
        
    def on_checkbutton_has_video_toggled(self, button):
        self.combobox_video.set_sensitive(button.get_active())
        self.verify()
        
    def on_checkbutton_has_audio_toggled(self, button):
        self.combobox_audio.set_sensitive(button.get_active())
        self.verify()

    def verify(self):
        if (not self.checkbutton_has_audio and
            not self.checkbutton_has_video):
            self.wizard.block_next(True)
        else:
            self.wizard.block_next(False)

    def get_next(self):
        if self.checkbutton_has_video:
            video_source = self.combobox_video.get_active()
            return video_source.step
        elif self.checkbutton_has_audio:
            audio_source = self.combobox_audio.get_active()
            if audio_source == AudioDevice.Soundcard:
                return 'Audio Source'
            else:
                return 'Consumption'
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


class TVCard(VideoSource):
    step_name = 'TV Card'
    glade_file = 'wizard_tvcard.glade'
    component_type = 'bttv'
    icon = 'tv.png'
    
    def setup(self):
        self.combobox_device.set_enum(TVCardDevice)
        self.combobox_signal.set_enum(TVCardSignal)

    def get_component_properties(self):
        options = self.wizard.get_step_state(self)
        options['device'] = options['device'].name
        options['signal'] = options['signal'].name
        return options
wizard.register_step(TVCard)



class FireWire(VideoSource):
    step_name = 'Firewire'
    glade_file = 'wizard_firewire.glade'
    component_type = 'firewire'
    icon = 'firewire.png'
wizard.register_step(FireWire)



class Webcam(VideoSource):
    step_name = 'Webcam'
    glade_file = 'wizard_webcam.glade'
    component_type = 'video4linux'
    icon = 'webcam.png'
wizard.register_step(Webcam)


    
class TestSource(VideoSource):
    step_name = 'Test Source'
    glade_file = 'wizard_testsource.glade'
    component_type = 'videotestsrc'
    icon = 'testsource.png'
    
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
wizard.register_step(TestSource)



class Overlay(wizard.WizardStep):
    step_name = 'Overlay'
    glade_file = 'wizard_overlay.glade'
    section = 'Production'
    component_type = 'overlay'
    icon = 'overlay.png'
    
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
                return 'Audio Source'
        return 'Encoding'
wizard.register_step(Overlay)



# XXX: Rename to Soundcard
class AudioSource(wizard.WizardStep):
    step_name = 'Audio Source'
    glade_file = 'wizard_audiosource.glade'
    section = 'Production'
    component_type = 'osssrc'
    icon = 'audiosrc.png'
    
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
                    bitdepth=int(self.combobox_bitdepth.get_string()),
                    samplerate=int(self.combobox_samplerate.get_string()),
                    channels=channels,
                    input=self.combobox_input.get_string())

    def get_next(self):
        return 'Encoding'
wizard.register_step(AudioSource)



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
    
    # This is bound to both radiobutton_bitrate and radiobutton_quality
    def on_radiobutton_toggled(self, button):
        self.spinbutton_bitrate.set_sensitive(
            self.radiobutton_bitrate.get_active())
        self.spinbutton_quality.set_sensitive(
            self.radiobutton_quality.get_active())

    def get_next(self):
        return self.wizard['Encoding'].get_audio_page()
    
    def get_component_properties(self):
        options = self.wizard.get_step_state(self)
        options['bitrate'] = int(self.spinbutton_bitrate.get_value())
        options['quality'] = int(options['quality'])
        return options
    
wizard.register_step(Theora)



class Smoke(VideoEncoder):
    step_name = 'Smoke'
    glade_file = 'wizard_smoke.glade'
    section = 'Conversion'
    component_type = 'smoke'

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



class Vorbis(AudioEncoder):
    step_name = 'Vorbis'
    component_type = 'vorbis'
    icon = 'xiphfish.png'

    def setup(self):
        self.spinbutton_bitrate.set_range(6000, 250001)
        self.spinbutton_bitrate.set_value(64000)
        
    def get_component_properties(self):
        options = self.wizard.get_step_state(self)
        options['bitrate'] = int(self.spinbutton_bitrate.get_value())
        return options
wizard.register_step(Vorbis)



class Speex(AudioEncoder):
    step_name = 'Speex'
    component_type = 'speex'
    icon = 'xiphfish.png'
    
    def setup(self):
        self.spinbutton_bitrate.set_range(6000, 250001)
        self.spinbutton_bitrate.set_value(64000)
    def get_component_properties(self):
        options = self.wizard.get_step_state(self)
        options['bitrate'] = int(self.spinbutton_bitrate.get_value())
        return options
wizard.register_step(Speex)



class Consumption(wizard.WizardStep):
    step_name = 'Consumption'
    glade_file = 'wizard_consumption.glade'
    section = 'Consumption'
    section_name = 'Consumption'
    icon = 'consumption.png'

    def setup(self):
        # XXX: remove
        self.checkbutton_disk.set_active(True)
        
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
    port = 8800
wizard.register_step(HTTPBoth)
    
                  
class HTTPAudio(HTTP):
    step_name = 'HTTP Streamer (audio only)'
    sidebar_name = 'HTTP video'
    port = 8801
wizard.register_step(HTTPAudio)



class HTTPVideo(HTTP):
    step_name = 'HTTP Streamer (video only)'
    sidebar_name = 'HTTP audio'
    port = 8802
wizard.register_step(HTTPVideo)

    

class Disk(wizard.WizardStep):
    glade_file = 'wizard_disk.glade'
    section = 'Consumption'
    icon = 'kcmdevices.png'
    
    def setup(self):
        self.directory = '/tmp'
        
        self.tool_tip = gtk.Tooltips()
        self.tool_tip.set_tip(self.button_browse, 'Select a folder')
        
        self.combobox_time_list.set_enum(RotateTime)
        self.combobox_size_list.set_enum(RotateSize)
        self.radiobutton_has_time.set_active(True)
        self.spinbutton_time.set_value(12)
        self.combobox_time_list.set_active(RotateTime.Hours)


    def on_button_browse_clicked(self, button):
        fc = gtk.FileChooserDialog("Open..",
                                   None,
                                   gtk.FILE_CHOOSER_ACTION_SELECT_FOLDER,
                                   (gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL,
                                    gtk.STOCK_OPEN, gtk.RESPONSE_OK))
        fc.set_default_response(gtk.RESPONSE_OK)

        response = fc.run()
        if response == gtk.RESPONSE_OK:
            self.directory = fc.get_filename()
            if len(self.directory) >= 23:
                cut_filename = '...' + self.directory[-20:]
            else:
                cut_filename = self.directory
                
            self.tool_tip.set_tip(self.button_browse, self.directory)
            self.button_browse.set_label(cut_filename)
        else:
            self.tool_tip.set_tip(self.button_browse, 'Select a folder')
            
        fc.destroy()
    
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
            options['rotate_type'] = 'none'
        else:
            if self.radiobutton_has_time:
                options['rotate_type'] = 'time'
                unit = self.combobox_time_list.get_enum().unit
                options['time'] = long(self.spinbutton_time.get_value() * unit)
            elif self.radiobutton.has_size:
                options['rotate_type'] = 'size'
                unit = self.combobox_size_list.get_enum().unit
                options['size'] = long(self.spinbutton_size.get_value() * unit)

        options['directory'] = self.directory
        
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
    def setup(self):
        self.combobox_license.set_enum(LicenseType)
        
    def on_checkbutton_set_license_toggled(self, button):
        self.combobox_license.set_sensitive(button.get_active())
        
    def get_next(self):
        return # WOHO, Finished!
wizard.register_step(Licence)
