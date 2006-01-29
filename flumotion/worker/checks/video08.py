# -*- Mode: Python -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# Flumotion - a streaming media server
# Copyright (C) 2004,2005,2006 Fluendo, S.L. (www.fluendo.com).
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


import re
import os

import gst
import gst.interfaces

from twisted.internet import reactor, defer

from flumotion.common import gstreamer, errors, log, messages
from flumotion.twisted import defer as fdefer

from flumotion.common.messages import N_
T_ = messages.gettexter('flumotion')
    
def do_element_check(pipeline_str, element_name, check_proc,
                     state=gst.STATE_READY):
    """
    Parse the given pipeline and set it to the given state.
    When the bin reaches that state, perform the given check function on the
    element with the given name.
    Return a deferred that will fire the result of the given check function,
    or a failure. 
    
    @param pipeline_str: description of the pipeline used to test
    @param element_name: name of the element being checked
    @param check_proc: a function to call with the GstElement as argument.

    @returns: a deferred that will fire with the result of check_proc, or
              fail.
    @rtype: L{twisted.internet.defer.Deferred}
    """
    assert state > gst.STATE_NULL
    
    def state_changed_cb(pipeline, old, new, resolution):
        # only perform check if we arrived at the requested state by going up
        if not (old == state>>1 and new == state):
            return
            
        element = pipeline.get_by_name(element_name)
        try:
            retval = check_proc(element)

            # If check_proc returns a Deferred, it is responsible for eventually
            # setting the bin state to NULL.
            if isinstance(retval, defer.Deferred):
                retval.addCallback(
                    lambda result: resolution.callback(result))
            else:
                reactor.callLater(0, pipeline.set_state, gst.STATE_NULL)
                resolution.callback(retval)

        except CheckProcError, e:
            resolution.errback(errors.RemoteRunError(e.data))
        except Exception, e:
            resolution.errback(errors.RemoteRunError(e))

    # if any error happens during the pipeline run, error out
    def error_cb(pipeline, element, gerror, debug, resolution):
        # refcounting bug in gst-python 0.8 makes gerror be invalid after
        # leaving the cb. so, create a fake GError.  What a spectular hack.
        class FakeGstGError: pass
        e = FakeGstGError()
        e.message = gerror.message
        e.code = gerror.code
        e.domain = gerror.domain
        resolution.errback(errors.GStreamerGstError(e, debug))

    bin = gst.parse_launch(pipeline_str)
    resolution = fdefer.Resolution()
    bin.connect('state-change', state_changed_cb, resolution)
    bin.connect('error', error_cb, resolution)
    bin.set_state(state)

    return resolution.d

def check1394(id=None):
    """
    Probe the firewire device.

    Return a deferred firing a result.

    The result is either:
     - succesful, with a None value: no device found
     - succesful, with a dictionary of width, height, and par as a num/den pair
     - failed
    
    @rtype: L{twisted.internet.defer.Deferred} of 
            L{flumotion.common.messages.Result}
    """
    result = messages.Result()
 
    def iterate(bin, resolution):
        pad = bin.get_by_name('dec').get_pad('video')

        if not bin.iterate():
            raise errors.GStreamerError('Failed to iterate bin')
        elif pad.get_negotiated_caps() == None:
            reactor.callLater(0, iterate, bin, resolution)
            return

        # we have caps now, examine them
        caps = pad.get_negotiated_caps()
        s = caps.get_structure(0)
        w = s.get_int('width')
        h = s.get_int('height')

        # FIXME: in the future we should check gst-python version and use
        # the pixel-aspect-ratio fraction tuple when it gets wrapped.
        # For now we do fairly safe string matching.
        matcher = re.compile(".*pixel-aspect-ratio=\(fraction\)(\d+)/(\d+).*")
        match = matcher.search(s.to_string())
        nom, den = 1, 1
        if match:
            nom, den = [int(s) for s in match.groups()]
        else:
            log.warning('Could not get pixel aspect ratio from device')
        log.debug('Using pixel aspect ratio of %d/%d' % (nom, den))

        reactor.callLater(0, bin.set_state, gst.STATE_NULL)
        result = dict(width=w, height=h, par=(nom, den))
        log.debug('returning dict %r' % result)
        resolution.callback(result)
        
    def do_check(element):
        bin = element.get_parent()
        resolution = fdefer.Resolution()
        reactor.callLater(0, iterate, bin, resolution)
        return resolution.d

    # first check if the obvious device node exists
    if not os.path.exists('/dev/raw1394'):
        m = messages.Error(T_(N_("Device node /dev/raw1394 does not exist.")),
            id=id)
        result.add(m)
        return defer.succeed(result)

    pipeline = 'dv1394src name=source ! dvdec name=dec ! fakesink'
    d = do_element_check(pipeline, 'source', do_check,
                            state=gst.STATE_PLAYING)

    def errbackResult(failure):
        log.debug('check', 'returning failed Result, %r' % failure)
        m = None
        if failure.check(errors.GStreamerGstError):
            gerror, debug = failure.value.args
            log.debug('check', 'GStreamer GError: %s (debug: %s)' % (
                gerror.message, debug))
            if gerror.domain == "gst-resource-error-quark":
                if gerror.code == int(gst.RESOURCE_ERROR_NOT_FOUND):
                    m = messages.Error(T_(
                        N_("No Firewire device found.")))

            if not m:
                m = check.handleGStreamerDeviceError(failure, 'Firewire')

        if not m:
            m = messages.Error(T_(N_("Could not probe Firewire device.")),
                debug=check.debugFailure(failure))

        m.id = id
        result.add(m)
        return result
    d.addCallback(check.callbackResult, result)
    d.addErrback(errbackResult)

    return d

def check_ffmpegcolorspace_AYUV(id=None):
    """
    Check if the ffmpegcolorspace element converts AYUV.
    This was added in gst-plugins 0.8.5
    """
    result = messages.Result()

    e = gst.element_factory_make('ffmpegcolorspace')
    s = e.get_pad_template('sink').get_caps().to_string()
    if s.find('AYUV') > -1:
        result.succeed(True)
    else:
        msg = messages.Error(T_(N_(
            'The ffmpegcolorspace element is too old. '
            'Please upgrade gst-plugins to version 0.8.5.')), id=id)
        result.add(msg)
        
    return defer.succeed(result)
