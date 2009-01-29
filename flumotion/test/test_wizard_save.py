# -*- Mode: Python; test-case-name: flumotion.test.test_wizard_models -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# Flumotion - a streaming media server
# Copyright (C) 2008 Fluendo, S.L. (www.fluendo.com).
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

import unittest

from kiwi.python import Settable

from flumotion.admin.assistant.configurationwriter import ConfigurationWriter
from flumotion.admin.assistant.models import Component, Plug, Porter, \
     AudioProducer, VideoProducer, AudioEncoder, VideoEncoder, HTTPServer
from flumotion.admin.assistant.save import AssistantSaver
from flumotion.common import testsuite
from flumotion.configure import configure
from flumotion.component.producers.firewire.wizard_gtk import FireWireProducer
from flumotion.scenario.steps.httpstreamersteps import HTTPStreamer
from flumotion.component.encoders.vorbis.wizard_gtk import VorbisAudioEncoder
from flumotion.component.encoders.theora.wizard_gtk import TheoraVideoEncoder
from flumotion.component.producers.videotest.wizard_gtk import \
     TestVideoProducer
from flumotion.component.producers.audiotest.wizard_gtk import \
     TestAudioProducer
from flumotion.admin.gtk.overlaystep import Overlay


class TestXMLWriter(testsuite.TestCase):

    def testEmpty(self):
        writer = ConfigurationWriter('', [], [])
        testsuite.diffStrings(
            ("<planet>\n"
             "</planet>\n"),
            writer.getXML())

    def testFlowComponent(self):
        c = Component()
        c.name = 'name'
        c.componentType = 'streamer'
        c.worker = 'worker'
        writer = ConfigurationWriter('flow', [c], [])
        testsuite.diffStrings(
            ('<planet>\n'
             '  <flow name="flow">\n'
             '    <component name="name"\n'
             '               type="streamer"\n'
             '               project="flumotion"\n'
             '               worker="worker"\n'
             '               version="%(version)s">\n'
             '    </component>\n'
             '  </flow>\n'
             '</planet>\n' % dict(version=configure.version)),
            writer.getXML())

    def testAtmosphereComponent(self):
        c = Component()
        c.name = 'name'
        c.componentType = 'streamer'
        c.worker = 'worker'
        c.properties.foo = 'bar'
        writer = ConfigurationWriter('', [], [c])
        testsuite.diffStrings(
            ('<planet>\n'
             '  <atmosphere>\n'
             '    <component name="name"\n'
             '               type="streamer"\n'
             '               project="flumotion"\n'
             '               worker="worker"\n'
             '               version="%(version)s">\n'
             '      \n'
             '      <property name="foo">bar</property>\n'
             '    </component>\n'
             '  </atmosphere>\n'
             '</planet>\n' % dict(version=configure.version)),
            writer.getXML())

    def testComponentWithPlug(self):
        c = Component()
        c.name = 'name'
        c.componentType = 'streamer'
        c.worker = 'worker'
        plug = Plug()
        plug.plugType = 'plug-type'
        plug.properties.foo = 'bar'
        c.plugs.append(plug)
        writer = ConfigurationWriter('flow', [c], [])
        testsuite.diffStrings(
            ('<planet>\n'
             '  <flow name="flow">\n'
             '    <component name="name"\n'
             '               type="streamer"\n'
             '               project="flumotion"\n'
             '               worker="worker"\n'
             '               version="%(version)s">\n'
             '      \n'
             '      <plugs>\n'
             '        <plug type="plug-type">\n'
             '          \n'
             '          <property name="foo">bar</property>\n'
             '        </plug>\n'
             '      </plugs>\n'
             '    </component>\n'
             '  </flow>\n'
             '</planet>\n' % dict(version=configure.version)),
            writer.getXML())

    def testComponentWithFeeders(self):
        c1 = Component()
        c1.name = 'name'
        c1.componentType = 'first'
        c1.worker = 'worker'
        c2 = Component()
        c2.name = 'name'
        c2.componentType = 'second'
        c2.worker = 'worker'
        c2.link(c1)

        writer = ConfigurationWriter('flow', [c1, c2], [])
        testsuite.diffStrings(
            ('<planet>\n'
             '  <flow name="flow">\n'
             '    <component name="name"\n'
             '               type="first"\n'
             '               project="flumotion"\n'
             '               worker="worker"\n'
             '               version="%(version)s">\n'
             '      <eater name="default">\n'
             '        <feed>name</feed>\n'
             '      </eater>\n'
             '    </component>\n'
             '    <component name="name"\n'
             '               type="second"\n'
             '               project="flumotion"\n'
             '               worker="worker"\n'
             '               version="%(version)s">\n'
             '    </component>\n'
             '  </flow>\n'
             '</planet>\n' % dict(version=configure.version)),
            writer.getXML())


