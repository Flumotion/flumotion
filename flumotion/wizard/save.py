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

from flumotion.wizard.enums import LicenseType
from flumotion.wizard.configurationwriter import ConfigurationWriter

_ = gettext.gettext
__version__ = "$Rev$"


class WizardSaver:
    def __init__(self, wizard):
        self.wizard = wizard
        self._flow_components = []
        self._atmosphere_components = []
        self._muxers = {}

    def _getVideoSource(self):
        source_step = self.wizard.get_step('Source')
        video_producer = source_step.get_video_producer()
        video_producer.name = 'producer-video'
        return video_producer

    def _getAudioSource(self, video_source):
        source_step = self.wizard.get_step('Source')
        audio_producer = source_step.get_audio_producer()

        if (video_source and
            video_source.component_type == audio_producer.component_type):
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
        if name in self._muxers:
            muxer = self._muxers[name]
        else:
            encoding_step = self.wizard.get_step('Encoding')
            muxer = encoding_step.get_muxer()
            muxer.name = 'muxer-' + name
            self._muxers[name] = muxer
        return muxer

    def _handleHTTPConsumer(self, step):
        name = step.getConsumerType()
        for server in step.getServerConsumers():
            server.name = 'http-server-%s' % (name,)
            self._flow_components.append(server)

        for porter in step.getPorters():
            porter.name = 'porter-%s' % (name,)
            self._atmosphere_components.append(porter)

    def _handleConsumers(self, audio_encoder, video_encoder):
        for step in self.wizard.getConsumtionSteps():
            consumer = step.getConsumerModel()
            if consumer.component_type == 'http-streamer':
                prefix = 'http'
                self._handleHTTPConsumer(step)
            elif consumer.component_type == 'disk-consumer':
                prefix = 'disk'
            elif consumer.component_type == 'shout2':
                prefix = 'shout2'
            else:
                raise AssertionError(consumer.component_type)

            consumerType = step.getConsumerType()
            # [disk,http,shout2]-[audio,video,audio-video]
            consumer.name = prefix + '-' + consumerType

            consumer.link(self._getMuxer(consumerType))
            self._flow_components.append(consumer)

        # Add & link the muxers we will use
        audio_muxer = self._getMuxer('audio')
        if audio_muxer.eaters:
            self._flow_components.append(audio_muxer)
            audio_muxer.link(audio_encoder)
        video_muxer = self._getMuxer('video')
        if video_muxer.eaters:
            self._flow_components.append(video_muxer)
            video_muxer.link(video_encoder)
        both_muxer = self._getMuxer('audio-video')
        if both_muxer.eaters:
            self._flow_components.append(both_muxer)
            both_muxer.link(video_encoder)
            both_muxer.link(audio_encoder)

    def _getVideoOverlay(self):
        step = self.wizard.get_step('Overlay')
        overlay = step.getOverlay()
        if not overlay:
            return None

        # At this point we already know that we should overlay something
        if overlay.show_logo:
            overlay.properties.fluendo_logo = True
            encoding_step = self.wizard.get_step('Encoding')
            if encoding_step.get_muxer_type() == 'ogg-muxer':
                overlay.properties.xiph_logo = True

            license_options = self.wizard.get_step_options('Content License')
            if (license_options['set-license'] and
                license_options['license'] == LicenseType.CC):
                overlay.properties.cc_logo = True

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

        self._handleConsumers(audio_encoder, video_encoder)

    def getXML(self):
        self._fetchComponentsFromWizardSteps()
        writer = ConfigurationWriter(self.wizard.flowName,
                                     self._flow_components,
                                     self._atmosphere_components)
        xml = writer.getXML()
        return xml
