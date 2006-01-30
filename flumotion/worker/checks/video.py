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

from flumotion.worker.checks import check

import gst

if gst.gst_version[1] == 8:
    from video08 import *
else:
    from video010 import *

def checkTVCard(device, id='check-tvcard'):
    """
    Probe the given device node as a TV card.
    Return a deferred firing a human-readable device name, a list of channel
    names (Tuner/Composite/...), and a list of norms (PAL/NTSC/SECAM/...).
    
    @rtype: L{twisted.internet.defer.Deferred}
    """
    result = messages.Result()

    def get_name_channels_norms(element):
        deviceName = element.get_property('device-name')
        channels = [channel.label for channel in element.list_channels()]
        norms = [norm.label for norm in element.list_norms()]
        return (deviceName, channels, norms)

    pipeline = 'v4lsrc name=source device=%s ! fakesink' % device
    d = do_element_check(pipeline, 'source', get_name_channels_norms)

    d.addCallback(check.callbackResult, result)
    d.addErrback(check.errbackNotFoundResult, result, id, device)
    d.addErrback(check.errbackResult, result, id, device)

    return d

def checkWebcam(device, id):
    """
    Probe the given device node as a webcam.

    The result is either:
     - succesful, with a None value: no device found
     - succesful, with a tuple:
                  - device name
                  - dict of mime, format, width, height, fps pair
     - failed
    
    @rtype: L{flumotion.common.messages.Result}
    """
    result = messages.Result()

    # FIXME: add code that checks permissions and ownership on errors,
    # so that we can offer helpful hints on what to do.
    def get_device_name(element):
        name = element.get_property('device-name')
        caps = element.get_pad("src").get_negotiated_caps()
        log.debug('check', 'negotiated caps: %s' % caps.to_string())
        s = caps[0]
        # before 0.10 framerate was a double
        if gst.gst_version[0] == 0 and gst.gst_version[1] < 9:
            num = int(s['framerate'] * 16)
            denom = 16
        else:
            num = s['framerate'].num
            denom = s['framerate'].denom

        d = {
            'mime': s.get_name(),
            'width': s['width'],
            'height': s['height'],
            'framerate': (num, denom),
        }
        # FIXME: do something about rgb
        if s.get_name() == 'video/x-raw-yuv':
            d['format'] = s['format'].fourcc
        return (name, d)
                
    # FIXME: taken from the 0.8 check
    # autoprobe = "autoprobe=false"
    # added in gst-plugins 0.8.6
    # if gstreamer.element_factory_has_property('v4lsrc', 'autoprobe-fps'):
    #    autoprobe += " autoprobe-fps=false"

    autoprobe = "autoprobe-fps=false"
    # FIXME: with autoprobe-fps turned off, pwc's don't work anymore
    autoprobe = ""

    pipeline = 'v4lsrc name=source device=%s %s ! fakesink' % (device,
        autoprobe)
    d = do_element_check(pipeline, 'source', get_device_name, state=gst.STATE_PAUSED)

    d.addCallback(check.callbackResult, result)
    d.addErrback(check.errbackNotFoundResult, result, id, device)
    d.addErrback(check.errbackResult, result, id, device)

    return d


# FIXME: move to audio ?
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
                
    pipeline = '%s name=source device=%s ! audio/x-raw-int,channels=%d ! fakesink' % (source_factory, device, channels)
    d = do_element_check(pipeline, 'source', get_tracks)

    d.addCallback(check.callbackResult, result)
    d.addErrback(check.errbackNotFoundResult, result, id, device)
    d.addErrback(check.errbackResult, result, id, device)

    return d


