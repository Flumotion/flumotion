# -*- Mode: Python -*-
# vi:si:et:sw=4:sts=4:ts=4

# Flumotion - a streaming media server
# Copyright (C) 2004,2005,2006,2007,2008,2009 Fluendo, S.L.
# Copyright (C) 2010,2011 Flumotion Services, S.A.
# All rights reserved.
#
# This file may be distributed and/or modified under the terms of
# the GNU Lesser General Public License version 2.1 as published by
# the Free Software Foundation.
# This file is distributed without any warranty; without even the implied
# warranty of merchantability or fitness for a particular purpose.
# See "LICENSE.LGPL" in the source distribution for more information.
#
# Headers in this file shall remain intact.


import common
import time
import os
import random

from twisted.trial import unittest
from flumotion.twisted import integration

audioTestXML="""<?xml version="1.0" ?>
<planet>
  <flow name="default">
    <component name="audio-source" project="flumotion"
               type="audiotest-producer"
               version="0.3.0.1" worker="default">

      <property name="frequency">440</property>
      <property name="samplerate">8000</property>
      <property name="volume">1.0</property>
    </component>

    <component name="audio-encoder" project="flumotion" type="vorbis-encoder"
               version="0.3.0.1" worker="default">
      <source>audio-source</source>

      <property name="quality">0.5</property>
    </component>

    <component name="muxer-audio" project="flumotion" type="ogg-muxer"
               version="0.3.0.1" worker="default">
      <source>audio-encoder</source>
    </component>
    <component name="http-audio" project="flumotion" type="http-streamer"
version="0.3.0.1" worker="default">
      <source>muxer-audio</source>

      <property name="bandwidth-limit">10</property>
      <property name="burst-on-connect">True</property>
      <property name="mount-point">/</property>
      <property name="port">%d</property>
      <property name="client-limit">1024</property>
    </component>

    <component name="disk-audio" project="flumotion" type="disk-consumer"
               version="0.3.0.1" worker="default">
      <source>muxer-audio</source>

      <property name="directory">%s</property>
      <property name="rotate-type">time</property>
      <property name="time">43200</property>
    </component>

  </flow>
</planet>"""


class TestStopStart(common.FlumotionManagerWorkerTest):

    def testAudioTestMultipleStopStarts(self, plan):
        m, w = self.spawnAndWaitManagerWorker(plan)
        httpPort = random.randrange(12800, 12899)
        self.makeFile('audiotest.xml',
            audioTestXML % (httpPort, os.getcwd()))
        self.loadConfiguration(plan, 'audiotest.xml')
        for i in range(0, 10):
            self.waitForHappyComponent(plan, '/default/http-audio')
            self.waitForHappyComponent(plan, '/default/disk-audio')
            self.stopAll(plan)
            self.startAll(plan)
        plan.kill(w, 0)
        plan.kill(m, 0)

    testAudioTestMultipleStopStarts = integration.test(
        testAudioTestMultipleStopStarts)
