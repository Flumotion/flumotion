# -*- Mode: Python -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# Flumotion - a streaming media server
# Copyright (C) 2004,2005,2006,2007 Fluendo, S.L. (www.fluendo.com).
# All rights reserved.

# Licensees having purchased or holding a valid Flumotion Advanced
# Streaming Server license may use this file in accordance with the
# Flumotion Advanced Streaming Server Commercial License Agreement.
# See "LICENSE.Flumotion" in the source distribution for more information.

# Headers in this file shall remain intact.


import common
import os
import random

from twisted.trial import unittest
from flumotion.twisted import integration

httpFileXML = """<?xml version="1.0" ?>
<planet>
  <flow name="default">
    <component type="http-server" name="httpfile" worker="default">
      <property name="port">%d</property>
      <property name="mount-point">/blah</property>
      <property name="path">%s</property>
      <property name="type">master</property>
    </component>
  </flow>
</planet>"""

videoTestNoOverlayXML = """<?xml version="1.0" ?>
<planet>
  <flow name="default">
    <component name="video-source" project="flumotion"
               type="videotest-producer"
               version="0.3.0.1" worker="default">
      <!-- properties -->
      <property name="format">video/x-raw-yuv</property>
      <property name="framerate">50/10</property>
      <property name="height">24</property>
      <property name="pattern">0</property>
      <property name="width">32</property>
    </component>
    <component name="video-encoder" project="flumotion" type="theora-encoder"
               version="0.3.0.1" worker="default">
      <source>video-source</source>
      <!-- properties -->
      <property name="bitrate">400000</property>
    </component>
    <component name="muxer-video" project="flumotion" type="ogg-muxer"
               version="0.3.0.1" worker="default">
      <source>video-encoder</source>
    </component>
    <component name="http-video" project="flumotion" type="http-streamer"
               version="0.3.0.1" worker="default">
      <source>muxer-video</source>
      <!-- properties -->
      <property name="bandwidth-limit">10</property>
      <property name="burst-on-connect">True</property>
      <property name="mount-point">/</property>
      <property name="port">%d</property>
      <property name="client-limit">1024</property>
    </component>
    <component name="disk-video" project="flumotion" type="disk-consumer"
               version="0.3.0.1" worker="default">
      <source>muxer-video</source>
      <!-- properties -->
      <property name="directory">%s</property>
      <property name="rotate-type">time</property>
      <property name="time">43200</property>
    </component>
  </flow>
</planet>"""

videoTestNoOverlayWithTokenBouncerXML = """<?xml version="1.0" ?>
<planet>
  <atmosphere>
    <component name="tokenbouncer" project="flumotion"
               type="tokentest-bouncer" version="0.3.0.1" worker="default">
      <property name="authorized-token">test</property>
    </component>
  </atmosphere>
  <flow name="default">
    <component name="video-source" project="flumotion"
               type="videotest-producer" version="0.3.0.1" worker="default">
      <!-- properties -->
      <property name="format">video/x-raw-yuv</property>
      <property name="framerate">50/10</property>
      <property name="height">24</property>
      <property name="pattern">0</property>
      <property name="width">32</property>
    </component>
    <component name="video-encoder" project="flumotion"
               type="theora-encoder" version="0.3.0.1" worker="default">
      <source>video-source</source>
      <!-- properties -->
      <property name="bitrate">400000</property>
    </component>
    <component name="muxer-video" project="flumotion" type="ogg-muxer"
               version="0.3.0.1" worker="default">
      <source>video-encoder</source>
    </component>
    <component name="http-video" project="flumotion" type="http-streamer"
               version="0.3.0.1" worker="default">
      <source>muxer-video</source>
      <!-- properties -->
      <property name="bandwidth-limit">10</property>
      <property name="burst-on-connect">True</property>
      <property name="mount-point">/</property>
      <property name="port">%d</property>
      <property name="client-limit">1024</property>
      <property name="issuer-class">HTTPTokenIssuer</property>
      <property name="bouncer">tokenbouncer</property>
    </component>
  </flow>
</planet>"""

