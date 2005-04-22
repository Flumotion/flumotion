# -*- Mode: Python; test-case-name: flumotion.test.test_common_gstreamer -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# Flumotion - a streaming media server
# Copyright (C) 2004,2005 Fluendo, S.L. (www.fluendo.com). All rights reserved.

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

from twisted.trial import unittest
from twisted.internet import reactor

import common

import gst
from flumotion.common import gstreamer

class Factory(unittest.TestCase):
    def testFakeSrc(self):
        hassync = gstreamer.element_factory_has_property('fakesrc', 'sync')
        self.failUnless(hassync)
        hasync = gstreamer.element_factory_has_property('fakesrc', 'ync')
        self.failIf(hasync)

class Caps(unittest.TestCase):
    def testCaps(self):
        caps = gst.caps_from_string('video/x-raw-yuv,width=10,framerate=5.0;video/x-raw-rgb,width=15,framerate=10.0')
        self.assertEquals(gstreamer.caps_repr(caps),
            'video/x-raw-yuv, width=(int)10, framerate=(double)5; video/x-raw-rgb, width=(int)15, framerate=(double)10')

    def testCapsStreamheader(self):
        caps = gst.caps_from_string('application/ogg,streamheader=abcd')
        self.assertEquals(gstreamer.caps_repr(caps),
            'streamheader=<...>')

class FakeComponent:
    def debug(self, string): pass

class DeepNotify(unittest.TestCase):
    def testDeepNotify(self):
        component = FakeComponent()
        pipeline = gst.parse_launch('fakesrc num-buffers=3 ! fakesink')
        pipeline.connect('deep-notify', gstreamer.verbose_deep_notify_cb,
            component)

        for i in range(10):
            pipeline.iterate()

class BinFindSink(unittest.TestCase):
    def testBinFindSinkZero(self):
        p = gst.parse_launch('identity ! identity')
        self.assertEquals(gstreamer.bin_find_sinks(p), [])

    def testBinFindSinkOne(self):
        p = gst.parse_launch('fakesrc ! fakesink name=n')
        l = gstreamer.bin_find_sinks(p)
        self.assertEquals(len(l), 1)
        self.assertEquals(l[0].get_name(), 'n')

    def testBinFindSinkTwo(self):
        p = gst.parse_launch('fakesrc ! fakesink name=n fakesrc ! fakesink name=n2')
        l = gstreamer.bin_find_sinks(p)
        self.assertEquals(len(l), 2)
        self.assertEquals(l[0].get_name(), 'n')
        self.assertEquals(l[1].get_name(), 'n2')

