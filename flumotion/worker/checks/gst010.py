# -*- Mode: Python -*-
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

import os

import gobject
import gst
import gst.interfaces
from twisted.internet.threads import deferToThread
from twisted.internet import defer

from flumotion.common import gstreamer, errors, log, messages
from flumotion.common.i18n import N_, gettexter
from flumotion.twisted import defer as fdefer
from flumotion.worker.checks import check

__version__ = "$Rev$"
T_ = gettexter()


class BusResolution(fdefer.Resolution):
    pipeline = None
    signal_id = None

    def cleanup(self):
        if self.pipeline:
            if self.signal_id:
                self.pipeline.get_bus().remove_signal_watch()
                self.pipeline.get_bus().disconnect(self.signal_id)
                self.signal_id = None
            self.pipeline.set_state(gst.STATE_NULL)
            self.pipeline = None

def do_element_check(pipeline_str, element_name, check_proc, state=None,
    set_state_deferred=False):
    """
    Parse the given pipeline and set it to the given state.
    When the bin reaches that state, perform the given check function on the
    element with the given name.

    @param pipeline_str: description of the pipeline used to test
    @param element_name: name of the element being checked
    @param check_proc: a function to call with the GstElement as argument.
    @param state: an unused keyword parameter that will be removed when
    support for GStreamer 0.8 is dropped.
    @param set_state_deferred: a flag to say whether the set_state is run in
    a deferToThread
    @type set_state_deferred: bool
    @returns: a deferred that will fire with the result of check_proc, or
              fail.
    @rtype: L{twisted.internet.defer.Deferred}
    """
    def run_check(pipeline, resolution):
        element = pipeline.get_by_name(element_name)
        try:
            retval = check_proc(element)
            resolution.callback(retval)
        except check.CheckProcError, e:
            log.debug('check', 'CheckProcError when running %r: %r',
                      check_proc, e.data)
            resolution.errback(errors.RemoteRunError(e.data))
        except Exception, e:
            log.debug('check', 'Unhandled exception while running %r: %r',
                      check_proc, e)
            resolution.errback(errors.RemoteRunError(
                log.getExceptionMessage(e)))
        # set pipeline state to NULL so worker does not consume
        # unnecessary resources
        pipeline.set_state(gst.STATE_NULL)


    def message_rcvd(bus, message, pipeline, resolution):
        t = message.type
        if t == gst.MESSAGE_STATE_CHANGED:
            if message.src == pipeline:
                old, new, pending = message.parse_state_changed()
                if new == gst.STATE_PLAYING:
                    run_check(pipeline, resolution)
        elif t == gst.MESSAGE_ERROR:
            gerror, debug = message.parse_error()
            # set pipeline state to NULL so worker does not consume
            # unnecessary resources
            pipeline.set_state(gst.STATE_NULL)
            resolution.errback(errors.GStreamerGstError(
                message.src, gerror, debug))
        elif t == gst.MESSAGE_EOS:
            resolution.errback(errors.GStreamerError(
                "Unexpected end of stream"))
        else:
            log.debug('check', 'message: %s: %s:' % (
                message.src.get_path_string(),
                message.type.value_nicks[1]))
            if message.structure:
                log.debug('check', 'message:    %s' %
                    message.structure.to_string())
            else:
                log.debug('check', 'message:    (no structure)')
        return True

    resolution = BusResolution()

    log.debug('check', 'parsing pipeline %s' % pipeline_str)
    try:
        pipeline = gst.parse_launch(pipeline_str)
        log.debug('check', 'parsed pipeline %s' % pipeline_str)
    except gobject.GError, e:
        resolution.errback(errors.GStreamerError(e.message))
        return resolution.d

    bus = pipeline.get_bus()
    bus.add_signal_watch()
    signal_id = bus.connect('message', message_rcvd, pipeline, resolution)

    resolution.signal_id = signal_id
    resolution.pipeline = pipeline
    log.debug('check', 'setting state to playing')
    if set_state_deferred:
        d = deferToThread(pipeline.set_state, gst.STATE_PLAYING)
        def stateChanged(res):
            return resolution.d
        d.addCallback(stateChanged)
        return d
    else:
        pipeline.set_state(gst.STATE_PLAYING)
        return resolution.d

def check1394(mid):
    """
    Probe the firewire device.

    Return a deferred firing a result.

    The result is either:
     - succesful, with a None value: no device found
     - succesful, with a dictionary of width, height, and par as a num/den pair
     - failed

    @param mid: the id to set on the message.

    @rtype: L{twisted.internet.defer.Deferred} of
            L{flumotion.common.messages.Result}
    """
    result = messages.Result()

    def do_check(demux):
        pad = demux.get_pad('video')

        if pad.get_negotiated_caps() == None:
            raise errors.GStreamerError('Pipeline failed to negotiate?')

        caps = pad.get_negotiated_caps()
        s = caps.get_structure(0)
        w = s['width']
        h = s['height']
        par = s['pixel-aspect-ratio']
        result = dict(width=w, height=h, par=(par.num, par.denom))
        log.debug('check', 'returning dict %r' % result)
        return result

    # first check if the obvious device node exists
    if not os.path.exists('/dev/raw1394'):
        m = messages.Error(T_(N_("Device node /dev/raw1394 does not exist.")),
            id=mid)
        result.add(m)
        return defer.succeed(result)

    pipeline = 'dv1394src name=source ! dvdemux name=demux ! fakesink'
    d = do_element_check(pipeline, 'demux', do_check)

    def errbackResult(failure):
        log.debug('check', 'returning failed Result, %r' % failure)
        m = None
        if failure.check(errors.GStreamerGstError):
            source, gerror, debug = failure.value.args
            log.debug('check', 'GStreamer GError: %s (debug: %s)' % (
                gerror.message, debug))
            if gerror.domain == "gst-resource-error-quark":
                if gerror.code == int(gst.RESOURCE_ERROR_NOT_FOUND):
                    # dv1394src was fixed after gst-plugins-good 0.10.2
                    # to distinguish NOT_FOUND and OPEN_READ
                    version = gstreamer.get_plugin_version('1394')
                    if version >= (0, 10, 0, 0) and version <= (0, 10, 2, 0):
                        m = messages.Error(T_(
                            N_("Could not find or open the Firewire device. "
                               "Check the device node and its permissions.")))
                    else:
                        m = messages.Error(T_(
                            N_("No Firewire device found.")))
                elif gerror.code == int(gst.RESOURCE_ERROR_OPEN_READ):
                    m = messages.Error(T_(
                        N_("Could not open Firewire device for reading. "
                           "Check permissions on the device.")))

            if not m:
                m = check.handleGStreamerDeviceError(failure, 'Firewire',
                    mid=mid)

        if not m:
            m = messages.Error(T_(N_("Could not probe Firewire device.")),
                debug=check.debugFailure(failure))

        m.id = mid
        result.add(m)
        return result
    d.addCallback(check.callbackResult, result)
    d.addErrback(errbackResult)

    return d
