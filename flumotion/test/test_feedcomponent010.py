# -*- Mode: Python; test-case-name: flumotion.test.test_feedcomponent010 -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# Flumotion - a streaming media server
# Copyright (C) 2004,2005,2006,2007 Fluendo, S.L. (www.fluendo.com).
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

import time
import gobject
gobject.threads_init()
import pygst
pygst.require('0.10')
import gst

from twisted.trial import unittest

import common

from twisted.python import failure
from twisted.internet import defer, reactor

from flumotion.component import feedcomponent010 as fc

class TestFeeder(unittest.TestCase):
    def setUp(self):
        self.feeder = fc.Feeder('video:default')

    def test_clientConnected(self):
        clientId = '/default/muxer-video'
        client = self.feeder.clientConnected(clientId, 3, lambda _: None)
        clients = self.feeder.getClients()
        self.failUnless(client in clients)
        self.assertEquals(client.uiState.get('clientId'), clientId)

    def testReconnect(self):
        clientId = '/default/muxer-video'

        # This needed because disconnecting clients only updates the stats in 
        # a callFromThread (which is roughly the same as a callLater).
        d = defer.Deferred()

        def checkClientDisconnected():
            self.clientAssertStats(c, 0, 0, 10, 1, 1)
        
            # connect again
            self.feeder.clientConnected(clientId, 3, lambda _: None)
            self.clientAssertStats(c, 0, 0, 10, 1, 2)

            # read 20 bytes, drop 2 buffers
            c.setStats((20, None, None, None, time.time(), 2))
            self.clientAssertStats(c, 20, 2, 30, 3, 2)

            d.callback(None)

        # connect
        c = self.feeder.clientConnected(clientId, 3, lambda _: None)

        # verify some stuff
        self.clientAssertStats(c, 0, None, 0, None, 1)

        # read 10 bytes, drop 1 buffer
        c.setStats((10, None, None, None, time.time(), 1))
        self.clientAssertStats(c, 10, 1, 10, 1, 1)

        # remove client
        self.feeder.clientDisconnected(3)

        reactor.callLater(0, checkClientDisconnected)

        return d

    def clientAssertEquals(self, client, key, value):
        self.assertEquals(client.uiState.get(key), value)

    def clientAssertStats(self, client, brc, bdc, brt, bdt, reconnects):
        self.clientAssertEquals(client, 'bytesReadCurrent', brc)
        self.clientAssertEquals(client, 'buffersDroppedCurrent', bdc)
        self.clientAssertEquals(client, 'bytesReadTotal', brt)
        self.clientAssertEquals(client, 'buffersDroppedTotal', bdt)
        self.clientAssertEquals(client, 'reconnects', reconnects)

class FakeComponent(object):
    def setPadMonitorActive(self, name):
        pass

    def setPadMonitorInactive(self, name):
        pass

class TestPadMonitor(unittest.TestCase):

    def _run_pipeline(self, pipeline):
        pipeline.set_state(gst.STATE_PLAYING)
        pipeline.get_bus().poll(gst.MESSAGE_EOS, -1)
        pipeline.set_state(gst.STATE_NULL)
        
    def testPadMonitorActivation(self):
        component = FakeComponent()
        pipeline = gst.parse_launch(
            'fakesrc num-buffers=1 ! identity name=id ! fakesink')
        identity = pipeline.get_by_name('id')

        srcpad = identity.get_pad('src')
        monitor = fc.PadMonitor(component, srcpad, 
            "identity-source")
        self.assertEquals(monitor.isActive(), False)

        self._run_pipeline(pipeline)
        # Now give the reactor a chance to process the callFromThread()
        d = defer.Deferred()
        def finishTest():
            self.assertEquals(monitor.isActive(), True)
            monitor.detach()
            d.callback(True)
        reactor.callLater(0.1, finishTest)

        return d

    def testPadMonitorTimeout(self):
        fc.PadMonitor.PAD_MONITOR_PROBE_FREQUENCY = 0.2
        fc.PadMonitor.PAD_MONITOR_TIMEOUT = 0.5

        component = FakeComponent()
        pipeline = gst.parse_launch(
            'fakesrc num-buffers=1 ! identity name=id ! fakesink')
        identity = pipeline.get_by_name('id')

        srcpad = identity.get_pad('src')
        monitor = fc.PadMonitor(component, srcpad, 
            "identity-source")
        self.assertEquals(monitor.isActive(), False)

        self._run_pipeline(pipeline)
        # Now give the reactor a chance to process the callFromThread()
        d = defer.Deferred()
        def finished():
            monitor.detach()
            d.callback(True)

        def hasInactivated(name):
            # We can't detach the monitor from this callback safely, so do
            # it from a reactor.callLater()
            reactor.callLater(0, finished)
            
        def hasActivated():
            self.assertEquals(monitor.isActive(), True)
            # Now, we don't send any more data, and after our 0.5 second timeout
            # we should go inactive. Pass our test if that happens. Otherwise
            # trial will time out.
            component.setPadMonitorInactive = hasInactivated
        reactor.callLater(0.1, hasActivated)

        return d

if __name__ == '__main__':
    unittest.main()
