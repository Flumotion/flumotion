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
import time
import os
import random
import gst
import gobject

from twisted.trial import unittest
from twisted.internet import reactor, defer
from flumotion.twisted import integration

from flumotion.component.common.fgdp import fgdp


fgdpServer="""<?xml version="1.0" ?>
<planet>
  <flow name="default">
    <component name="fgdp-audio-video"
               project="flumotion"
               type="fgdp-producer"
               worker="default">

      <property name="username">user</property>
      <property name="password">test</property>
      <property name="port">15000</property>
      <property name="mode">push</property>
    </component>

    <component name="av-decoder"
               project="flumotion"
               type="av-generic-decoder"
               worker="default">
      <source>fgdp-audio-video</source>
    </component>
    <component name="video-encoder"
               project="flumotion"
               type="theora-encoder"
               worker="default">
      <source>av-decoder:video</source>
    </component>
    <component name="audio-encoder"
               project="flumotion"
               type="vorbis-encoder"
               worker="default">
      <source>av-decoder:audio</source>
    </component>
    <component name="muxer"
               project="flumotion"
               type="ogg-muxer"
               worker="default">
      <eater name="default">
        <feed>video-encoder</feed>
      </eater>
      <eater name="default-bis">
        <feed>audio-encoder</feed>
      </eater>
    </component>
  </flow>
</planet>"""


class TestFGDP(common.FlumotionManagerWorkerTest):

    def _setupOggSink(self, _):
        ogg_pipeline = ("videotestsrc ! video/x-raw-yuv,framerate=5/1,"
                        "width=320,height=240 ! theoraenc bitrate=400 ! mux. "
                        "audiotestsrc ! audiorate ! legacyresample ! "
                        "audioconvert ! audio/x-raw-float,channels=2 "
                        "! vorbisenc bitrate=64000 ! mux. "
                        "oggmux name=mux ! fgdpsink "
                        "port=15000 mode=pull user=user password=test")
        self._pipeline = gst.parse_launch(ogg_pipeline)
        self._pipeline.set_state(gst.STATE_PLAYING)

    def _setupWebmSink(self, _):
        webm_pipeline = ("videotestsrc ! video/x-raw-yuv,framerate=5/1,"
                         "width=320,height=240 ! vp8enc bitrate=400 ! mux. "
                         "audiotestsrc ! audiorate ! legacyresample ! "
                         "audioconvert ! audio/x-raw-float,channels=2 "
                         "! vorbisenc bitrate=64000 ! mux. "
                         "webmmux name=mux streamable=true ! fgdpsink "
                         "port=15000 mode=pull user=user password=test")
        self._pipeline = gst.parse_launch(webm_pipeline)
        self._pipeline.set_state(gst.STATE_PLAYING)

    def _stopEncoding(self, _):
        self._pipeline.set_state(gst.STATE_NULL)
        self._pipeline = None

    def _startAndStopPipeline(self, plan, creator):
        p = plan.spawnThread(creator)
        plan.wait(p, 0)
        self.waitForComponentMood(plan, '/default/av-decoder', 'happy')
        self.waitForComponentMood(plan, '/default/muxer', 'happy')
        p = plan.spawnThread(self._stopEncoding)
        plan.wait(p, 0)

        def waitabit(_):
            time.sleep(5)
        p = plan.spawnThread(waitabit)
        plan.wait(p, 0)

    @integration.test
    def testPushOggAndDecodeIt(self, plan):
        m, w = self.spawnAndWaitManagerWorker(plan)

        self.makeFile('server.xml', fgdpServer)
        self.loadConfiguration(plan, 'server.xml')

        self.waitForComponentMood(plan, '/default/fgdp-audio-video', 'hungry')
        self.waitForComponentMood(plan, '/default/av-decoder', 'hungry')

        self._startAndStopPipeline(plan, self._setupOggSink)

        plan.kill(w, 0)
        plan.kill(m, 0)

    @integration.test
    def testPushFlvAndDecodeIt(self, plan):
        m, w = self.spawnAndWaitManagerWorker(plan)

        self.makeFile('server.xml', fgdpServer)
        self.loadConfiguration(plan, 'server.xml')

        self.waitForComponentMood(plan, '/default/fgdp-audio-video', 'hungry')
        self.waitForComponentMood(plan, '/default/av-decoder', 'hungry')

        self._startAndStopPipeline(plan, self._setupFlvSink)

        plan.kill(w, 0)
        plan.kill(m, 0)

    @integration.test
    def testPushWebmAndDecodeIt(self, plan):
        m, w = self.spawnAndWaitManagerWorker(plan)

        self.makeFile('server.xml', fgdpServer)
        self.loadConfiguration(plan, 'server.xml')

        self.waitForComponentMood(plan, '/default/fgdp-audio-video', 'hungry')
        self.waitForComponentMood(plan, '/default/av-decoder', 'hungry')

        self._startAndStopPipeline(plan, self._setupWebmSink)

        plan.kill(w, 0)
        plan.kill(m, 0)

    @integration.test
    def testTortureDecoder(self, plan):
        m, w = self.spawnAndWaitManagerWorker(plan)

        self.makeFile('server.xml', fgdpServer)
        self.loadConfiguration(plan, 'server.xml')

        self.waitForComponentMood(plan, '/default/fgdp-audio-video', 'hungry')
        self.waitForComponentMood(plan, '/default/av-decoder', 'hungry')

        for i in range(0, 5):
            self._startAndStopPipeline(plan, self._setupWebmSink)
            self._startAndStopPipeline(plan, self._setupOggSink)

        plan.kill(w, 0)
        plan.kill(m, 0)
