from flumotion.wizard.enums import *

video_source_components = { VideoDevice.TVCard    : 'tv-card',
                            VideoDevice.Firewire  : 'firewire',
                            VideoDevice.Webcam    : 'webcam',
                            VideoDevice.Test      : 'videotestsrc' }
audio_source_components = { AudioDevice.Firewire  : 'audio-firewire',
                            AudioDevice.Soundcard : 'alsasrc',
                            AudioDevice.Test      : 'sinesrc' }

class Component:
    def __init__(self, name, type, properties={}):
        self.name = name
        self.type = type
        self.props = properties
        self.eaters = []
        self.feeders = []
        
    def __repr__(self):
        return '<flumotion.wizard.save.Component name="%s">' % self.name

    def addEater(self, component):
        self.eaters.append(component)
        
    def addFeeder(self, component):
        self.feeders.append(component)
        component.addEater(self)

    def toXML(self):
        s = '    <component name="%s" type="%s">\n' % (self.name, self.type)

        if len(self.eaters) == 1:
            s += '      <feed>default</feed>\n'
        else:
            for feed_name in self.eaters:
                s += "      <feed>%s</feed>\n" % source.feed_name
                
        for source in self.feeders:
            s += "      <source>%s</source>\n" % source.name

        if self.props:
            s += "      <!-- properties -->\n"
            for name, value in self.props.items():
                s += "      <%s>%s</%s>\n" % (name, value, name)
            
        s += "    </component>"
        return s
    
    def printTree(self, indent=1):
        print indent * '*', self.name, self.type, \
              tuple([f.name for f in self.feeders]) or ''
        for eater in self.eaters:
            eater.printTree(indent+1)
            
class WizardSaver:
    def __init__(self, wizard):
        self.wizard = wizard

    def getVideoSource(self):
        options = self.wizard.get_step_options('Source')
        source = options['video']
        video_step = self.wizard[source.step]
        return Component('video-source', source.component_type,
                         video_step.get_component_properties())

    def getVideoOverlay(self, video_step):
        step = self.wizard['Overlay']
        video_props = video_step.get_component_properties()
        properties = step.get_component_properties()
        properties['width'] = video_props['width']
        properties['height'] = video_props['height']
        return Component('video-overlay', 'overlay', properties)
        
    def getVideoEncoder(self):
        options = self.wizard.get_step_options('Encoding')
        encoder = options['video']
        encoder_step = self.wizard[encoder.step]
        return Component('video-encoder', encoder.component_type,
                         encoder_step.get_component_properties())

    def getAudioSource(self):
        options = self.wizard.get_step_options('Source')
        source = options['audio']
        audio_step = self.wizard['Audio Source']
        return Component('audio-source', source.component_type,
                         audio_step.get_component_properties())

    def getAudioEncoder(self):
        options = self.wizard.get_step_options('Encoding')
        encoder = options['audio']
        
        if encoder == EncodingAudio.Mulaw:
            props = {}
        else:
            encoder_step = self.wizard[encoder.step]
            props = encoder_step.get_component_properties()
            
        return Component('audio-encoder', encoder.component_type, props)

    def getMuxer(self):
        options = self.wizard.get_step_options('Encoding')
        muxer = options['format']
        return Component('multiplexer', muxer.component_type)

    def handleVideo(self, muxer, components):
        overlay_options = self.wizard.get_step_options('Overlay')
        has_overlay = overlay_options['show_logo'] or \
                      overlay_options['show_text']
        
        video_source =  self.getVideoSource()
        components.append(video_source)
            
        video_overlay = None
        video_encoder = self.getVideoEncoder()
            
        if has_overlay:
            video_overlay = self.getVideoOverlay(video_source)
            components.append(video_overlay)
                
        if video_overlay is not None:
            video_overlay.addFeeder(video_source)
            video_encoder.addFeeder(video_overlay)
        else:
            video_encoder.addFeeder(video_source)

        components.append(video_encoder)
        muxer.addFeeder(video_encoder)
            
    def handleAudio(self, muxer, components):
        audio_source = self.getAudioSource()
        components.append(audio_source)

        audio_decoder = self.getAudioEncoder()
        components.append(audio_decoder)
        audio_decoder.addFeeder(audio_source)
            
        muxer.addFeeder(audio_decoder)

    def handleConsumers(self, muxer, components):
        cons_options = self.wizard.get_step_options('Consumption')
        has_audio = self.wizard.get_step_option('Source', 'has_audio')
        has_video = self.wizard.get_step_option('Source', 'has_video')
        
        steps = []
        if has_audio and has_video:
            if cons_options['http']:
                if cons_options['http_audio_video']:
                    steps.append(('http_audio_video', 'http-audio-video',
                          'http-streamer', 'HTTP Streamer (audio & video)'))
                if cons_options['http_audio']:
                    steps.append(('http_audio', 'http-audio', 'http-streamer',
                                  'HTTP Streamer (audio only)'))
                if cons_options['http_video']:
                    steps.append(('http_video', 'http-video', 'http-streamer',
                                  'HTTP Streamer (video only)'))
            if cons_options['disk']:
                if cons_options['disk_audio_video']:
                    steps.append(('disk_audio_video', 'disk-audio-video',
                                  'file-dumper', 'Disk (audio & video)'))
                if cons_options['disk_audio']:
                    steps.append(('disk_audio', 'disk-audio', 'file-dumper',
                                  'Disk (audio only)'))
                if cons_options['disk_video']:
                    steps.append(('disk_video', 'disk-video', 'file-dumper',
                                  'Disk (video only)'))
        elif has_video and not has_audio:
            if cons_options['http']:
                steps.append(('http_video', 'http-video', 'http-streamer',
                              'HTTP Streamer (video only)'))
            if cons_options['disk']:
                steps.append(('disk_video', 'disk-video', 'file-dumper',
                              'Disk (video only)'))
        elif has_audio and not has_video:
            if cons_options['http']:
                steps.append(('http_audio', 'http-audio', 'http-streamer',
                              'HTTP Streamer (audio only)'))
            if cons_options['disk']:
                steps.append(('disk_audio', 'disk-audio', 'file-dumper',
                              'Disk (audio only)'))
        else:
            raise AssertionError

        for key, name, type, step_name in steps:
            if not cons_options.has_key(key):
                continue
            step = self.wizard[step_name]
            comp = Component(name, type, step.get_component_properties())
            comp.addFeeder(muxer)
            components.append(comp)
        
    def save(self):
        source_options = self.wizard.get_step_options('Source')
        has_video = source_options['has_video']
        has_audio = source_options['has_audio']

        components = []
        
        muxer = self.getMuxer()

        if has_video:
            self.handleVideo(muxer, components)

        if has_audio:
            self.handleAudio(muxer, components)

        # Append muxer here, so we get them in "correct" order, in the
        # gstreamer pipeline point of view, left to right.
        components.append(muxer)

        self.handleConsumers(muxer, components)

        print '<planet>'
        
        print '  <atmosphere>'
        for component in components:
            print component.toXML()
        print '  </atmosphere>'
        print '</planet>'
        
