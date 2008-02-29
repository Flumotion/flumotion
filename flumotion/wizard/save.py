4# -*- Mode: Python; test-case-name: flumotion.test.test_wizard -*-
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

from flumotion.wizard.configurationwriter import ConfigurationWriter
from flumotion.wizard.models import Muxer, AudioProducer, VideoProducer, \
     AudioEncoder, VideoEncoder

_ = gettext.gettext
__version__ = "$Rev$"


class WizardSaver:
    def __init__(self):
        self._flowComponents = []
        self._atmosphereComponents = []
        self._muxers = {}
        self._flowName = None
        self._audioProducer = None
        self._videoProducer = None
        self._audioEncoder = None
        self._videoEncoder = None
        self._videoOverlay = None
        self._useCCLicense = False
        self._muxerType = None
        self._muxerWorker = None

    # Public API

    def setFlowName(self, flowName):
        """Sets the name of the flow we're saving.
        @param flowName:
        @type flowName: string
        """
        self._flowName = flowName

    def setAudioProducer(self, audioProducer):
        """Attach a audio producer for this flow
        @param audioProducer: audio producer
        @type audioProducer: L{AudioProducer} subclass or None
        """
        if (audioProducer is not None and
            not isinstance(audioProducer, AudioProducer)):
            raise TypeError(
                "audioProducer must be a AudioProducer subclass, not %r" % (
                audioProducer,))
        self._audioProducer = audioProducer

    def setVideoProducer(self, videoProducer):
        """Attach a video producer for this flow
        @param videoProducer: video producer
        @type videoProducer: L{VideoProducer} subclass or None
        """
        if (videoProducer is not None and
            not isinstance(videoProducer, VideoProducer)):
            raise TypeError(
                "videoProducer must be a VideoProducer subclass, not %r" % (
                videoProducer,))
        self._videoProducer = videoProducer

    def setVideoOverlay(self, videoOverlay):
        self._videoOverlay = videoOverlay

    def setAudioEncoder(self, audioEncoder):
        """Attach a audio encoder for this flow
        @param audioEncoder: audio encoder
        @type audioEncoder: L{AudioEncoder} subclass or None
        """
        if (audioEncoder is not None and
            not isinstance(audioEncoder, AudioEncoder)):
            raise TypeError(
                "audioEncoder must be a AudioEncoder subclass, not %r" % (
                audioEncoder,))
        self._audioEncoder = audioEncoder

    def setVideoEncoder(self, videoEncoder):
        """Attach a video encoder for this flow
        @param videoEncoder: video encoder
        @type videoEncoder: L{VideoEncoder} subclass or None
        """
        if (videoEncoder is not None and
            not isinstance(videoEncoder, VideoEncoder)):
            raise TypeError(
                "videoEncoder must be a VideoEncoder subclass, not %r" % (
                videoEncoder,))
        self._videoEncoder = videoEncoder

    def setMuxer(self, muxerType, muxerWorker):
        """Adds the necessary state to be able to create a muxer
        for this flow.
        @param muxerType:
        @type muxerType: string
        @param muxerWorker: name of the worker
        @type muxerWorker: string
        """
        self._muxerType = muxerType
        self._muxerWorker = muxerWorker

    def addServerConsumer(self, server, consumerType):
        """Add a server consumer. Currently limited a to http-server
        server consumers
        @param server: server consumer
        @type server:
        @param consumerType: the type of the consumer, one of
          audio/video/audio-video
        @type consumerType: string
        """
        # FIXME: Do not hard code to http-server here
        server.name = 'http-server-%s' % (consumerType,)
        self._flowComponents.append(server)

    def addPorter(self, porter, consumerType):
        """Add a porter
        @param porter: porter
        @type porter:
        @param consumerType: the type of the consumer, one of
          audio/video/audio-video
        @type consumerType: string
        """
        porter.name = 'porter-%s' % (consumerType,)
        self._atmosphereComponents.append(porter)

    def addConsumer(self, consumer, consumerType):
        """Add a consumer
        @param consumer: consumer
        @type consumer:
        @param consumerType: the type of the consumer, one of
          audio/video/audio-video
        @type consumerType: string
        """
        if consumer.component_type == 'http-streamer':
            prefix = 'http'
        elif consumer.component_type == 'disk-consumer':
            prefix = 'disk'
        elif consumer.component_type == 'shout2':
            prefix = 'shout2'

        # [disk,http,shout2]-[audio,video,audio-video]
        consumer.name = prefix + '-' + consumerType

        consumer.link(self._getMuxer(consumerType))
        self._flowComponents.append(consumer)

    def setUseCCLicense(self, useCCLicense):
        """Sets if we should use a Creative Common license on
        the created flow. This will overlay an image if we do
        video streaming.
        @param useCCLicense: if we should use a CC license
        @type useCCLicense: bool
        """
        self._useCCLicense = useCCLicense

    def getXML(self):
        """Creates an XML configuration of the state set
        @returns: the xml configuration
        @rtype: string
        """
        self._handleAudio()
        self._handleVideo()
        self._handleConsumers()
        writer = ConfigurationWriter(self._flowName,
                                     self._flowComponents,
                                     self._atmosphereComponents)
        xml = writer.getXML()
        return xml

    # Private API

    def _getMuxer(self, name):
        if name in self._muxers:
            muxer = self._muxers[name]
        else:
            muxer = Muxer()
            muxer.name = 'muxer-' + name
            muxer.component_type = self._muxerType
            muxer.worker = self._muxerWorker
            self._muxers[name] = muxer
        return muxer

    def _handleAudio(self):
        if not self._audioProducer:
            return

        self._audioProducer.name = 'producer-audio'
        if (self._videoProducer and
            self._videoProducer.component_type ==
            self._audioProducer.component_type):
            self._audioProducer = self._videoProducer
        else:
            self._flowComponents.append(self._audioProducer)

        self._audioEncoder.name = 'encoder-audio'
        self._flowComponents.append(self._audioEncoder)

        self._audioEncoder.link(self._audioProducer)

    def _handleVideo(self):
        if not self._videoProducer:
            return

        self._videoProducer.name = 'video-producer'
        self._flowComponents.append(self._videoProducer)

        self._videoEncoder.name = 'encoder-video'
        self._flowComponents.append(self._videoEncoder)

        if self._videoOverlay:
            self._handleVideoOverlay()
            self._videoOverlay.link(self._videoProducer)
            self._videoEncoder.link(self._videoOverlay)
            self._flowComponents.append(self._videoOverlay)
        else:
            self._videoEncoder.link(self._videoProducer)

    def _handleVideoOverlay(self):
        self._videoOverlay.name = 'overlay-video'

        if not self._videoOverlay.show_logo:
            return

        self._videoOverlay.properties.fluendo_logo = True
        if self._muxerType == 'ogg-muxer':
            self._videoOverlay.properties.xiph_logo = True

        if self._useCCLicense:
            self._videoOverlay.properties.cc_logo = True

    def _handleConsumers(self):
        # Add & link the muxers we will use
        audio_muxer = self._getMuxer('audio')
        if audio_muxer.eaters:
            self._flowComponents.append(audio_muxer)
            audio_muxer.link(self._audioEncoder)

        video_muxer = self._getMuxer('video')
        if video_muxer.eaters:
            self._flowComponents.append(video_muxer)
            video_muxer.link(self._videoEncoder)

        both_muxer = self._getMuxer('audio-video')
        if both_muxer.eaters:
            self._flowComponents.append(both_muxer)
            both_muxer.link(self._audioEncoder)
            both_muxer.link(self._videoEncoder)
