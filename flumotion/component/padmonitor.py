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

import time

from twisted.internet import reactor

from flumotion.common import log


class PadMonitor(log.Loggable):
    PAD_MONITOR_PROBE_FREQUENCY = 5.0
    PAD_MONITOR_TIMEOUT = PAD_MONITOR_PROBE_FREQUENCY * 2.5

    def __init__(self, pad, name, setActive, setInactive):
        self._last_data_time = -1
        self._pad = pad
        self.name = name
        self._active = False
        self._first = True

        self._doSetActive = setActive
        self._doSetInactive = setInactive

        # This dict sillyness is because python's dict operations are atomic
        # w.r.t. the GIL.
        self._probe_id = {}
        self._add_probe_dc = None

        self._add_flow_probe()

        self._check_flow_dc = reactor.callLater(self.PAD_MONITOR_TIMEOUT,
            self._check_flow_timeout)

    def isActive(self):
        return self._active

    def detach(self):
        probe_id = self._probe_id.pop("id", None)
        if probe_id:
            self._pad.remove_buffer_probe(probe_id)

        if self._add_probe_dc:
            self._add_probe_dc.cancel()
            self._add_probe_dc = None

        if self._check_flow_dc:
            self._check_flow_dc.cancel()
            self._check_flow_dc = None

    def logMessage(self, message, *args):
        if self._first:
            self.debug(message, *args)
        else:
            self.log(message, *args)
        
    def _add_flow_probe(self):
        self._probe_id['id'] = self._pad.add_buffer_probe(
            self._flow_watch_probe_cb)
        self._add_probe_dc = None

    def _add_flow_probe_later(self):
        self._add_probe_dc = reactor.callLater(self.PAD_MONITOR_PROBE_FREQUENCY,
            self._add_flow_probe)

    def _flow_watch_probe_cb(self, pad, buffer):
        """
        Periodically scheduled buffer probe, that ensures that we're currently
        actually having dataflow through our eater elements.

        Called from GStreamer threads.

        @param pad:       The gst.Pad srcpad for one eater in this component.
        @param buffer:    A gst.Buffer that has arrived on this pad
        """

        self._last_data_time = time.time()

        self.logMessage('buffer probe on %s has timestamp %s', self.name,
             gst.TIME_ARGS(buffer.timestamp))

        id = self._probe_id.pop("id", None)
        if id:
            # This will be None only if detach() has been called.
            self._pad.remove_buffer_probe(id)

            reactor.callFromThread(self._add_flow_probe_later)

            # Data received! Return to happy ASAP:
            reactor.callFromThread(self._check_flow_timeout_now)

        self._first = False

        return True

    def _check_flow_timeout_now(self):
        if self._check_flow_dc:
            self._check_flow_dc.cancel()
        self._check_flow_timeout()
        
    def _check_flow_timeout(self):
        self._check_flow_dc = None

        self.log('last buffer for %s at %r', self.name, self._last_data_time)

        now = time.time()

        if self._last_data_time < 0:
            # We never received any data in the first timeout period... 
            self._last_data_time = 0
            self.setInactive()

        if self._last_data_time > 0:
            delta = now - self._last_data_time

            if self._active and delta > self.PAD_MONITOR_TIMEOUT:
                self.info("No data received on pad %s for > %r seconds, setting "
                    "to hungry", self.name, self.PAD_MONITOR_TIMEOUT)
                self.setInactive()
            elif not self._active and delta < self.PAD_MONITOR_TIMEOUT:
                self.info("Receiving data again on pad %s, flow active", 
                    self.name)
                self.setActive()

        self._check_flow_dc = reactor.callLater(self.PAD_MONITOR_TIMEOUT,
            self._check_flow_timeout)

    def setInactive(self):
        self._doSetInactive(self.name)
        self._active = False

    def setActive(self):
        self._doSetActive(self.name)
        self._active = True

class EaterPadMonitor(PadMonitor):
    def __init__(self, pad, name, setActive, setInactive,
                 reconnectEater, *args):
        PadMonitor.__init__(self, pad, name, setActive, setInactive)

        self._doReconnectEater = lambda: reconnectEater(*args)
        self._reconnectDC = None

    def setInactive(self):
        PadMonitor.setInactive(self)

        # If an eater received a buffer before being marked as disconnected,
        # and still within the buffer check interval, the next eaterCheck
        # call could accidentally think the eater was reconnected properly.
        # Setting this to 0 here avoids that happening in eaterCheck.
        self._last_data_time = 0

        self._doReconnectEater()
        def reconnect():
            self._reconnectDC = None
            self._doReconnectEater()

        self._reconnectDC = reactor.callLater(self.PAD_MONITOR_TIMEOUT,
            reconnect)

    def setActive(self):
        PadMonitor.setActive(self)

        if self._reconnectDC:
            self._reconnectDC.cancel()
            self._reconnectDC = None

    def detach(self):
        PadMonitor.detach(self)

        if self._reconnectDC:
            self._reconnectDC.cancel()
            self._reconnectDC = None

class PadMonitorSet(dict, log.Loggable):
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

