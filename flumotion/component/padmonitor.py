# -*- Mode: Python; test-case-name: flumotion.test.test_feedcomponent010 -*-
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

import time

import gst
from twisted.internet import reactor, defer

from flumotion.common import log
from flumotion.common.poller import Poller

__version__ = "$Rev$"


class PadMonitor(log.Loggable):
    """
    I monitor data flow on a GStreamer pad.
    I regularly schedule a buffer probe call at PAD_MONITOR_PROBE_INTERVAL.
    I regularly schedule a check call at PAD_MONITOR_CHECK_INTERVAL
    that makes sure a buffer probe was triggered since the last check call.
    """

    PAD_MONITOR_PROBE_INTERVAL = 5.0
    PAD_MONITOR_CHECK_INTERVAL = PAD_MONITOR_PROBE_INTERVAL * 2.5

    def __init__(self, pad, name, setActive, setInactive):
        """
        @type  pad:         L{gst.Pad}
        @type  name:        str
        @param setActive:   a callable that will be called when the pad is
                            considered active, taking the name of the monitor.
        @type  setActive:   callable
        @param setInactive: a callable that will be called when the pad is
                            considered inactive, taking the name of the
                            monitor.
        @type  setInactive: callable
        """
        self._last_data_time = -1 # system time in epoch secs of last reception
        self._pad = pad
        self.name = name
        self._active = False
        self._first = True
        self._running = True

        self._doSetActive = []
        self._doSetInactive = []
        self.addWatch(setActive, setInactive)

        # This dict sillyness is because python's dict operations are atomic
        # w.r.t. the GIL.
        self._probe_id = {}

        self.check_poller = Poller(self._probe_timeout,
                                   self.PAD_MONITOR_PROBE_INTERVAL,
                                   immediately=True)

        self.watch_poller = Poller(self._check_timeout,
                                   self.PAD_MONITOR_CHECK_INTERVAL)

    def logMessage(self, message, *args):
        if self._first:
            self.debug(message, *args)
        else:
            self.log(message, *args)

    def isActive(self):
        return self._active

    def detach(self):
        self.check_poller.stop()
        self.watch_poller.stop()
        self._running = False

        # implementation closely tied to _probe_timeout wrt to GIL
        # tricks, threadsafety, and getting the probe deferred to
        # actually return
        d, probe_id = self._probe_id.pop("id", (None, None))
        if probe_id:
            self._pad.remove_buffer_probe(probe_id)
            d.callback(None)

    def _probe_timeout(self):
        # called every so often to install a probe callback

        def probe_cb(pad, buffer):
            """
            Periodically scheduled buffer probe, that ensures that we're
            currently actually having dataflow through our eater
            elements.

            Called from GStreamer threads.

            @param pad:       The gst.Pad srcpad for one eater in this
                              component.
            @param buffer:    A gst.Buffer that has arrived on this pad
            """
            self._last_data_time = time.time()

            self.logMessage('buffer probe on %s has timestamp %s', self.name,
                            gst.TIME_ARGS(buffer.timestamp))

            deferred, probe_id = self._probe_id.pop("id", (None, None))
            if probe_id:
                # This will be None only if detach() has been called.
                self._pad.remove_buffer_probe(probe_id)

                reactor.callFromThread(deferred.callback, None)
                # Data received! Return to happy ASAP:
                reactor.callFromThread(self.watch_poller.run)

            self._first = False

            # let the buffer through
            return True

        d = defer.Deferred()
        # FIXME: this is racy: evaluate RHS, drop GIL, buffer probe
        # fires before __setitem__ in LHS; need a mutex
        self._probe_id['id'] = (d, self._pad.add_buffer_probe(probe_cb))
        return d

    def _check_timeout(self):
        # called every so often to check that a probe callback was triggered
        self.log('last buffer for %s at %r', self.name, self._last_data_time)

        now = time.time()

        if self._last_data_time < 0:
            # We never received any data in the first timeout period...
            self._last_data_time = 0
            self.setInactive()
        elif self._last_data_time == 0:
            # still no data...
            pass
        else:
            # We received data at some time in the past.
            delta = now - self._last_data_time

            if self._active and delta > self.PAD_MONITOR_CHECK_INTERVAL:
                self.info("No data received on pad %s for > %r seconds, "
                          "setting to hungry",
                          self.name, self.PAD_MONITOR_CHECK_INTERVAL)
                self.setInactive()
            elif not self._active and delta < self.PAD_MONITOR_CHECK_INTERVAL:
                self.info("Receiving data again on pad %s, flow active",
                    self.name)
                self.setActive()

    def addWatch(self, setActive, setInactive):
        """
        @param setActive:   a callable that will be called when the pad is
                            considered active, taking the name of the monitor.
        @type  setActive:   callable
        @param setInactive: a callable that will be called when the pad is
                            considered inactive, taking the name of the
                            monitor.
        @type  setInactive: callable
        """
        self._doSetActive.append(setActive)
        self._doSetInactive.append(setInactive)

    def setInactive(self):
        self._active = False
        for setInactive in self._doSetInactive:
            setInactive(self.name)

    def setActive(self):
        self._active = True
        for setActive in self._doSetActive:
            setActive(self.name)


