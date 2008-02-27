# -*- Mode: Python; test-case-name: flumotion.test.test_wizard -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# Flumotion - a streaming media server
# Copyright (C) 2004,2005,2006,2007,2008 Fluendo, S.L. (www.fluendo.com).
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
from flumotion.wizard.enums import LicenseType
from flumotion.wizard.configurationwriter import ConfigurationWriter

_ = gettext.gettext
__version__ = "$Rev$"


class Component(log.Loggable):
    logCategory = "componentsave"

    def __init__(self, name, component_type, worker, properties=None, plugs=None):
        self.debug('Creating component %s (%s) worker=%r' % (
            name, type, worker))
        self.name = name
        self.component_type = component_type
        if not properties:
            properties = {}
        self.props = properties
        if not plugs:
            plugs = []
        self.plugs = plugs
        self.worker = worker
        self.eaters = []
        self.feeders = []

    def __repr__(self):
        return '<flumotion.wizard.save.Component name="%s">' % self.name

    def link(self, component):
        self.feeders.append(component)
        component.eaters.append(self)

    def getProperties(self):
        return self.props

    def getFeeders(self):
        for source in self.feeders:
            yield source.name


class WizardSaver(log.Loggable):
    logCategory = 'wizard-saver'
    def __init__(self, wizard):
        self.wizard = wizard
        self._flow_components = []
        self._atmosphere_components = []

    def _getVideoSource(self):
        source_step = self.wizard.get_step('Source')
        video_producer = source_step.get_video_producer()
        video_producer.name = 'producer-video'
        return video_producer

    def _getAudioSource(self, video_source):
        source_step = self.wizard.get_step('Source')
        audio_producer = source_step.get_audio_producer()

        # If we selected firewire and have selected video
        # and the selected video is Firewire,
        #   return the source
        if (audio_producer.component_type == 'firewire-producer' and
            video_source and
            video_source.component_type == 'firewire-producer'):
            return video_source

        audio_producer.name = 'producer-audio'
        return audio_producer

    def _getVideoEncoder(self):
        encoding_step = self.wizard.get_step('Encoding')
        video_encoder = encoding_step.get_video_encoder()
        video_encoder.name = 'encoder-video'
        return video_encoder

    def _getAudioEncoder(self):
        encoding_step = self.wizard.get_step('Encoding')
        audio_encoder = encoding_step.get_audio_encoder()
        audio_encoder.name = 'encoder-audio'
        return audio_encoder

    def _getMuxer(self, name):
        encoding_step = self.wizard.get_step('Encoding')
        muxer = encoding_step.get_muxer()
        muxer.name = 'muxer-' + name
        return muxer

    def _handleHTTPConsumer(self, name, step):
        name = name[5:] # strip http, we'll add it manually
        for server in step.getServerConsumers():
            server.name = 'http-server-%s' % (name,)
            self._flow_components.append(server)

        for porter in step.getPorters():
            porter.name = 'porter-%s' % (name,)
            self._atmosphere_components.append(porter)

        streamer = step.getStreamerConsumer()
        streamer.name = 'http-%s' % (name,)
        return streamer

    def _handleDiskerConsumer(self, name, step):
        disker = step.getDisker()
        disker.name = name
        return disker

    def _getVideoOverlay(self):
        step = self.wizard.get_step('Overlay')
        overlay = step.getOverlay()
        if not overlay:
            return None
        properties = overlay.getProperties()

        # At this point we already know that we should overlay something
        if overlay.show_logo:
            properties.fluendo_logo = True
            encoding_step = self.wizard.get_step('Encoding')
            if encoding_step.get_muxer_type() == 'ogg-muxer':
                properties.xiph_logo = True

            license_options = self.wizard.get_step_options('Content License')
            if (license_options['set-license'] and
                license_options['license'] == LicenseType.CC):
                properties.cc_logo = True

        overlay.name = 'overlay-video'
        return overlay

    def handleVideo(self):
        video_source = self._getVideoSource()
        self._flow_components.append(video_source)

        video_encoder = self._getVideoEncoder()
        self._flow_components.append(video_encoder)

        video_overlay = self._getVideoOverlay()
        if video_overlay:
            video_overlay.link(video_source)
            video_encoder.link(video_overlay)
            self._flow_components.append(video_overlay)
        else:
            video_encoder.link(video_source)
        return video_encoder, video_source

    def handleAudio(self, video_source):
        audio_source = self._getAudioSource(video_source)
        # In case of firewire component, which can already be there
        if not audio_source in self._flow_components:
            self._flow_components.append(audio_source)

        audio_encoder = self._getAudioEncoder()
        self._flow_components.append(audio_encoder)
        audio_encoder.link(audio_source)

        return audio_encoder

    def handleConsumers(self, audio_encoder, video_encoder):
        cons_options = self.wizard.get_step_options('Consumption')
        has_audio = self.wizard.get_step_option('Source', 'has-audio')
        has_video = self.wizard.get_step_option('Source', 'has-video')

        audio_muxer = self._getMuxer('audio')
        video_muxer = self._getMuxer('video')
        both_muxer = self._getMuxer('audio-video')

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
            step = self.wizard.get_step(step_name)
            if comp_type == 'http-streamer':
                consumer = self._handleHTTPConsumer(name, step)
            elif comp_type == 'disk-consumer':
                consumer = self._handleDiskerConsumer(name, step)
            else:
                consumer = Component(
                    name, comp_type,
                    step.worker, step.get_state())

            consumer.link(muxer)
            self._flow_components.append(consumer)

        # Add & link the muxers we will use
        if audio_muxer and audio_muxer.eaters:
            self._flow_components.append(audio_muxer)
            audio_muxer.link(audio_encoder)
        if video_muxer and video_muxer.eaters:
            self._flow_components.append(video_muxer)
            video_muxer.link(video_encoder)
        if both_muxer and both_muxer.eaters:
            self._flow_components.append(both_muxer)
            both_muxer.link(video_encoder)
            both_muxer.link(audio_encoder)

    def _fetchComponentsFromWizardSteps(self):
        source_options = self.wizard.get_step_options('Source')
        has_video = source_options['has-video']
        has_audio = source_options['has-audio']

        video_encoder = None
        video_source = None
        if has_video:
            video_encoder, video_source = self.handleVideo()

        # Must do audio after video, in case of a firewire audio component
        # is selected together with a firewire video component
        audio_encoder = None
        if has_audio:
            audio_encoder = self.handleAudio(video_source)

        self.handleConsumers(audio_encoder, video_encoder)

    def getXML(self):
        self._fetchComponentsFromWizardSteps()
        writer = ConfigurationWriter(self.wizard.flowName,
                                     self._flow_components,
                                     self._atmosphere_components)
        xml = writer.getXML()
        return xml
