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
from flumotion.component.consumers.httpstreamer.httpstreamer_wizard import \
     HTTPPorter, HTTPStreamer
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
             'project="flumotion" worker="worker" version="0.5.1.1">\n'
             '    </component>\n'
             '  </flow>\n'
             '</planet>\n'),
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
             'project="flumotion" worker="worker" version="0.5.1.1">\n'
             '      \n'
             '      <property name="foo">bar</property>\n'
             '    </component>\n'
             '  </atmosphere>\n'
             '</planet>\n'),
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
             'project="flumotion" worker="worker" version="0.5.1.1">\n'
             '      \n'
             '      <plugs>\n'
             '        <plug type="plug-type">\n'
             '          \n'
             '          <property name="foo">bar</property>\n'
             '        </plug>\n'
             '      </plugs>\n'
             '    </component>\n'
             '  </flow>\n'
             '</planet>\n'),
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
             'project="flumotion" worker="worker" version="0.5.1.1">\n'
             '      <eater name="default">\n'
             '        <feed>name</feed>\n'
             '      </eater>\n'
             '    </component>\n'
             '    <component name="name" type="second" '
             'project="flumotion" worker="worker" version="0.5.1.1">\n'
             '    </component>\n'
             '  </flow>\n'
             '</planet>\n'),
            writer.getXML())


class TestWizardSave(testsuite.TestCase):
    def testDefaultStream(self):
        save = WizardSaver()
        save.setFlowName('flow')

        audioProducer = AudioProducer()
        audioProducer.component_type = 'audio-producer'
        audioProducer.worker = 'audio-producer-worker'
        save.setAudioProducer(audioProducer)
        videoProducer = VideoProducer()
        videoProducer.component_type = 'video-producer'
        videoProducer.worker = 'video-producer-worker'
        videoProducer.properties.width = 640
        videoProducer.properties.height = 480
        save.setVideoProducer(videoProducer)

        overlay = Overlay(videoProducer)
        overlay.worker = 'overlay-worker'
        save.setVideoOverlay(overlay)

        audioEncoder = AudioEncoder()
        audioEncoder.component_type = 'audio-encoder'
        audioEncoder.worker = 'audio-encoder-worker'
        videoEncoder = VideoEncoder()
        videoEncoder.component_type = 'video-encoder'
        videoEncoder.worker = 'video-encoder-worker'
        save.setAudioEncoder(audioEncoder)
        save.setVideoEncoder(videoEncoder)
        save.setMuxer('ogg-muxer', 'muxer-worker')

        streamer = HTTPStreamer()
        streamer.properties.port = 8080
        streamer.socket_path = 'flu-XXXX.socket'
        streamer.porter_username = 'username'
        streamer.porter_password = 'password'
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
             'project="flumotion" worker="streamer-worker" version="0.5.1.1">\n'
             '      \n'
             '      <property name="password">password</property>\n'
             '      <property name="port">8080</property>\n'
             '      <property name="socket-path">flu-XXXX.socket</property>\n'
             '      <property name="username">username</property>\n'
             '    </component>\n'
             '  </atmosphere>\n'
             '  <flow name="flow">\n'
             '    <component name="http-audio-video" type="http-streamer" '
             'project="flumotion" worker="streamer-worker" version="0.5.1.1">\n'
             '      <eater name="default">\n'
             '        <feed>muxer-audio-video</feed>\n'
             '      </eater>\n'
             '      \n'
             '      <property name="port">8080</property>\n'
             '    </component>\n'
             '    <component name="http-server-audio-video" type="http-server" '
             'project="flumotion" worker="server-worker" version="0.5.1.1">\n'
             '      \n'
             '      <property name="mount-point">/mount/</property>\n'
             '    </component>\n'
             '    <component name="producer-audio" type="audio-producer" '
             'project="flumotion" worker="audio-producer-worker" version="0.5.1.1">\n'
             '    </component>\n'
             '    <component name="encoder-audio" type="audio-encoder" '
             'project="flumotion" worker="audio-encoder-worker" version="0.5.1.1">\n'
             '      <eater name="default">\n'
             '        <feed>producer-audio</feed>\n'
             '      </eater>\n'
             '    </component>\n'
             '    <component name="video-producer" type="video-producer" '
             'project="flumotion" worker="video-producer-worker" version="0.5.1.1">\n'
             '      \n'
             '      <property name="height">480</property>\n'
             '      <property name="width">640</property>\n'
             '    </component>\n'
             '    <component name="encoder-video" type="video-encoder" '
             'project="flumotion" worker="video-encoder-worker" version="0.5.1.1">\n'
             '      <eater name="default">\n'
             '        <feed>overlay-video</feed>\n'
             '      </eater>\n'
             '    </component>\n'
             '    <component name="overlay-video" type="overlay-converter" '
             'project="flumotion" worker="overlay-worker" version="0.5.1.1">\n'
             '      <eater name="default">\n'
             '        <feed>video-producer</feed>\n'
             '      </eater>\n'
             '      \n'
             '      <property name="cc-logo">True</property>\n'
             '      <property name="fluendo-logo">True</property>\n'
             '      <property name="height">480</property>\n'
             '      <property name="text">Fluendo</property>\n'
             '      <property name="width">640</property>\n'
             '      <property name="xiph-logo">True</property>\n'
             '    </component>\n'
             '    <component name="muxer-audio-video" type="ogg-muxer" '
             'project="flumotion" worker="muxer-worker" version="0.5.1.1">\n'
             '      <eater name="default">\n'
             '        <feed>encoder-audio</feed>\n'
             '        <feed>encoder-video</feed>\n'
             '      </eater>\n'
             '    </component>\n'
             '  </flow>\n'
             '</planet>\n'),
            configuration)

if __name__ == '__main__':
    unittest.main()
