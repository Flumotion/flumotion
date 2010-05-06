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

import gst

from twisted.internet import defer, reactor
from twisted.trial import unittest

from flumotion.common import testsuite
from flumotion.component import padmonitor

attr = testsuite.attr


@attr('slow')
class TestPadMonitor(testsuite.TestCase):

    def _run_pipeline(self, pipeline):
        pipeline.set_state(gst.STATE_PLAYING)
        pipeline.get_bus().poll(gst.MESSAGE_EOS, -1)
        pipeline.set_state(gst.STATE_NULL)

    def testPadMonitorActivation(self):
        pipeline = gst.parse_launch(
            'fakesrc num-buffers=1 ! identity name=id ! fakesink')
        identity = pipeline.get_by_name('id')

        srcpad = identity.get_pad('src')
        monitor = padmonitor.PadMonitor(srcpad, "identity-source",
                                        lambda name: None,
                                        lambda name: None)
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
        padmonitor.PadMonitor.PAD_MONITOR_PROBE_FREQUENCY = 0.2
        padmonitor.PadMonitor.PAD_MONITOR_TIMEOUT = 0.5

        pipeline = gst.parse_launch(
            'fakesrc num-buffers=1 ! identity name=id ! fakesink')
        identity = pipeline.get_by_name('id')

        srcpad = identity.get_pad('src')

        # Now give the reactor a chance to process the callFromThread()

        def finished():
            monitor.detach()
            d.callback(True)

        def hasInactivated(name):
            # We can't detach the monitor from this callback safely, so do
            # it from a reactor.callLater()
            reactor.callLater(0, finished)

        def hasActivated():
            self.assertEquals(monitor.isActive(), True)
            # Now, we don't send any more data, and after our 0.5 second
            # timeout we should go inactive. Pass our test if that happens.
            # Otherwise trial will time out.

        monitor = padmonitor.PadMonitor(srcpad, "identity-source",
                                        lambda name: None,
                                        hasInactivated)
        self.assertEquals(monitor.isActive(), False)

        self._run_pipeline(pipeline)

        d = defer.Deferred()

        reactor.callLater(0.2, hasActivated)

        return d

if __name__ == '__main__':
    unittest.main()
