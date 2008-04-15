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

from flumotion.worker.checks import check
from flumotion.common import messages, log

import gst

from gst010 import do_element_check

__version__ = "$Rev$"


def checkMixerTracks(source_factory, device, channels, id=None):
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
        set_state_deferred = True)

    d.addCallback(check.callbackResult, result)
    d.addErrback(check.errbackNotFoundResult, result, id, device)
    d.addErrback(check.errbackResult, result, id, device)

    return d