audioTestXML="""<?xml version="1.0" ?>
<planet>
  <flow name="default">
    <component name="audio-source" project="flumotion"
               type="audiotest-producer" version="0.3.0.1" worker="default">

      <property name="frequency">440</property>
      <property name="rate">8000</property>
      <property name="volume">1.0</property>
    </component>

    <component name="audio-encoder" project="flumotion"
               type="vorbis-encoder" version="0.3.0.1" worker="default">
      <source>audio-source</source>

      <property name="quality">0.5</property>
    </component>

    <component name="muxer-audio" project="flumotion"
               type="ogg-muxer" version="0.3.0.1" worker="default">
      <source>audio-encoder</source>
    </component>
    <component name="http-audio" project="flumotion"
               type="http-streamer" version="0.3.0.1" worker="default">
      <source>muxer-audio</source>

      <property name="bandwidth-limit">10</property>
      <property name="burst-on-connect">True</property>
      <property name="mount-point">/</property>
      <property name="port">%d</property>
      <property name="client-limit">1024</property>
    </component>

    <component name="disk-audio" project="flumotion"
               type="disk-consumer" version="0.3.0.1" worker="default">
      <source>muxer-audio</source>

      <property name="directory">%s</property>
      <property name="rotate-type">time</property>
      <property name="time">43200</property>
    </component>

  </flow>
</planet>"""

videoTestXML = """<?xml version="1.0" ?>
<planet>
  <flow name="default">
    <component name="video-source" project="flumotion"
               type="videotest-producer" version="0.3.0.1" worker="default">

      <property name="format">video/x-raw-yuv</property>
      <property name="framerate">50/10</property>
      <property name="height">120</property>
      <property name="pattern">0</property>
      <property name="width">160</property>
    </component>

    <component name="video-overlay" project="flumotion"
               type="overlay-converter" version="0.3.0.1" worker="default">
      <source>video-source</source>

      <property name="cc-logo">True</property>
      <property name="fluendo-logo">True</property>
      <property name="height">240</property>
      <property name="show-text">True</property>
      <property name="text">Fluendo</property>
      <property name="width">320</property>
      <property name="xiph-logo">True</property>
    </component>

    <component name="video-encoder" project="flumotion"
               type="theora-encoder" version="0.3.0.1" worker="default">
      <source>video-overlay</source>

      <property name="bitrate">400000</property>
    </component>

    <component name="muxer-video" project="flumotion"
               type="ogg-muxer" version="0.3.0.1" worker="default">
      <source>video-encoder</source>
    </component>

    <component name="http-video" project="flumotion"
               type="http-streamer" version="0.3.0.1" worker="default">
      <source>muxer-video</source>

      <property name="bandwidth-limit">10</property>
      <property name="burst-on-connect">True</property>
      <property name="mount-point">/</property>
      <property name="port">%d</property>
      <property name="client-limit">1024</property>
    </component>

    <component name="disk-video" project="flumotion"
               type="disk-consumer" version="0.3.0.1" worker="default">
      <source>muxer-video</source>

      <property name="directory">%s</property>
      <property name="rotate-type">time</property>
      <property name="time">43200</property>
    </component>

  </flow>
</planet>"""


