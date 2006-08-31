# -*- Mode: Python -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# Flumotion - a streaming media server
# Copyright (C) 2004,2005,2006 Fluendo, S.L. (www.fluendo.com).
# All rights reserved.

# Licensees having purchased or holding a valid Flumotion Advanced
# Streaming Server license may use this file in accordance with the
# Flumotion Advanced Streaming Server Commercial License Agreement.
# See "LICENSE.Flumotion" in the source distribution for more information.

# Headers in this file shall remain intact.


import common
import time
import os
import random

from twisted.trial import unittest
from flumotion.twisted import integration

httpFileXML = """<?xml version="1.0" ?>
<planet>
  <flow name="default">
    <component type="httpfile" name="httpfile" worker="default">
      <property name="port">%d</property>
      <property name="mount_point">/blah</property>
      <property name="path_to_file">%s</property>
      <property name="type">master</property>
    </component>
  </flow>
</planet>"""

videoTestNoOverlayXML = """<?xml version="1.0" ?>
<planet>
  <flow name="default">
    <component name="video-source" project="flumotion" type="videotest" version="0.3.0.1" worker="default">
      <!-- properties -->
      <property name="format">video/x-raw-yuv</property>
      <property name="framerate">50/10</property>
      <property name="height">240</property>
      <property name="pattern">0</property>
      <property name="width">320</property>
    </component>
    <component name="video-encoder" project="flumotion" type="theora-encoder" version="0.3.0.1" worker="default">
      <source>video-source</source>
      <!-- properties -->
      <property name="bitrate">400</property>
    </component>
    <component name="muxer-video" project="flumotion" type="ogg-muxer" version="0.3.0.1" worker="default">
      <source>video-encoder</source>
    </component>
    <component name="http-video" project="flumotion" type="http-streamer" version="0.3.0.1" worker="default">
      <source>muxer-video</source>
      <!-- properties -->
      <property name="bandwidth_limit">10</property>
      <property name="burst_on_connect">True</property>
      <property name="mount_point">/</property>
      <property name="port">%d</property>
      <property name="user_limit">1024</property>
    </component>
    <component name="disk-video" project="flumotion" type="disker" version="0.3.0.1" worker="default">
      <source>muxer-video</source>
      <!-- properties -->
      <property name="directory">%s</property>
      <property name="rotateType">time</property>
      <property name="time">43200</property>
    </component>
  </flow>
</planet>"""

videoTestNoOverlayWithTokenBouncerXML = """<?xml version="1.0" ?>
<planet>
  <atmosphere>
    <component name="tokenbouncer" project="flumotion" type="tokentestbouncer" version="0.3.0.1" worker="default">
      <property name="authorized-token">test</property>
    </component>
  </atmosphere>
  <flow name="default">
    <component name="video-source" project="flumotion" type="videotest" version="0.3.0.1" worker="default">
      <!-- properties -->
      <property name="format">video/x-raw-yuv</property>
      <property name="framerate">50/10</property>
      <property name="height">240</property>
      <property name="pattern">0</property>
      <property name="width">320</property>
    </component>
    <component name="video-encoder" project="flumotion" type="theora-encoder" version="0.3.0.1" worker="default">
      <source>video-source</source>
      <!-- properties -->
      <property name="bitrate">400</property>
    </component>
    <component name="muxer-video" project="flumotion" type="ogg-muxer" version="0.3.0.1" worker="default">
      <source>video-encoder</source>
    </component>
    <component name="http-video" project="flumotion" type="http-streamer" version="0.3.0.1" worker="default">
      <source>muxer-video</source>
      <!-- properties -->
      <property name="bandwidth_limit">10</property>
      <property name="burst_on_connect">True</property>
      <property name="mount_point">/</property>
      <property name="port">%d</property>
      <property name="user_limit">1024</property>
      <property name="issuer">HTTPTokenIssuer</property>
      <property name="bouncer">tokenbouncer</property>
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
        httpPort = random.randrange(12800,12899)
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
        httpPort = random.randrange(12800,12899)
        self.makeFile('videotest-nooverlay.xml', videoTestNoOverlayXML % (
            httpPort, os.getcwd()))
        self.loadConfiguration(plan, 'videotest-nooverlay.xml')
        self.waitForHappyComponent(plan, '/default/http-video')
        self.waitForHappyComponent(plan, '/default/disk-video')
        h = plan.spawn('wait-for-http-headers', 'http://localhost:%d/' % (
            httpPort,))
        plan.wait(h, 0)
        # now check files saved by disker
        cft = plan.spawn('check-file-type', 
            os.path.join(os.getcwd(), "disk-video*.ogg"),
            'Ogg')
        plan.wait(cft, 0)
        plan.kill(w, 0)
        plan.kill(m, 0)
    testVideoTestNoOverlay = integration.test(testVideoTestNoOverlay)

    def testVideoTestNoOverlayWithTokenBouncer(self, plan):
        m, w = self.spawnAndWaitManagerWorker(plan)
        httpPort = random.randrange(12800, 12899)
        self.makeFile('tokenbouncer.xml', 
            videoTestNoOverlayWithTokenBouncerXML % httpPort)
        self.loadConfiguration(plan, 'tokenbouncer.xml')
        self.waitForHappyComponent(plan, '/default/http-video')
        self.waitForHappyComponent(plan, '/atmosphere/tokenbouncer')
        h = plan.spawn('check-token-for-http', 'http://localhost:%d/' % (
            httpPort,), 'test', 'badtoken')
        plan.wait(h, 0)
        plan.kill(w, 0)
        plan.kill(m, 0)
    testVideoTestNoOverlayWithTokenBouncer = integration.test(
        testVideoTestNoOverlayWithTokenBouncer)
