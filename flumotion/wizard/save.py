# -*- Mode: Python; test-case-name: flumotion.test.test_wizard -*-
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

from flumotion.common import log
from flumotion.wizard import enums
from flumotion.configure import configure

# FIXME: This is absolutely /horrible/, we should not
#        use translatable string as constants when saving the
#        wizard configuration.
_ = N_ = gettext.gettext

def _fraction_from_float(number, denominator):
    """
    Return a string to be used in serializing to XML.
    """
    return "%d/%d" % (number * denominator, denominator)

class Component(log.Loggable):
    logCategory = "componentsave"

    def __init__(self, name, type, worker, properties={}):
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
            if source.type == 'firewire-producer':
                if self.name in ('encoder-video', 'overlay-video'):
                    feed = 'video'
                else:
                    feed = 'audio'
                s.append('%s:%s' % (source.name, feed))
            else:
                s.append(source.name)

        return s

    def toXML(self):
        """
        Write out the XML <component> section for this component.
        """
        extra = ' worker="%s"' % self.worker

        # FIXME: when the wizard can be split among projects, "project"
        # and "version" should be taken from the relevant project
        s = '    <component name="%s" type="%s" ' \
            'project="flumotion" version="%s"%s>\n' % (
            self.name, self.type, configure.version, extra)
        whoIsFeedingUs = self.getFeeders()
        if len(whoIsFeedingUs) > 0:
            s += '      <eater name="default">\n'
            for sourceName in whoIsFeedingUs:
                s += "        <feed>%s</feed>\n" % sourceName
            s += '      </eater>\n'

        if self.props:
            s += "\n"
            property_names = self.props.keys()
            property_names.sort()

            #import code; code.interact(local=locals())
            for name in property_names:
                value = self.props[name]
                s += '      <property name="%s">%s</property>\n' % (name, value)

        s += "    </component>\n"
        return s

    def printTree(self, indent=1):
        print indent * '*', self.name, self.type, \
              tuple([f.name for f in self.feeders]) or ''
        for eater in self.eaters:
            eater.printTree(indent+1)

