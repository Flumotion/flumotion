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

from flumotion.common import testsuite
from flumotion.configure import configure
from flumotion.component.producers.firewire.firewire_wizard import \
     FireWireVideoProducer, FireWireAudioProducer
from flumotion.component.consumers.httpstreamer.httpstreamer_wizard import \
     HTTPPorter, HTTPStreamer
from flumotion.component.encoders.vorbis.vorbis_wizard import \
     VorbisAudioEncoder
from flumotion.component.encoders.theora.theora_wizard import \
     TheoraVideoEncoder
from flumotion.component.producers.videotest.videotest_wizard import \
     TestVideoProducer
from flumotion.component.producers.audiotest.audiotest_wizard import \
     TestAudioProducer
from flumotion.wizard.configurationwriter import ConfigurationWriter
from flumotion.wizard.models import Component, Plug, AudioProducer, \
     VideoProducer, AudioEncoder, VideoEncoder, HTTPServer
from flumotion.wizard.overlaystep import Overlay
from flumotion.wizard.save import WizardSaver

__version__ = "$Rev: 6126 $"


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
        c.component_type = 'streamer'
        c.worker = 'worker'
        writer = ConfigurationWriter('flow', [c], [])
        testsuite.diffStrings(
            ('<planet>\n'
             '  <flow name="flow">\n'
             '    <component name="name" type="streamer" '
             'project="flumotion" worker="worker" version="%(version)s">\n'
             '    </component>\n'
             '  </flow>\n'
             '</planet>\n' % dict(version=configure.version)),
            writer.getXML())

    def testAtmosphereComponent(self):
        c = Component()
        c.name = 'name'
        c.component_type = 'streamer'
        c.worker = 'worker'
        c.properties.foo = 'bar'
        writer = ConfigurationWriter('', [], [c])
        testsuite.diffStrings(
            ('<planet>\n'
             '  <atmosphere>\n'
             '    <component name="name" type="streamer" '
             'project="flumotion" worker="worker" version="%(version)s">\n'
             '      \n'
             '      <property name="foo">bar</property>\n'
             '    </component>\n'
             '  </atmosphere>\n'
             '</planet>\n' % dict(version=configure.version)),
            writer.getXML())

    def testComponentWithPlug(self):
        c = Component()
        c.name = 'name'
        c.component_type = 'streamer'
        c.worker = 'worker'
        plug = Plug()
        plug.plug_type = 'plug-type'
        plug.properties.foo = 'bar'
        c.plugs.append(plug)
        writer = ConfigurationWriter('flow', [c], [])
        testsuite.diffStrings(
            ('<planet>\n'
             '  <flow name="flow">\n'
             '    <component name="name" type="streamer" '
             'project="flumotion" worker="worker" version="%(version)s">\n'
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
        c1.component_type = 'first'
        c1.worker = 'worker'
        c2 = Component()
        c2.name = 'name'
        c2.component_type = 'second'
        c2.worker = 'worker'
        c1.link(c2)

        writer = ConfigurationWriter('flow', [c1, c2], [])
        testsuite.diffStrings(
            ('<planet>\n'
             '  <flow name="flow">\n'
             '    <component name="name" type="first" '
             'project="flumotion" worker="worker" version="%(version)s">\n'
             '      <eater name="default">\n'
             '        <feed>name</feed>\n'
             '      </eater>\n'
             '    </component>\n'
             '    <component name="name" type="second" '
             'project="flumotion" worker="worker" version="%(version)s">\n'
             '    </component>\n'
             '  </flow>\n'
             '</planet>\n' % dict(version=configure.version)),
            writer.getXML())


class TestWizardSave(testsuite.TestCase):
    def _createAudioProducer(self, component_type='audio-producer',
                             worker='audio-producer-worker'):
        audioProducer = AudioProducer()
        audioProducer.component_type = component_type
        audioProducer.worker = worker
        return audioProducer

    def _createVideoProducer(self, component_type='video-producer',
                             worker='video-producer-worker'):
        videoProducer = VideoProducer()
        videoProducer.component_type = component_type
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
        audioEncoder.component_type = 'audio-encoder'
        audioEncoder.worker = 'audio-encoder-worker'
        return audioEncoder

    def _createVideoEncoder(self):
        videoEncoder = VideoEncoder()
        videoEncoder.component_type = 'video-encoder'
        videoEncoder.worker = 'video-encoder-worker'
        return videoEncoder

    def _createHTTPStreamer(self):
        streamer = HTTPStreamer()
        streamer.properties.port = 8080
        streamer.socket_path = 'flu-XXXX.socket'
        streamer.porter_username = 'username'
        streamer.porter_password = 'password'
        return streamer

    def _createFirewireVideoProducer(self):
        videoProducer = FireWireVideoProducer()
        videoProducer.worker = 'firewire-video-producer-worker'
        videoProducer.properties.width = 640
        videoProducer.properties.height = 480
        return videoProducer

    def testDefaultStream(self):
        save = WizardSaver()
        save.setFlowName('flow')

        save.setAudioProducer(self._createAudioProducer())
        videoProducer = self._createVideoProducer()
        save.setVideoProducer(videoProducer)
        save.setVideoOverlay(self._createVideoOverlay(videoProducer))
        save.setAudioEncoder(self._createAudioEncoder())
        save.setVideoEncoder(self._createVideoEncoder())

        save.setMuxer('default-muxer', 'muxer-worker')

        streamer = self._createHTTPStreamer()
        streamer.worker = 'streamer-worker'
        save.addConsumer(streamer, 'audio-video')

        server = HTTPServer('server-worker', '/mount/')
        save.addServerConsumer(server, 'audio-video')

        porter = HTTPPorter(streamer)
        save.addPorter(porter, 'audio-video')

        save.setUseCCLicense(True)

        configuration = save.getXML()
        testsuite.diffStrings(
            ('<planet>\n'
             '  <atmosphere>\n'
             '    <component name="porter-audio-video" type="porter" '
             'project="flumotion" worker="streamer-worker" version="%(version)s">\n'
             '      \n'
             '      <property name="password">password</property>\n'
             '      <property name="port">8080</property>\n'
             '      <property name="socket-path">flu-XXXX.socket</property>\n'
             '      <property name="username">username</property>\n'
             '    </component>\n'
             '  </atmosphere>\n'
             '  <flow name="flow">\n'
             '    <component name="http-audio-video" type="http-streamer" '
             'project="flumotion" worker="streamer-worker" version="%(version)s">\n'
             '      <eater name="default">\n'
             '        <feed>muxer-audio-video</feed>\n'
             '      </eater>\n'
             '      \n'
             '      <property name="burst-on-connect">False</property>\n'
             '      <property name="port">8080</property>\n'
             '    </component>\n'
             '    <component name="http-server-audio-video" type="http-server" '
             'project="flumotion" worker="server-worker" version="%(version)s">\n'
             '      \n'
             '      <property name="mount-point">/mount/</property>\n'
             '    </component>\n'
             '    <component name="producer-audio" type="audio-producer" '
             'project="flumotion" worker="audio-producer-worker" version="%(version)s">\n'
             '    </component>\n'
             '    <component name="encoder-audio" type="audio-encoder" '
             'project="flumotion" worker="audio-encoder-worker" version="%(version)s">\n'
             '      <eater name="default">\n'
             '        <feed>producer-audio</feed>\n'
             '      </eater>\n'
             '    </component>\n'
             '    <component name="video-producer" type="video-producer" '
             'project="flumotion" worker="video-producer-worker" version="%(version)s">\n'
             '      \n'
             '      <property name="height">480</property>\n'
             '      <property name="width">640</property>\n'
             '    </component>\n'
             '    <component name="encoder-video" type="video-encoder" '
             'project="flumotion" worker="video-encoder-worker" version="%(version)s">\n'
             '      <eater name="default">\n'
             '        <feed>overlay-video</feed>\n'
             '      </eater>\n'
             '    </component>\n'
             '    <component name="overlay-video" type="overlay-converter" '
             'project="flumotion" worker="overlay-worker" version="%(version)s">\n'
             '      <eater name="default">\n'
             '        <feed>video-producer</feed>\n'
             '      </eater>\n'
             '      \n'
             '      <property name="cc-logo">True</property>\n'
             '      <property name="fluendo-logo">True</property>\n'
             '      <property name="height">480</property>\n'
             '      <property name="text">Fluendo</property>\n'
             '      <property name="width">640</property>\n'
             '    </component>\n'
             '    <component name="muxer-audio-video" type="default-muxer" '
             'project="flumotion" worker="muxer-worker" version="%(version)s">\n'
             '      <eater name="default">\n'
             '        <feed>encoder-audio</feed>\n'
             '        <feed>encoder-video</feed>\n'
             '      </eater>\n'
             '    </component>\n'
             '  </flow>\n'
             '</planet>\n' % dict(version=configure.version)),
            configuration)

    def testMultiFeedProducer(self):
        save = WizardSaver()
        save.setFlowName('flow')

        save.setAudioProducer(self._createAudioProducer(
            worker='both-producer-worker',
            component_type='both-producer'))
        save.setVideoProducer(self._createVideoProducer(
            component_type='both-producer',
            worker='both-producer-worker'))

        save.setAudioEncoder(self._createAudioEncoder())
        save.setVideoEncoder(self._createVideoEncoder())

        configuration = save.getXML()
        testsuite.diffStrings(
            ('<planet>\n'
             '  <flow name="flow">\n'
             '    <component name="encoder-audio" type="audio-encoder" '
             'project="flumotion" worker="audio-encoder-worker" version="%(version)s">\n'
             '      <eater name="default">\n'
             '        <feed>producer-audio</feed>\n'
             '      </eater>\n'
             '    </component>\n'
             '    <component name="producer-audio-video" type="both-producer" '
             'project="flumotion" worker="both-producer-worker" version="%(version)s">\n'
             '      \n'
             '      <property name="height">480</property>\n'
             '      <property name="width">640</property>\n'
             '    </component>\n'
             '    <component name="encoder-video" type="video-encoder" '
             'project="flumotion" worker="video-encoder-worker" version="%(version)s">\n'
             '      <eater name="default">\n'
             '        <feed>producer-audio-video</feed>\n'
             '      </eater>\n'
             '    </component>\n'
             '  </flow>\n'
             '</planet>\n' % dict(version=configure.version)),
            configuration)

    def testOggStream(self):
        save = WizardSaver()
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

        streamer = self._createHTTPStreamer()
        streamer.worker = 'worker'
        save.addConsumer(streamer, 'audio-video')

        configuration = save.getXML()
        testsuite.diffStrings(
            ('<planet>\n'
             '  <flow name="flow">\n'
             '    <component name="http-audio-video" type="http-streamer" project="flumotion" worker="worker" version="%(version)s">\n'
             '      <eater name="default">\n'
             '        <feed>muxer-audio-video</feed>\n'
             '      </eater>\n'
             '      \n'
             '      <property name="burst-on-connect">False</property>\n'
             '      <property name="port">8080</property>\n'
             '    </component>\n'
             '    <component name="producer-audio" type="audiotest-producer" project="flumotion" worker="worker" version="%(version)s">\n'
             '      \n'
             '      <property name="rate">44100</property>\n'
             '    </component>\n'
             '    <component name="encoder-audio" type="vorbis-encoder" project="flumotion" worker="worker" version="%(version)s">\n'
             '      <eater name="default">\n'
             '        <feed>producer-audio</feed>\n'
             '      </eater>\n'
             '      \n'
             '      <property name="bitrate">64000</property>\n'
             '    </component>\n'
             '    <component name="video-producer" type="videotest-producer" project="flumotion" worker="worker" version="%(version)s">\n'
             '      \n'
             '      <property name="format">video/x-raw-yuv</property>\n'
             '      <property name="height">240</property>\n'
             '      <property name="pattern">0</property>\n'
             '      <property name="width">320</property>\n'
             '    </component>\n'
             '    <component name="encoder-video" type="theora-encoder" project="flumotion" worker="worker" version="%(version)s">\n'
             '      <eater name="default">\n'
             '        <feed>overlay-video</feed>\n'
             '      </eater>\n'
             '      \n'
             '      <property name="keyframe-maxdistance">64</property>\n'
             '      <property name="noise-sensitivity">1</property>\n'
             '      <property name="quality">16</property>\n'
             '      <property name="sharpness">0</property>\n'
             '    </component>\n'
             '    <component name="overlay-video" type="overlay-converter" project="flumotion" worker="overlay-worker" version="%(version)s">\n'
             '      <eater name="default">\n'
             '        <feed>video-producer</feed>\n'
             '      </eater>\n'
             '      \n'
             '      <property name="fluendo-logo">True</property>\n'
             '      <property name="height">240</property>\n'
             '      <property name="text">Fluendo</property>\n'
             '      <property name="width">320</property>\n'
             '      <property name="xiph-logo">True</property>\n'
             '    </component>\n'
             '    <component name="muxer-audio-video" type="ogg-muxer" project="flumotion" worker="muxer-worker" version="%(version)s">\n'
             '      <eater name="default">\n'
             '        <feed>encoder-audio</feed>\n'
             '        <feed>encoder-video</feed>\n'
             '      </eater>\n'
             '    </component>\n'
             '  </flow>\n'
             '</planet>\n' % dict(version=configure.version)),
            configuration)

    def testAudioOnlyStream(self):
        save = WizardSaver()
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
        streamer.worker = 'worker'
        save.addConsumer(streamer, 'audio-only')

        configuration = save.getXML()
        testsuite.diffStrings(
            ('<planet>\n'
             '  <flow name="flow">\n'
             '    <component name="http-audio-only" type="http-streamer" project="flumotion" worker="worker" version="%(version)s">\n'
             '      <eater name="default">\n'
             '        <feed>muxer-audio-only</feed>\n'
             '      </eater>\n'
             '      \n'
             '      <property name="burst-on-connect">False</property>\n'
             '      <property name="port">8080</property>\n'
             '    </component>\n'
             '    <component name="producer-audio" type="audiotest-producer" project="flumotion" worker="worker" version="%(version)s">\n'
             '      \n'
             '      <property name="rate">44100</property>\n'
             '    </component>\n'
             '    <component name="encoder-audio" type="vorbis-encoder" project="flumotion" worker="worker" version="%(version)s">\n'
             '      <eater name="default">\n'
             '        <feed>producer-audio</feed>\n'
             '      </eater>\n'
             '      \n'
             '      <property name="bitrate">64000</property>\n'
             '    </component>\n'
             '  </flow>\n'
             '</planet>\n' % dict(version=configure.version)),
            configuration)

    def testFirewireStreamer(self):
        save = WizardSaver()
        save.setFlowName('flow')

        videoProducer = self._createFirewireVideoProducer()
        save.setAudioProducer(videoProducer)
        save.setVideoProducer(videoProducer)
        save.setVideoOverlay(self._createVideoOverlay(videoProducer))
        save.setAudioEncoder(self._createAudioEncoder())
        save.setVideoEncoder(self._createVideoEncoder())

        save.setMuxer('default-muxer', 'muxer-worker')

        streamer = self._createHTTPStreamer()
        streamer.worker = 'streamer-worker'
        save.addConsumer(streamer, 'audio-video')

        server = HTTPServer('server-worker', '/mount/')
        save.addServerConsumer(server, 'audio-video')

        porter = HTTPPorter(streamer)
        save.addPorter(porter, 'audio-video')

        save.setUseCCLicense(True)

        configuration = save.getXML()
        testsuite.diffStrings(
            ('<planet>\n'
             '  <atmosphere>\n'
             '    <component name="porter-audio-video" type="porter" '
             'project="flumotion" worker="streamer-worker" version="%(version)s">\n'
             '      \n'
             '      <property name="password">password</property>\n'
             '      <property name="port">8080</property>\n'
             '      <property name="socket-path">flu-XXXX.socket</property>\n'
             '      <property name="username">username</property>\n'
             '    </component>\n'
             '  </atmosphere>\n'
             '  <flow name="flow">\n'
             '    <component name="http-audio-video" type="http-streamer" '
             'project="flumotion" worker="streamer-worker" version="%(version)s">\n'
             '      <eater name="default">\n'
             '        <feed>muxer-audio-video</feed>\n'
             '      </eater>\n'
             '      \n'
             '      <property name="burst-on-connect">False</property>\n'
             '      <property name="port">8080</property>\n'
             '    </component>\n'
             '    <component name="http-server-audio-video" type="http-server" '
             'project="flumotion" worker="server-worker" version="%(version)s">\n'
             '      \n'
             '      <property name="mount-point">/mount/</property>\n'
             '    </component>\n'
             '    <component name="encoder-audio" type="audio-encoder" '
             'project="flumotion" worker="audio-encoder-worker" version="%(version)s">\n'
             '      <eater name="default">\n'
             '        <feed>producer-audio-video</feed>\n'
             '      </eater>\n'
             '    </component>\n'
             '    <component name="producer-audio-video" '
             'type="firewire-producer" project="flumotion" '
             'worker="firewire-video-producer-worker" version="%(version)s">\n'
             '      \n'
             '      <property name="height">480</property>\n'
             '      <property name="is-square">False</property>\n'
             '      <property name="width">640</property>\n'
             '    </component>\n'
             '    <component name="encoder-video" type="video-encoder" '
             'project="flumotion" worker="video-encoder-worker" version="%(version)s">\n'
             '      <eater name="default">\n'
             '        <feed>overlay-video</feed>\n'
             '      </eater>\n'
             '    </component>\n'
             '    <component name="overlay-video" type="overlay-converter" '
             'project="flumotion" worker="overlay-worker" version="%(version)s">\n'
             '      <eater name="default">\n'
             '        <feed>producer-audio-video</feed>\n'
             '      </eater>\n'
             '      \n'
             '      <property name="cc-logo">True</property>\n'
             '      <property name="fluendo-logo">True</property>\n'
             '      <property name="height">480</property>\n'
             '      <property name="text">Fluendo</property>\n'
             '      <property name="width">640</property>\n'
             '    </component>\n'
             '    <component name="muxer-audio-video" type="default-muxer" '
             'project="flumotion" worker="muxer-worker" version="%(version)s">\n'
             '      <eater name="default">\n'
             '        <feed>encoder-audio</feed>\n'
             '        <feed>encoder-video</feed>\n'
             '      </eater>\n'
             '    </component>\n'
             '  </flow>\n'
             '</planet>\n' % dict(version=configure.version)),
            configuration)

if __name__ == '__main__':
    unittest.main()