class TestWizardSave(testsuite.TestCase):

    def _createAudioProducer(self, componentType='audio-producer',
                             worker='audio-producer-worker'):
        audioProducer = AudioProducer()
        audioProducer.componentType = componentType
        audioProducer.worker = worker
        return audioProducer

    def _createVideoProducer(self, componentType='video-producer',
                             worker='video-producer-worker'):
        videoProducer = VideoProducer()
        videoProducer.componentType = componentType
        videoProducer.worker = worker
        videoProducer.properties.width = 640
        videoProducer.properties.height = 480
        return videoProducer

    def _createVideoOverlay(self, videoProducer):
        overlay = Overlay(videoProducer)
        overlay.worker = 'overlay-worker'
        return overlay

    def _createAudioEncoder(self):
        audioEncoder = AudioEncoder()
        audioEncoder.componentType = 'audio-encoder'
        audioEncoder.worker = 'audio-encoder-worker'
        return audioEncoder

    def _createVideoEncoder(self):
        videoEncoder = VideoEncoder()
        videoEncoder.componentType = 'video-encoder'
        videoEncoder.worker = 'video-encoder-worker'
        return videoEncoder

    def _createPorter(self):
        return Porter('porter-worker',
                      port=8080,
                      username='username',
                      password='password',
                      socketPath='flu-XXXX.socket')

    def _createHTTPStreamer(self):
        streamer = HTTPStreamer()
        streamer.worker = 'streamer-worker'
        return streamer

    def _createFirewireProducer(self):
        producer = FireWireProducer()
        producer.worker = 'firewire-video-producer-worker'
        producer.properties.width = 640
        producer.properties.height = 480
        return producer

    def testDefaultStream(self):
        save = AssistantSaver()
        save.setFlowName('flow')

        save.setAudioProducer(self._createAudioProducer())
        videoProducer = self._createVideoProducer()
        save.setVideoProducer(videoProducer)
        save.setVideoOverlay(self._createVideoOverlay(videoProducer))
        save.setAudioEncoder(self._createAudioEncoder())
        save.setVideoEncoder(self._createVideoEncoder())

        save.setMuxer('default-muxer', 'muxer-worker')

        porter = self._createPorter()
        save.addPorter(porter, 'audio-video')

        streamer = self._createHTTPStreamer()
        streamer.setPorter(porter)
        save.addConsumer(streamer, 'audio-video')

        server = HTTPServer('server-worker', '/mount/')
        save.addServerConsumer(server, 'audio-video')

        save.setUseCCLicense(True)

        configuration = save.getXML()
        testsuite.diffStrings(
            ('<planet>\n'
             '  <atmosphere>\n'
             '    <component name="http-server-audio-video"\n'
             '               type="http-server"\n'
             '               project="flumotion"\n'
             '               worker="server-worker"\n'
             '               version="%(version)s">\n'
             '      \n'
             '      <property name="mount-point">/mount/</property>\n'
             '    </component>\n'
             '    <component name="porter-audio-video"\n'
             '               type="porter"\n'
             '               project="flumotion"\n'
             '               worker="porter-worker"\n'
             '               version="%(version)s">\n'
             '      \n'
             '      <property name="password">password</property>\n'
             '      <property name="port">8080</property>\n'
             '      <property name="socket-path">flu-XXXX.socket</property>\n'
             '      <property name="username">username</property>\n'
             '    </component>\n'
             '  </atmosphere>\n'
             '  <flow name="flow">\n'
             '    <component name="producer-audio"\n'
             '               type="audio-producer"\n'
             '               project="flumotion"\n'
             '               worker="audio-producer-worker"\n'
             '               version="%(version)s">\n'
             '    </component>\n'
             '    <component name="producer-video"\n'
             '               type="video-producer"\n'
             '               project="flumotion"\n'
             '               worker="video-producer-worker"\n'
             '               version="%(version)s">\n'
             '      \n'
             '      <property name="height">480</property>\n'
             '      <property name="width">640</property>\n'
             '    </component>\n'
             '    <component name="overlay-video"\n'
             '               type="overlay-converter"\n'
             '               project="flumotion"\n'
             '               worker="overlay-worker"\n'
             '               version="%(version)s">\n'
             '      <eater name="default">\n'
             '        <feed>producer-video</feed>\n'
             '      </eater>\n'
             '      \n'
             '      <property name="cc-logo">True</property>\n'
             '      <property name="fluendo-logo">True</property>\n'
             '      <property name="height">480</property>\n'
             '      <property name="show-text">True</property>\n'
             '      <property name="text">Flumotion</property>\n'
             '      <property name="width">640</property>\n'
             '    </component>\n'
             '    <component name="encoder-audio"\n'
             '               type="audio-encoder"\n'
             '               project="flumotion"\n'
             '               worker="audio-encoder-worker"\n'
             '               version="%(version)s">\n'
             '      <eater name="default">\n'
             '        <feed>producer-audio</feed>\n'
             '      </eater>\n'
             '    </component>\n'
             '    <component name="encoder-video"\n'
             '               type="video-encoder"\n'
             '               project="flumotion"\n'
             '               worker="video-encoder-worker"\n'
             '               version="%(version)s">\n'
             '      <eater name="default">\n'
             '        <feed>overlay-video</feed>\n'
             '      </eater>\n'
             '    </component>\n'
             '    <component name="muxer-audio-video"\n'
             '               type="default-muxer"\n'
             '               project="flumotion"\n'
             '               worker="muxer-worker"\n'
             '               version="%(version)s">\n'
             '      <eater name="default">\n'
             '        <feed>encoder-audio</feed>\n'
             '        <feed>encoder-video</feed>\n'
             '      </eater>\n'
             '    </component>\n'
             '    <component name="http-audio-video"\n'
             '               type="http-streamer"\n'
             '               project="flumotion"\n'
             '               worker="streamer-worker"\n'
             '               version="%(version)s">\n'
             '      <eater name="default">\n'
             '        <feed>muxer-audio-video</feed>\n'
             '      </eater>\n'
             '      \n'
             '      <property name="burst-on-connect">False</property>\n'
             '      <property name="port">8080</property>\n'
             '      <property name="porter-password">password</property>\n'
             '      <property name="porter-socket-path">flu-XXXX.socket'
             '</property>\n'
             '      <property name="porter-username">username</property>\n'
             '      <property name="type">slave</property>\n'
             '    </component>\n'
             '  </flow>\n'
             '</planet>\n' % dict(version=configure.version)),
            configuration)

    def testMultiFeedProducer(self):
        save = AssistantSaver()
        save.setFlowName('flow')

        save.setAudioProducer(self._createAudioProducer(
            worker='both-producer-worker',
            componentType='both-producer'))
        save.setVideoProducer(self._createVideoProducer(
            componentType='both-producer',
            worker='both-producer-worker'))

        save.setAudioEncoder(self._createAudioEncoder())
        save.setVideoEncoder(self._createVideoEncoder())

        save.setMuxer('default-muxer', 'muxer-worker')

        porter = self._createPorter()
        save.addPorter(porter, 'audio-video')

        streamer = self._createHTTPStreamer()
        streamer.setPorter(porter)
        save.addConsumer(streamer, 'audio-video')

        configuration = save.getXML()
        testsuite.diffStrings(
            ('<planet>\n'
             '  <atmosphere>\n'
             '    <component name="porter-audio-video"\n'
             '               type="porter"\n'
             '               project="flumotion"\n'
             '               worker="porter-worker"\n'
             '               version="%(version)s">\n'
             '      \n'
             '      <property name="password">password</property>\n'
             '      <property name="port">8080</property>\n'
             '      <property name="socket-path">flu-XXXX.socket</property>\n'
             '      <property name="username">username</property>\n'
             '    </component>\n'
             '  </atmosphere>\n'
             '  <flow name="flow">\n'
             '    <component name="producer-audio-video"\n'
             '               type="both-producer"\n'
             '               project="flumotion"\n'
             '               worker="both-producer-worker"\n'
             '               version="%(version)s">\n'
             '      \n'
             '      <property name="height">480</property>\n'
             '      <property name="width">640</property>\n'
             '    </component>\n'
             '    <component name="encoder-audio"\n'
             '               type="audio-encoder"\n'
             '               project="flumotion"\n'
             '               worker="audio-encoder-worker"\n'
             '               version="%(version)s">\n'
             '      <eater name="default">\n'
             '        <feed>producer-audio-video</feed>\n'
             '      </eater>\n'
             '    </component>\n'
             '    <component name="encoder-video"\n'
             '               type="video-encoder"\n'
             '               project="flumotion"\n'
             '               worker="video-encoder-worker"\n'
             '               version="%(version)s">\n'
             '      <eater name="default">\n'
             '        <feed>producer-audio-video</feed>\n'
             '      </eater>\n'
             '    </component>\n'
             '    <component name="muxer-audio-video"\n'
             '               type="default-muxer"\n'
             '               project="flumotion"\n'
             '               worker="muxer-worker"\n'
             '               version="%(version)s">\n'
             '      <eater name="default">\n'
             '        <feed>encoder-audio</feed>\n'
             '        <feed>encoder-video</feed>\n'
             '      </eater>\n'
             '    </component>\n'
             '    <component name="http-audio-video"\n'
             '               type="http-streamer"\n'
             '               project="flumotion"\n'
             '               worker="streamer-worker"\n'
             '               version="%(version)s">\n'
             '      <eater name="default">\n'
             '        <feed>muxer-audio-video</feed>\n'
             '      </eater>\n'
             '      \n'
             '      <property name="burst-on-connect">False</property>\n'
             '      <property name="port">8080</property>\n'
             '      <property name="porter-password">password</property>\n'
             '      <property name="porter-socket-path">flu-XXXX.socket'
             '</property>\n'
             '      <property name="porter-username">username</property>\n'
             '      <property name="type">slave</property>\n'
             '    </component>\n'
             '  </flow>\n'
             '</planet>\n' % dict(version=configure.version)),
            configuration)

    def testOggStream(self):
        save = AssistantSaver()
        save.setFlowName('flow')

        audioProducer = TestAudioProducer()
        audioProducer.worker = 'worker'
        save.setAudioProducer(audioProducer)
        videoProducer = TestVideoProducer()
        videoProducer.worker = 'worker'
        videoProducer.properties.width = 320
        videoProducer.properties.height = 240
        save.setVideoProducer(videoProducer)

        save.setVideoOverlay(self._createVideoOverlay(videoProducer))

        audioEncoder = VorbisAudioEncoder()
        audioEncoder.worker = 'worker'
        save.setAudioEncoder(audioEncoder)
        videoEncoder = TheoraVideoEncoder()
        videoEncoder.worker = 'worker'
        save.setVideoEncoder(videoEncoder)

        save.setMuxer('ogg-muxer', 'muxer-worker')

        porter = self._createPorter()
        save.addPorter(porter, 'audio-video')
        streamer = self._createHTTPStreamer()
        streamer.setPorter(porter)
        save.addConsumer(streamer, 'audio-video')

        configuration = save.getXML()
        testsuite.diffStrings(
            ('<planet>\n'
             '  <atmosphere>\n'
             '    <component name="porter-audio-video"\n'
             '               type="porter"\n'
             '               project="flumotion"\n'
             '               worker="porter-worker"\n'
             '               version="%(version)s">\n'
             '      \n'
             '      <property name="password">password</property>\n'
             '      <property name="port">8080</property>\n'
             '      <property name="socket-path">flu-XXXX.socket</property>\n'
             '      <property name="username">username</property>\n'
             '    </component>\n'
             '  </atmosphere>\n'
             '  <flow name="flow">\n'
             '    <component name="producer-audio"\n'
             '               type="audiotest-producer"\n'
             '               project="flumotion"\n'
             '               worker="worker"\n'
             '               version="%(version)s">\n'
             '      \n'
             '      <property name="samplerate">44100</property>\n'
             '    </component>\n'
             '    <component name="producer-video"\n'
             '               type="videotest-producer"\n'
             '               project="flumotion"\n'
             '               worker="worker"\n'
             '               version="%(version)s">\n'
             '      \n'
             '      <property name="height">240</property>\n'
             '      <property name="pattern">0</property>\n'
             '      <property name="width">320</property>\n'
             '    </component>\n'
             '    <component name="overlay-video"\n'
             '               type="overlay-converter"\n'
             '               project="flumotion"\n'
             '               worker="overlay-worker"\n'
             '               version="%(version)s">\n'
             '      <eater name="default">\n'
             '        <feed>producer-video</feed>\n'
             '      </eater>\n'
             '      \n'
             '      <property name="fluendo-logo">True</property>\n'
             '      <property name="height">240</property>\n'
             '      <property name="show-text">True</property>\n'
             '      <property name="text">Flumotion</property>\n'
             '      <property name="width">320</property>\n'
             '      <property name="xiph-logo">True</property>\n'
             '    </component>\n'
             '    <component name="encoder-video"\n'
             '               type="theora-encoder"\n'
             '               project="flumotion"\n'
             '               worker="worker"\n'
             '               version="%(version)s">\n'
             '      <eater name="default">\n'
             '        <feed>overlay-video</feed>\n'
             '      </eater>\n'
             '      \n'
             '      <property name="bitrate">400000</property>\n'
             '      <property name="keyframe-maxdistance">50</property>\n'
             '      <property name="noise-sensitivity">1</property>\n'
             '      <property name="sharpness">0</property>\n'
             '    </component>\n'
             '    <component name="encoder-audio"\n'
             '               type="vorbis-encoder"\n'
             '               project="flumotion"\n'
             '               worker="worker"\n'
             '               version="%(version)s">\n'
             '      <eater name="default">\n'
             '        <feed>producer-audio</feed>\n'
             '      </eater>\n'
             '      \n'
             '      <property name="bitrate">64000</property>\n'
             '    </component>\n'
             '    <component name="muxer-audio-video"\n'
             '               type="ogg-muxer"\n'
             '               project="flumotion"\n'
             '               worker="muxer-worker"\n'
             '               version="%(version)s">\n'
             '      <eater name="default">\n'
             '        <feed>encoder-audio</feed>\n'
             '        <feed>encoder-video</feed>\n'
             '      </eater>\n'
             '    </component>\n'
             '    <component name="http-audio-video"\n'
             '               type="http-streamer"\n'
             '               project="flumotion"\n'
             '               worker="streamer-worker"\n'
             '               version="%(version)s">\n'
             '      <eater name="default">\n'
             '        <feed>muxer-audio-video</feed>\n'
             '      </eater>\n'
             '      \n'
             '      <property name="burst-on-connect">False</property>\n'
             '      <property name="port">8080</property>\n'
             '      <property name="porter-password">password</property>\n'
             '      <property name="porter-socket-path">flu-XXXX.socket'
             '</property>\n'
             '      <property name="porter-username">username</property>\n'
             '      <property name="type">slave</property>\n'
             '    </component>\n'
             '  </flow>\n'
             '</planet>\n' % dict(version=configure.version)),
            configuration)

    def testAudioOnlyStream(self):
        save = AssistantSaver()
        porter = self._createPorter()
        save.addPorter(porter, 'audio-video')
        save.setFlowName('flow')

        audioProducer = TestAudioProducer()
        audioProducer.worker = 'worker'
        save.setAudioProducer(audioProducer)

        audioEncoder = VorbisAudioEncoder()
        audioEncoder.worker = 'worker'
        save.setAudioEncoder(audioEncoder)

        videoProducer = self._createVideoEncoder()
        self.assertRaises(ValueError, save.setVideoOverlay,
                          self._createVideoOverlay(videoProducer))

        save.setMuxer('ogg-muxer', 'muxer')

        streamer = self._createHTTPStreamer()
        streamer.setPorter(porter)
        save.addConsumer(streamer, 'audio')

        configuration = save.getXML()
        testsuite.diffStrings(
            ('<planet>\n'
             '  <atmosphere>\n'
             '    <component name="porter-audio-video"\n'
             '               type="porter"\n'
             '               project="flumotion"\n'
             '               worker="porter-worker"\n'
             '               version="%(version)s">\n'
             '      \n'
             '      <property name="password">password</property>\n'
             '      <property name="port">8080</property>\n'
             '      <property name="socket-path">flu-XXXX.socket</property>\n'
             '      <property name="username">username</property>\n'
             '    </component>\n'
             '  </atmosphere>\n'
             '  <flow name="flow">\n'
             '    <component name="producer-audio"\n'
             '               type="audiotest-producer"\n'
             '               project="flumotion"\n'
             '               worker="worker"\n'
             '               version="%(version)s">\n'
             '      \n'
             '      <property name="samplerate">44100</property>\n'
             '    </component>\n'
             '    <component name="encoder-audio"\n'
             '               type="vorbis-encoder"\n'
             '               project="flumotion"\n'
             '               worker="worker"\n'
             '               version="%(version)s">\n'
             '      <eater name="default">\n'
             '        <feed>producer-audio</feed>\n'
             '      </eater>\n'
             '      \n'
             '      <property name="bitrate">64000</property>\n'
             '    </component>\n'
             '    <component name="muxer-audio"\n'
             '               type="ogg-muxer"\n'
             '               project="flumotion"\n'
             '               worker="muxer"\n'
             '               version="%(version)s">\n'
             '      <eater name="default">\n'
             '        <feed>encoder-audio</feed>\n'
             '      </eater>\n'
             '    </component>\n'
             '    <component name="http-audio"\n'
             '               type="http-streamer"\n'
             '               project="flumotion"\n'
             '               worker="streamer-worker"\n'
             '               version="%(version)s">\n'
             '      <eater name="default">\n'
             '        <feed>muxer-audio</feed>\n'
             '      </eater>\n'
             '      \n'
             '      <property name="burst-on-connect">False</property>\n'
             '      <property name="port">8080</property>\n'
             '      <property name="porter-password">password</property>\n'
             '      <property name="porter-socket-path">flu-XXXX.socket'
             '</property>\n'
             '      <property name="porter-username">username</property>\n'
             '      <property name="type">slave</property>\n'
             '    </component>\n'
             '  </flow>\n'
             '</planet>\n' % dict(version=configure.version)),
            configuration)

    def testFirewireStreamer(self):
        save = AssistantSaver()
        porter = self._createPorter()
        save.addPorter(porter, 'audio-video')
        save.setFlowName('flow')

        producer = self._createFirewireProducer()
        save.setAudioProducer(producer)
        save.setVideoProducer(producer)
        save.setVideoOverlay(self._createVideoOverlay(producer))
        save.setAudioEncoder(self._createAudioEncoder())
        save.setVideoEncoder(self._createVideoEncoder())

        save.setMuxer('default-muxer', 'muxer-worker')

        streamer = self._createHTTPStreamer()
        streamer.setPorter(porter)
        save.addConsumer(streamer, 'audio-video')

        server = HTTPServer('server-worker', '/mount/')
        save.addServerConsumer(server, 'audio-video')

        save.setUseCCLicense(True)

        configuration = save.getXML()
        testsuite.diffStrings(
            ('<planet>\n'
             '  <atmosphere>\n'
             '    <component name="http-server-audio-video"\n'
             '               type="http-server"\n'
             '               project="flumotion"\n'
             '               worker="server-worker"\n'
             '               version="%(version)s">\n'
             '      \n'
             '      <property name="mount-point">/mount/</property>\n'
             '    </component>\n'
             '    <component name="porter-audio-video"\n'
             '               type="porter"\n'
             '               project="flumotion"\n'
             '               worker="porter-worker"\n'
             '               version="%(version)s">\n'
             '      \n'
             '      <property name="password">password</property>\n'
             '      <property name="port">8080</property>\n'
             '      <property name="socket-path">flu-XXXX.socket</property>\n'
             '      <property name="username">username</property>\n'
             '    </component>\n'
             '  </atmosphere>\n'
             '  <flow name="flow">\n'
             '    <component name="producer-audio-video"\n'
             '               type="firewire-producer"\n'
             '               project="flumotion"\n'
             '               worker="firewire-video-producer-worker"\n'
             '               version="%(version)s">\n'
             '      \n'
             '      <property name="height">480</property>\n'
             '      <property name="is-square">False</property>\n'
             '      <property name="width">640</property>\n'
             '    </component>\n'
             '    <component name="overlay-video"\n'
             '               type="overlay-converter"\n'
             '               project="flumotion"\n'
             '               worker="overlay-worker"\n'
             '               version="%(version)s">\n'
             '      <eater name="default">\n'
             '        <feed>producer-audio-video:video</feed>\n'
             '      </eater>\n'
             '      \n'
             '      <property name="cc-logo">True</property>\n'
             '      <property name="fluendo-logo">True</property>\n'
             '      <property name="height">480</property>\n'
             '      <property name="show-text">True</property>\n'
             '      <property name="text">Flumotion</property>\n'
             '      <property name="width">640</property>\n'
             '    </component>\n'
             '    <component name="encoder-audio"\n'
             '               type="audio-encoder"\n'
             '               project="flumotion"\n'
             '               worker="audio-encoder-worker"\n'
             '               version="%(version)s">\n'
             '      <eater name="default">\n'
             '        <feed>producer-audio-video:audio</feed>\n'
             '      </eater>\n'
             '    </component>\n'
             '    <component name="encoder-video"\n'
             '               type="video-encoder"\n'
             '               project="flumotion"\n'
             '               worker="video-encoder-worker"\n'
             '               version="%(version)s">\n'
             '      <eater name="default">\n'
             '        <feed>overlay-video</feed>\n'
             '      </eater>\n'
             '    </component>\n'
             '    <component name="muxer-audio-video"\n'
             '               type="default-muxer"\n'
             '               project="flumotion"\n'
             '               worker="muxer-worker"\n'
             '               version="%(version)s">\n'
             '      <eater name="default">\n'
             '        <feed>encoder-audio</feed>\n'
             '        <feed>encoder-video</feed>\n'
             '      </eater>\n'
             '    </component>\n'
             '    <component name="http-audio-video"\n'
             '               type="http-streamer"\n'
             '               project="flumotion"\n'
             '               worker="streamer-worker"\n'
             '               version="%(version)s">\n'
             '      <eater name="default">\n'
             '        <feed>muxer-audio-video</feed>\n'
             '      </eater>\n'
             '      \n'
             '      <property name="burst-on-connect">False</property>\n'
             '      <property name="port">8080</property>\n'
             '      <property name="porter-password">password</property>\n'
             '      <property name="porter-socket-path">flu-XXXX.socket'
             '</property>\n'
             '      <property name="porter-username">username</property>\n'
             '      <property name="type">slave</property>\n'
             '    </component>\n'
             '  </flow>\n'
             '</planet>\n' % dict(version=configure.version)),
            configuration)

    def testFirewireStreamerDifferentWorkers(self):
        save = AssistantSaver()
        porter = self._createPorter()
        save.addPorter(porter, 'audio-video')
        save.setFlowName('flow')

        audioProducer = self._createFirewireProducer()
        audioProducer.name = 'audio-producer'
        audioProducer.worker = 'audio-worker'
        save.setAudioProducer(audioProducer)
        videoProducer = self._createFirewireProducer()
        videoProducer.name = 'video-producer'
        videoProducer.worker = 'video-worker'
        save.setVideoProducer(videoProducer)
        save.setVideoOverlay(self._createVideoOverlay(videoProducer))
        save.setAudioEncoder(self._createAudioEncoder())
        save.setVideoEncoder(self._createVideoEncoder())

        save.setMuxer('default-muxer', 'muxer-worker')

        streamer = self._createHTTPStreamer()
        streamer.has_bandwidth_limit = True
        streamer.bandwidth_limit = 123
        streamer.setPorter(porter)
        save.addConsumer(streamer, 'audio-video')

        server = HTTPServer('server-worker', '/mount/')
        save.addServerConsumer(server, 'audio-video')

        save.setUseCCLicense(True)

        configuration = save.getXML()
        testsuite.diffStrings(
            ('<planet>\n'
             '  <atmosphere>\n'
             '    <component name="http-server-audio-video"\n'
             '               type="http-server"\n'
             '               project="flumotion"\n'
             '               worker="server-worker"\n'
             '               version="%(version)s">\n'
             '      \n'
             '      <property name="mount-point">/mount/</property>\n'
             '    </component>\n'
             '    <component name="porter-audio-video"\n'
             '               type="porter"\n'
             '               project="flumotion"\n'
             '               worker="porter-worker"\n'
             '               version="%(version)s">\n'
             '      \n'
             '      <property name="password">password</property>\n'
             '      <property name="port">8080</property>\n'
             '      <property name="socket-path">flu-XXXX.socket</property>\n'
             '      <property name="username">username</property>\n'
             '    </component>\n'
             '  </atmosphere>\n'
             '  <flow name="flow">\n'
             '    <component name="producer-audio"\n'
             '               type="firewire-producer"\n'
             '               project="flumotion"\n'
             '               worker="audio-worker"\n'
             '               version="%(version)s">\n'
             '      \n'
             '      <property name="height">480</property>\n'
             '      <property name="is-square">False</property>\n'
             '      <property name="width">640</property>\n'
             '    </component>\n'
             '    <component name="producer-video"\n'
             '               type="firewire-producer"\n'
             '               project="flumotion"\n'
             '               worker="video-worker"\n'
             '               version="%(version)s">\n'
             '      \n'
             '      <property name="height">480</property>\n'
             '      <property name="is-square">False</property>\n'
             '      <property name="width">640</property>\n'
             '    </component>\n'
             '    <component name="overlay-video"\n'
             '               type="overlay-converter"\n'
             '               project="flumotion"\n'
             '               worker="overlay-worker"\n'
             '               version="%(version)s">\n'
             '      <eater name="default">\n'
             '        <feed>producer-video:video</feed>\n'
             '      </eater>\n'
             '      \n'
             '      <property name="cc-logo">True</property>\n'
             '      <property name="fluendo-logo">True</property>\n'
             '      <property name="height">480</property>\n'
             '      <property name="show-text">True</property>\n'
             '      <property name="text">Flumotion</property>\n'
             '      <property name="width">640</property>\n'
             '    </component>\n'
             '    <component name="encoder-audio"\n'
             '               type="audio-encoder"\n'
             '               project="flumotion"\n'
             '               worker="audio-encoder-worker"\n'
             '               version="%(version)s">\n'
             '      <eater name="default">\n'
             '        <feed>producer-audio:audio</feed>\n'
             '      </eater>\n'
             '    </component>\n'
             '    <component name="encoder-video"\n'
             '               type="video-encoder"\n'
             '               project="flumotion"\n'
             '               worker="video-encoder-worker"\n'
             '               version="%(version)s">\n'
             '      <eater name="default">\n'
             '        <feed>overlay-video</feed>\n'
             '      </eater>\n'
             '    </component>\n'
             '    <component name="muxer-audio-video"\n'
             '               type="default-muxer"\n'
             '               project="flumotion"\n'
             '               worker="muxer-worker"\n'
             '               version="%(version)s">\n'
             '      <eater name="default">\n'
             '        <feed>encoder-audio</feed>\n'
             '        <feed>encoder-video</feed>\n'
             '      </eater>\n'
             '    </component>\n'
             '    <component name="http-audio-video"\n'
             '               type="http-streamer"\n'
             '               project="flumotion"\n'
             '               worker="streamer-worker"\n'
             '               version="%(version)s">\n'
             '      <eater name="default">\n'
             '        <feed>muxer-audio-video</feed>\n'
             '      </eater>\n'
             '      \n'
             '      <property name="bandwidth-limit">123000000</property>\n'
             '      <property name="burst-on-connect">False</property>\n'
             '      <property name="port">8080</property>\n'
             '      <property name="porter-password">password</property>\n'
             '      <property name="porter-socket-path">flu-XXXX.socket'
             '</property>\n'
             '      <property name="porter-username">username</property>\n'
             '      <property name="type">slave</property>\n'
             '    </component>\n'
             '  </flow>\n'
             '</planet>\n' % dict(version=configure.version)),
            configuration)

    def testOndemand(self):
        save = AssistantSaver()

        server = HTTPServer('ondemand-server-worker', '/mount-point/')
        save.addServerConsumer(server, 'ondemand')

        configuration = save.getXML()
        testsuite.diffStrings(
            ('<planet>\n'
             '  <atmosphere>\n'
             '    <component name="http-server-ondemand"\n'
             '               type="http-server"\n'
             '               project="flumotion"\n'
             '               worker="ondemand-server-worker"\n'
             '               version="%(version)s">\n'
             '      \n'
             '      <property name="mount-point">/mount-point/</property>\n'
             '    </component>\n'
             '  </atmosphere>\n'
             '</planet>\n' % dict(version=configure.version)),
            configuration)


class TestNameConflicts(testsuite.TestCase):

    def setUp(self):
        self.save = AssistantSaver()

    def _addServer(self, name):
        server = HTTPServer('ondemand-server-worker', '/mount-point/')
        self.save.addServerConsumer(server, name)

    def testNameConflicts(self):
        self.save.setExistingComponentNames(['http-server-ondemand'])
        self._addServer('ondemand')
        self.save.getXML()

        components = self.save.getAtmosphereComponents()
        self.assertEquals(components[0].name, 'http-server-ondemand2')

    def testNameConflictsDoubleDigits(self):
        componentNames = ['http-server-ondemand'] + [
            'http-server-ondemand%d' % i for i in range(2, 10)]
        self.save.setExistingComponentNames(componentNames)
        self._addServer('ondemand')
        self.save.getXML()

        components = self.save.getAtmosphereComponents()
        self.assertEquals(components[0].name, 'http-server-ondemand10')

if __name__ == '__main__':
    unittest.main()