class WizardSaver(log.Loggable):
    logCategory = 'wizard-saver'
    def __init__(self, wizard):
        self.wizard = wizard

    def getVideoSource(self):
        options = self.wizard.get_step_options(_('Source'))
        source = options['video']
        video_step = self.wizard.get_step(N_(source.step))

        if hasattr(video_step, 'worker'):
            properties = video_step.get_state()
            worker = video_step.worker
        else:
            properties = {}
            worker = self.wizard.get_step(_('Source')).worker

        self._set_fraction_property(properties, 'framerate', 10)

        return Component('producer-video', source.component_type, worker,
                         properties)

    def getVideoOverlay(self, video_source):
        step = self.wizard.get_step(_('Overlay'))
        properties = step.get_state()

        has_overlay = (step.can_overlay and
                       (properties['show-logo'] or
                        properties['show-text']))
        if not has_overlay:
            del properties['text']
            return

        properties['width'] = video_source.props['width']
        properties['height'] = video_source.props['height']

        # At this point we already know that we should overlay something
        if properties['show-logo']:
            properties['fluendo-logo'] = True
            encoding_options = self.wizard.get_step_options(_('Encoding'))
            if (encoding_options['format'] == enums.EncodingFormat.Ogg or
                encoding_options['video'] == enums.EncodingVideo.Theora):
                properties['xiph-logo'] = True

            license_options = self.wizard.get_step_options(_('Content License'))
            if (license_options['set-license']
                and license_options['license'] == enums.LicenseType.CC):
                properties['cc-logo'] = True

        # These were just used to pass capabilities; they shouldn't go into the
        # XML.
        del properties['show-logo']

        return Component('overlay-video', 'overlay-converter',
                         step.worker, properties)

    def _set_fraction_property(self, properties, property_name, denominator):
        if not property_name in properties:
            return

        framerate = _fraction_from_float(int(properties[property_name]),
                                         denominator)
        properties[property_name] = framerate

    def getVideoEncoder(self):
        options = self.wizard.get_step_options(_('Encoding'))
        encoder = options['video']
        encoder_step = self.wizard.get_step(N_(encoder.step))

        properties = encoder_step.get_state()
        return Component('encoder-video', encoder.component_type,
                         encoder_step.worker,
                         properties)

    def getAudioSource(self, video_source):
        options = self.wizard.get_step_options(_('Source'))
        source = options['audio']

        # If we selected firewire and have selected video
        # and the selected video is Firewire,
        #   return the source
        if (source == enums.AudioDevice.Firewire and video_source and
            options['video'] == enums.VideoDevice.Firewire):
            return video_source


        audio_step = self.wizard.get_step(N_(source.step))

        if hasattr(audio_step, 'worker'):
            properties = audio_step.get_state()
            worker = audio_step.worker
        else:
            properties = {}
            worker = self.wizard.get_step(_('Source')).worker

        self._set_fraction_property(properties, 'framerate', 10)

        return Component('producer-audio', source.component_type, worker,
                         properties)

    def getAudioEncoder(self):
        options = self.wizard.get_step_options(_('Encoding'))
        encoder = options['audio']

        if encoder == enums.EncodingAudio.Mulaw:
            props = {}
            worker = self.wizard.get_step(_('Source')).worker
        else:
            encoder_step = self.wizard.get_step(N_(encoder.step))
            props = encoder_step.get_state()
            worker = encoder_step.worker

        return Component('encoder-audio', encoder.component_type, worker, props)

    def getMuxer(self, name):
        options = self.wizard.get_step_options(_('Encoding'))
        step = self.wizard.get_step(_('Encoding'))
        muxer = options['format']
        return Component('muxer-' + name, muxer.component_type,
                         step.worker)

    def handleVideo(self, components):
        video_source = self.getVideoSource()
        components.append(video_source)

        video_encoder = self.getVideoEncoder()
        components.append(video_encoder)

        video_overlay = self.getVideoOverlay(video_source)
        if video_overlay:
            video_overlay.link(video_source)
            video_encoder.link(video_overlay)
            components.append(video_overlay)
        else:
            video_encoder.link(video_source)
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
        cons_options = self.wizard.get_step_options(_('Consumption'))
        has_audio = self.wizard.get_step_option(_('Source'), 'has-audio')
        has_video = self.wizard.get_step_option(_('Source'), 'has-video')

        audio_muxer = self.getMuxer('audio')
        video_muxer = self.getMuxer('video')
        both_muxer = self.getMuxer('audio-video')

        steps = []
        if has_audio and has_video:
            if cons_options['http']:
                if cons_options['http-audio-video']:
                    steps.append(('http-audio-video',
                                  'http-streamer',
                                  'HTTP Streamer (audio & video)',
                                  both_muxer))
                if cons_options['http-audio']:
                    steps.append(('http-audio', 'http-streamer',
                                  'HTTP Streamer (audio only)',
                                  audio_muxer))
                if cons_options['http-video']:
                    steps.append(('http-video', 'http-streamer',
                                  'HTTP Streamer (video only)',
                                  video_muxer))
            if cons_options['disk']:
                if cons_options['disk-audio-video']:
                    steps.append(('disk-audio-video',
                                  'disk-consumer',
                                  'Disk (audio & video)',
                                  both_muxer))
                if cons_options['disk-audio']:
                    steps.append(('disk-audio', 'disk-consumer',
                                  'Disk (audio only)', audio_muxer))
                if cons_options['disk-video']:
                    steps.append(('disk-video', 'disk-consumer',
                                  'Disk (video only)', video_muxer))
            if cons_options['shout2']:
                if cons_options['shout2-audio-video']:
                    steps.append(('shout2-audio-video', 'shout2-consumer',
                                  'Icecast streamer (audio & video)',
                                  both_muxer))
                if cons_options['shout2-audio']:
                    steps.append(('shout2-audio', 'shout2-consumer',
                                  'Icecast streamer (audio only)',
                                  audio_muxer))
                if cons_options['shout2-video']:
                    steps.append(('shout2-video', 'shout2-consumer',
                                  'Icecast streamer (video only)',
                                  video_muxer))
        elif has_video and not has_audio:
            if cons_options['http']:
                steps.append(('http-video', 'http-streamer',
                              'HTTP Streamer (video only)', video_muxer))
            if cons_options['disk']:
                steps.append(('disk-video', 'disk-consumer',
                              'Disk (video only)', video_muxer))
            if cons_options['shout2']:
                steps.append(('shout2-video', 'shout2-consumer',
                              'Icecast streamer (video only)', video_muxer))
        elif has_audio and not has_video:
            if cons_options['http']:
                steps.append(('http-audio', 'http-streamer',
                              'HTTP Streamer (audio only)', audio_muxer))
            if cons_options['disk']:
                steps.append(('disk-audio', 'disk-consumer',
                              'Disk (audio only)', audio_muxer))
            if cons_options['shout2']:
                steps.append(('shout2', 'shout2-consumer',
                              'Icecast streamer (audio only)', audio_muxer))
        else:
            raise AssertionError

        for name, comp_type, step_name, muxer in steps:
            if not cons_options.has_key(name):
                continue
            step = self.wizard.get_step(N_(step_name))
            consumer = Component(name, comp_type, step.worker,
                                 step.get_state())
            consumer.link(muxer)
            components.append(consumer)

        # Add & link the muxers we will use
        if audio_muxer and audio_muxer.eaters:
            components.append(audio_muxer)
            audio_muxer.link(audio_encoder)
        if video_muxer and video_muxer.eaters:
            components.append(video_muxer)
            video_muxer.link(video_encoder)
        if both_muxer and both_muxer.eaters:
            components.append(both_muxer)
            both_muxer.link(video_encoder)
            both_muxer.link(audio_encoder)

    def getComponents(self):
        source_options = self.wizard.get_step_options(_('Source'))
        has_video = source_options['has-video']
        has_audio = source_options['has-audio']

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
        self.debug('Got %d components' % len(components))

        s = '<planet>\n'
        s += '  <flow name="%s">\n' % self.wizard.flowName
        for component in components:
            s += component.toXML() + "\n"
        s += '  </flow>\n'
        s += '</planet>\n'

        return s
