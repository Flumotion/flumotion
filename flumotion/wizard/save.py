# -*- Mode: Python; test-case-name: flumotion.test.test_wizard -*-
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

from flumotion.common import log, registry
from flumotion.wizard import enums
from flumotion.configure import configure

class Component(log.Loggable):
    logCategory = "componentsave"

    def __init__(self, name, type, properties={}, worker=None):
        self.debug('Creating component %s (%s) worker=%r' % (
            name, type, worker))
        self.name = name
        self.type = type
        self.props = properties
        self.worker = worker
        self.eaters = []
        self.feeders = []
        
    def __repr__(self):
        return '<flumotion.wizard.save.Component name="%s">' % self.name

    def addEater(self, component):
        self.eaters.append(component)
        
    def addFeeder(self, component):
        self.feeders.append(component)

    def link(self, component):
        self.feeders.append(component)
        component.addEater(self)

    def getFeeders(self):
        s = []
        for source in self.feeders:
            if source.type == 'firewire':
                if self.name in ('video-encoder', 'video-overlay'):
                    feed = 'video'
                else:
                    feed = 'audio'
                s.append('%s:%s' % (source.name, feed))
            else:
                s.append(source.name)
                
        return s
    
    def toXML(self, registry):
        """
        Write out the XML <component> section for this component.

        @type registry: L{flumotion.common.registry.ComponentRegistry}
        """
        regentry = registry.getComponent(self.type)

        if self.worker:
            extra = ' worker="%s"' % self.worker
        else:
            extra = ''
            
        # FIXME: when the wizard can be split among projects, "project"
        # and "version" should be taken from the relevant project
        s = '    <component name="%s" type="%s" ' \
            'project="flumotion" version="%s"%s>\n' % (
            self.name, self.type, configure.version, extra)

        for sourceName in self.getFeeders():
            s += "      <source>%s</source>\n" % sourceName
                    
        if self.props:
            s += "      <!-- properties -->\n"
            property_names = self.props.keys()
            property_names.sort()
            
            #import code; code.interact(local=locals())
            for name in property_names:
                # FIXME: warn if a property name is not in the registry
                # change to a more visible warning once we fix all of these
                if not regentry.hasProperty(name):
                    self.debug('WARNING: property named %s in component '
                        'config, but not in registry.  Fix wizard !' % name)
                    continue
                value = self.props[name]
                s += '      <property name="%s">%s</property>\n' % (name, value)
            
        s += "    </component>\n"
        return s
    
    def printTree(self, indent=1):
        print indent * '*', self.name, self.type, \
              tuple([f.name for f in self.feeders]) or ''
        for eater in self.eaters:
            eater.printTree(indent+1)

