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

import gst

from flumotion.common import errors, log, messages

from flumotion.common.messages import N_
T_ = messages.gettexter('flumotion')
    
def handleGStreamerDeviceError(failure, device):
    """
    Handle common GStreamer GstErrors or other.
    Return a message or None.
    """
    m = None

    if failure.check(errors.GStreamerGstError):
        gerror, debug = failure.value.args
        log.debug('check',
            'GStreamer GError: %s (domain %s, code %d, debug %s)' % (
                gerror.message, gerror.domain, gerror.code, debug))
        
        if gerror.domain == "gst-resource-error-quark":
            if gerror.code == int(gst.RESOURCE_ERROR_OPEN_READ):
                m = messages.Error(T_(
                    N_("Could not open device '%s' for reading.  Check permissions on the device."), device))
            elif gerror.code == int(gst.RESOURCE_ERROR_OPEN_READ_WRITE):
                m = messages.Error(T_(
                    N_("Could not open device '%s'.  Check permissions on the device."), device))
            elif gerror.code == int(gst.RESOURCE_ERROR_BUSY):
                m = messages.Error(T_(
                    N_("Device '%s' is already in use."), device))
            elif gerror.code == int(gst.RESOURCE_ERROR_SETTINGS):
                m = messages.Error(T_(
                    N_("Device '%s' did not accept the requested settings."),
                    device),
                    debug="%s\n%s" % (gerror.message, debug))

        # fallback GStreamer GstError handling
        if not m:
            m = messages.Error(T_(N_("Internal GStreamer error.")),
                debug="%s\n%s: %d\n%s" % (
                    gerror.message, gerror.domain, gerror.code, debug))
    elif failure.check(errors.GStreamerError):
            m = messages.Error(T_(N_("Internal GStreamer error.")),
                debug=debugFailure(failure))
    log.debug('handleGStreamerError: returning %r' % m)
    return m

def debugFailure(failure):
    """
    Create debug info from a failure.
    """
    return "Failure %r: %s\n%s" % (failure, failure.getErrorMessage(),
        failure.getTraceback())

def callbackResult(value, result):
    """
    I am a callback to add to a do_element_check deferred.
    """
    log.debug('check', 'returning succeeded Result, value %r' % (value, ))
    result.succeed(value)
    return result

def errbackResult(failure, result, id, device):
    """
    I am an errback to add to a do_element_check deferred, after your
    specific one.
    """
    m = None
    if failure.check(errors.GStreamerGstError):
        m = handleGStreamerDeviceError(failure, device)

    if not m:
        log.debug('check', 'unhandled failure: %r (%s)\nTraceback:\n%s' % (
            failure, failure.getErrorMessage(), failure.getTraceback()))
        m = messages.Error(T_(N_("Could not probe device '%s'."), device),
            debug=debugFailure(failure))

    m.id = id
    result.add(m)
    return result

def errbackNotFoundResult(failure, result, id, device):
    """
    I am an errback to add to a do_element_check deferred
    to check for RESOURCE_ERROR_NOT_FOUND, and add a message to the result.
    """
    failure.trap(errors.GStreamerGstError)
    gerror, debug = failure.value.args

    if gerror.domain == "gst-resource-error-quark" and \
        gerror.code == int(gst.RESOURCE_ERROR_NOT_FOUND):
        m = messages.Warning(T_(
            N_("No device found on %s."), device), id=id)
        result.add(m)
        return result

    # let failure fall through otherwise
    return failure

class CheckProcError(Exception):
    'Utility error for element checker procedures'
    data = None

    def __init__(self, data):
        self.data = data
