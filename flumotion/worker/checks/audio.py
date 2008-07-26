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

__version__ = "$Rev$"

import gst

from flumotion.common import messages, log, errors, gstreamer
from flumotion.common.i18n import N_, gettexter
from flumotion.worker.checks import check

from gst010 import do_element_check

T_ = gettexter()

def checkMixerTracks(source_factory, device, channels, mid=None):
    """
    Probe the given GStreamer element factory with the given device for
    audio mixer tracks.
    Return a deferred firing a result.

    The result is either:
     - succesful, with a None value: no device found
     - succesful, with a human-readable device name and a list of mixer
       track labels.
     - failed

    @rtype: L{twisted.internet.defer.Deferred}
    """
    result = messages.Result()

    def get_tracks(element):
        # Only mixers have list_tracks. Why is this a perm error? FIXME in 0.9?
        if not element.implements_interface(gst.interfaces.Mixer):
            msg = 'Cannot get mixer tracks from the device.  '\
                  'Check permissions on the mixer device.'
            log.debug('checks', "returning failure: %s" % msg)
            raise check.CheckProcError(msg)
        return (element.get_property('device-name'),
                [track.label for track in element.list_tracks()])

    pipeline = ('%s name=source device=%s ! '
                'audio/x-raw-int,channels=%d ! fakesink') % (
        source_factory, device, channels)
    d = do_element_check(pipeline, 'source', get_tracks,
        set_state_deferred=True)

    def errbackAlsaBugResult(failure, result, mid, device):
        # alsasrc in gst-plugins-base <= 0.10.14 was accidentally reporting
        # GST_RESOURCE_ERROR_WRITE when it could not be opened for reading.
        if not failure.check(errors.GStreamerGstError):
            return failure
        if source_factory != 'alsasrc':
            return failure
        version = gstreamer.get_plugin_version('alsasrc')
        if version > (0, 10, 14):
            return failure

        source, gerror, debug = failure.value.args
        log.debug('check',
            'GStreamer GError: %s (domain %s, code %d, debug %s)' % (
                gerror.message, gerror.domain, gerror.code, debug))

        if gerror.domain == "gst-resource-error-quark":
            if gerror.code == int(gst.RESOURCE_ERROR_OPEN_WRITE):
                m = messages.Error(T_(
                    N_("Could not open device '%s' for reading.  "
                       "Check permissions on the device."), device))
                result.add(m)
                return result

        return failure
        

    d.addCallback(check.callbackResult, result)
    d.addErrback(check.errbackNotFoundResult, result, mid, device)
    d.addErrback(errbackAlsaBugResult, result, mid, device)
    d.addErrback(check.errbackResult, result, mid, device)

    return d