class WizardSaver:
    def __init__(self, wizard):
        self.wizard = wizard
        self.registry = registry.getRegistry()

    def getVideoSource(self):
        options = self.wizard.get_step_options('Source')
        source = options['video']
        video_step = self.wizard[source.step]
        
        if hasattr(video_step, 'worker'):
            props = video_step.get_component_properties()
            worker = video_step.worker
        else:
            props = {}
            worker = self.wizard['Source'].worker

        return Component('video-source', source.component_type, props, worker)

    def getVideoOverlay(self, show_logo):
        # At this point we already know that we should overlay something
        step = self.wizard['Overlay']
        properties = step.get_component_properties()
        if show_logo:
            properties['fluendo_logo'] = True
            encoding_options = self.wizard.get_step_options('Encoding')
            if (encoding_options['format'] == enums.EncodingFormat.Ogg or
                encoding_options['video'] == enums.EncodingVideo.Theora):
                properties['xiph_logo'] = True

            license_options = self.wizard.get_step_options('Content License')
            if (license_options['set_license']
                and license_options['license'] == enums.LicenseType.CC):
                properties['cc_logo'] = True
            
        return Component('video-overlay', 'overlay', properties, step.worker)
        
    def getVideoEncoder(self):
        options = self.wizard.get_step_options('Encoding')
        encoder = options['video']
        encoder_step = self.wizard[encoder.step]
        return Component('video-encoder', encoder.component_type,
                         encoder_step.get_component_properties(),
                         encoder_step.worker)

    def getAudioSource(self, video_source):
        options = self.wizard.get_step_options('Source')
        source = options['audio']
        
        # If we selected firewire and have selected video
        # and the selected video is Firewire,
        #   return the source
        if (source == enums.AudioDevice.Firewire and video_source and
            options['video'] == enums.VideoDevice.Firewire):
            return video_source
        
        props = {}
        
        audio_step = self.wizard[source.step]
        
        if hasattr(audio_step, 'worker'):
            props = audio_step.get_component_properties()
            worker = audio_step.worker
        else:
            worker = self.wizard['Source'].worker
        
        return Component('audio-source', source.component_type, props, worker)

    def getAudioEncoder(self):
        options = self.wizard.get_step_options('Encoding')
        encoder = options['audio']
        
        if encoder == enums.EncodingAudio.Mulaw:
            props = {}
            # FIXME
            worker = None 
        else:
            encoder_step = self.wizard[encoder.step]
            props = encoder_step.get_component_properties()
            worker = encoder_step.worker
            
        return Component('audio-encoder', encoder.component_type, props, worker)

    def getMuxer(self, name):
        options = self.wizard.get_step_options('Encoding')
        step = self.wizard['Encoding']
        muxer = options['format']
        return Component('muxer-' + name, muxer.component_type,
                         worker=step.worker)

    def handleVideo(self, components):
        overlay_options = self.wizard.get_step_options('Overlay')
        has_overlay = (overlay_options['can_overlay'] and
                       (overlay_options['show_logo'] or
                        overlay_options['show_text']))
        
        video_source =  self.getVideoSource()
        components.append(video_source)
            
        video_overlay = None
        video_encoder = self.getVideoEncoder()
            
        if has_overlay:
            video_overlay = self.getVideoOverlay(overlay_options['show_logo'])
            components.append(video_overlay)
                
        if video_overlay != None:
            video_overlay.link(video_source)
            video_encoder.link(video_overlay)
        else:
            video_encoder.link(video_source)
        components.append(video_encoder)
        return video_encoder, video_source
            
    def handleAudio(self, components, video_source):
        audio_source = self.getAudioSource(video_source)
        # In case of firewire component, which can already be there
        if not audio_source in components:
            components.append(audio_source)
            
        audio_encoder = self.getAudioEncoder()
        components.append(audio_encoder)
        audio_encoder.link(audio_source)

        return audio_encoder
    
    def handleConsumers(self, components, audio_encoder, video_encoder):
        cons_options = self.wizard.get_step_options('Consumption')
        has_audio = self.wizard.get_step_option('Source', 'has_audio')
        has_video = self.wizard.get_step_option('Source', 'has_video')

        audio_muxer = None
        if has_audio:
            audio_muxer = self.getMuxer('audio')
            components.append(audio_muxer)
            audio_muxer.link(audio_encoder)
            
        video_muxer = None
        if has_video:
            video_muxer = self.getMuxer('video')
            components.append(video_muxer)
            video_muxer.link(video_encoder)

        steps = []
        both_muxer = None
        if has_audio and has_video:
            both_muxer = self.getMuxer('audio-video')
            components.append(both_muxer)
            both_muxer.link(video_encoder)
            both_muxer.link(audio_encoder)
            
            if cons_options['http']:
                if cons_options['http_audio_video']:
                    steps.append(('http_audio_video', 'http-audio-video',
                                  'http-streamer',
                                  'HTTP Streamer (audio & video)', both_muxer))
                if cons_options['http_audio']:
                    steps.append(('http_audio', 'http-audio', 'http-streamer',
                                  'HTTP Streamer (audio only)', audio_muxer))
                if cons_options['http_video']:
                    steps.append(('http_video', 'http-video', 'http-streamer',
                                  'HTTP Streamer (video only)', video_muxer))
            if cons_options['disk']:
                if cons_options['disk_audio_video']:
                    steps.append(('disk_audio_video', 'disk-audio-video',
                                  'disker', 'Disk (audio & video)',
                                  both_muxer))
                if cons_options['disk_audio']:
                    steps.append(('disk_audio', 'disk-audio', 'disker',
                                  'Disk (audio only)', audio_muxer))
                if cons_options['disk_video']:
                    steps.append(('disk_video', 'disk-video', 'disker',
                                  'Disk (video only)', video_muxer))
        elif has_video and not has_audio:
            if cons_options['http']:
                steps.append(('http_video', 'http-video', 'http-streamer',
                              'HTTP Streamer (video only)', video_muxer))
            if cons_options['disk']:
                steps.append(('disk_video', 'disk-video', 'disker',
                              'Disk (video only)', video_muxer))
        elif has_audio and not has_video:
            if cons_options['http']:
                steps.append(('http_audio', 'http-audio', 'http-streamer',
                              'HTTP Streamer (audio only)', audio_muxer))
            if cons_options['disk']:
                steps.append(('disk_audio', 'disk-audio', 'disker',
                              'Disk (audio only)', audio_muxer))
        else:
            raise AssertionError

        for key, name, type, step_name, muxer in steps:
            if not cons_options.has_key(key):
                continue
            step = self.wizard[step_name]
            consumer = Component(name, type, step.get_component_properties(),
                                 step.worker)
            consumer.link(muxer)
            components.append(consumer)

        # Removed unused ones
        if audio_muxer and not audio_muxer.eaters:
            components.remove(audio_muxer)
        if video_muxer and not video_muxer.eaters:
            components.remove(video_muxer)
        if both_muxer and not both_muxer.eaters:
            components.remove(both_muxer)

    def getComponents(self):
        source_options = self.wizard.get_step_options('Source')
        has_video = source_options['has_video']
        has_audio = source_options['has_audio']

        components = []
        
        video_encoder = None
        video_source = None
        if has_video:
            video_encoder, video_source = self.handleVideo(components)

        # Must do audio after video, in case of a firewire audio component
        # is selected together with a firewire video component
        audio_encoder = None
        if has_audio:
            audio_encoder = self.handleAudio(components, video_source)
            
        self.handleConsumers(components, audio_encoder, video_encoder)

        return components
    
    def getXML(self):
        # FIXME: allow for naming flows !
        components = self.getComponents()
        
        s = '<planet>\n'
        s += '  <flow name="%s">\n' % self.wizard.flowName
        for component in components:
            s += component.toXML(self.registry)
        s += '  </flow>\n'
        s += '</planet>\n'

        return s