class EaterPadMonitor(PadMonitor):

    def __init__(self, pad, name, setActive, setInactive,
                 reconnectEater, *args):
        PadMonitor.__init__(self, pad, name, setActive, setInactive)

        self._reconnectPoller = Poller(lambda: reconnectEater(*args),
                                       self.PAD_MONITOR_CHECK_INTERVAL,
                                       start=False)

    def setInactive(self):
        PadMonitor.setInactive(self)

        # It might be that we got detached while calling
        # PadMonitor.setInactive() For example someone might have
        # stopped the component as it went hungry, which would happen
        # inside the PadMonitor.setInactive() call. The component
        # would then detach us and the reconnect poller would get
        # stopped. If that happened don't bother restarting it, as it
        # will result in the reactor ending up in an unclean state.
        #
        # A prominent example of such situation is
        # flumotion.test.test_component_disker, where the component
        # gets stopped right after it goes hungry
        if self._running:
            # If an eater received a buffer before being marked as
            # disconnected, and still within the buffer check
            # interval, the next eaterCheck call could accidentally
            # think the eater was reconnected properly.  Setting this
            # to 0 here avoids that happening in eaterCheck.
            self._last_data_time = 0

            self.debug('starting the reconnect poller')
            self._reconnectPoller.start(immediately=True)

    def setActive(self):
        PadMonitor.setActive(self)
        self.debug('stopping the reconnect poller')
        self._reconnectPoller.stop()

    def detach(self):
        PadMonitor.detach(self)
        self.debug('stopping the reconnect poller')
        self._reconnectPoller.stop()


class PadMonitorSet(dict, log.Loggable):
    """
    I am a dict of monitor name -> monitor.
    """

    def __init__(self, setActive, setInactive):
        # These callbacks will be called when the set as a whole is
        # active or inactive.
        self._doSetActive = setActive
        self._doSetInactive = setInactive
        self._wasActive = True

    def attach(self, pad, name, klass=PadMonitor, *args):
        """
        Watch for data flow through this pad periodically.
        If data flow ceases for too long, we turn hungry. If data flow resumes,
        we return to happy.
        """

        def monitorActive(name):
            self.info('Pad data flow at %s is active', name)
            if self.isActive() and not self._wasActive:
                # The wasActive check is to prevent _doSetActive from being
                # called happy initially because of this; only if we
                # previously went inactive because of an inactive monitor. A
                # curious interface.
                self._wasActive = True
                self._doSetActive()

        def monitorInactive(name):
            self.info('Pad data flow at %s is inactive', name)
            if self._wasActive:
                self._doSetInactive()
                self._wasActive = False

        assert name not in self
        monitor = klass(pad, name, monitorActive, monitorInactive, *args)
        self[monitor.name] = monitor
        self.info("Added pad monitor %s", monitor.name)

    def remove(self, name):
        if name not in self:
            self.warning("No pad monitor with name %s", name)
            return

        monitor = self.pop(name)
        monitor.detach()

    def isActive(self):
        for monitor in self.values():
            if not monitor.isActive():
                return False
        return True