class TestFlumotion(common.FlumotionManagerWorkerTest):

    def testManagerWorker(self, plan):
        m, w = self.spawnAndWaitManagerWorker(plan)
        plan.kill(w, 0)
        plan.kill(m, 0)
    testManagerWorker = integration.test(testManagerWorker)

    def testHttpFile(self, plan):
        m, w = self.spawnAndWaitManagerWorker(plan)
        httpPort = random.randrange(12800, 12899)
        self.makeFile('httpfile-config.xml', httpFileXML % (httpPort,
            __file__))
        self.loadConfiguration(plan, 'httpfile-config.xml')
        self.waitForHappyComponent(plan, '/default/httpfile')
        # wait for httpfile
        h = plan.spawn('wait-for-http-port', 'http://localhost:%d/blah' % (
            httpPort))
        plan.wait(h, 0)
        plan.kill(w, 0)
        plan.kill(m, 0)
    testHttpFile = integration.test(testHttpFile)

    def testVideoTestNoOverlay(self, plan):
        m, w = self.spawnAndWaitManagerWorker(plan)
        httpPort = random.randrange(12800, 12899)
        self.makeFile('videotest-nooverlay.xml', videoTestNoOverlayXML % (
            httpPort, os.getcwd()))
        self.loadConfiguration(plan, 'videotest-nooverlay.xml')
        self.waitForHappyComponent(plan, '/default/video-source')
        self.waitForHappyComponent(plan, '/default/muxer-video')
        self.waitForHappyComponent(plan, '/default/http-video')
        self.waitForHappyComponent(plan, '/default/disk-video')
        h = plan.spawn('wait-for-http-headers', 'http://localhost:%d/' % (
            httpPort, ))
        plan.wait(h, 0)
        # now check files saved by disker
        cft = plan.spawn('check-disker-file-type', 'Ogg',
            'user:test@localhost:%d' % self.managerPort, '/default/disk-video')
        plan.wait(cft, 0)
        # clean up disk files
        clean = plan.spawn('remove-disker-files', 'user:test@localhost:%d' % (
            self.managerPort, ), '/default/disk-video')
        plan.wait(clean, 0)
        plan.kill(w, 0)
        plan.kill(m, 0)
    testVideoTestNoOverlay = integration.test(testVideoTestNoOverlay)

    def testVideoTestNoOverlayWithTokenBouncer(self, plan):
        m, w = self.spawnAndWaitManagerWorker(plan)
        httpPort = random.randrange(12800, 12899)
        self.makeFile('tokenbouncer.xml',
            videoTestNoOverlayWithTokenBouncerXML % httpPort)
        self.loadConfiguration(plan, 'tokenbouncer.xml')
        self.waitForHappyComponent(plan, '/default/video-source')
        self.waitForHappyComponent(plan, '/default/muxer-video')
        self.waitForHappyComponent(plan, '/default/http-video')
        self.waitForHappyComponent(plan, '/atmosphere/tokenbouncer')
        h = plan.spawn('check-token-for-http', 'http://localhost:%d/' % (
            httpPort, ), 'test', 'badtoken')
        plan.wait(h, 0)
        plan.kill(w, 0)
        plan.kill(m, 0)
    testVideoTestNoOverlayWithTokenBouncer = integration.test(
        testVideoTestNoOverlayWithTokenBouncer)

    def testAudioTest(self, plan):
        m, w = self.spawnAndWaitManagerWorker(plan)
        httpPort = random.randrange(12800, 12899)
        self.makeFile('audiotest.xml',
            audioTestXML % (httpPort, os.getcwd()))
        self.loadConfiguration(plan, 'audiotest.xml')
        self.waitForHappyComponent(plan, '/default/http-audio')
        self.waitForHappyComponent(plan, '/default/disk-audio')
        h = plan.spawn('wait-for-http-headers', 'http://localhost:%d/' % (
            httpPort, ))
        plan.wait(h, 0)
        # now check files saved by disker
        cft = plan.spawn('check-disker-file-type', 'Ogg',
            'user:test@localhost:%d' % self.managerPort, '/default/disk-audio')
        plan.wait(cft, 0)
        # clean up disk files
        clean = plan.spawn('remove-disker-files', 'user:test@localhost:%d' % (
            self.managerPort, ), '/default/disk-audio')
        plan.wait(clean, 0)

        plan.kill(w, 0)
        plan.kill(m, 0)
    testAudioTest = integration.test(testAudioTest)

    def testVideoTestWithOverlay(self, plan):
        m, w = self.spawnAndWaitManagerWorker(plan)
        httpPort = random.randrange(12800, 12899)
        self.makeFile('videotest.xml',
            videoTestXML % (httpPort, os.getcwd()))
        self.loadConfiguration(plan, 'videotest.xml')
        self.waitForHappyComponent(plan, '/default/video-source')
        self.waitForHappyComponent(plan, '/default/muxer-video')
        self.waitForHappyComponent(plan, '/default/http-video')
        self.waitForHappyComponent(plan, '/default/disk-video')
        h = plan.spawn('wait-for-http-headers', 'http://localhost:%d/' % (
            httpPort, ))
        plan.wait(h, 0)
        # change filename with disker
        cft = plan.spawn('check-disker-file-type', 'Ogg',
            'user:test@localhost:%d' % self.managerPort, '/default/disk-video')
        plan.wait(cft, 0)
        # clean up disk files
        clean = plan.spawn('remove-disker-files', 'user:test@localhost:%d' % (
            self.managerPort, ), '/default/disk-video')
        plan.wait(clean, 0)

        plan.kill(w, 0)
        plan.kill(m, 0)
    testVideoTestWithOverlay = integration.test(testVideoTestWithOverlay)
