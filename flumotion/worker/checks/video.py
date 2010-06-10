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

import gst

from twisted.internet import defer

from flumotion.common import gstreamer, log, messages
from flumotion.worker.checks import check
from flumotion.worker.checks.gst010 import do_element_check

__version__ = "$Rev$"


def checkTVCard(device, mid='check-tvcard'):
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
    d.addErrback(check.errbackNotFoundResult, result, mid, device)
    d.addErrback(check.errbackResult, result, mid, device)

    return d


def checkWebcam(device, mid):
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
    # FIXME: add code that checks permissions and ownership on errors,
    # so that we can offer helpful hints on what to do.

    def probeDevice(element):
        name = element.get_property('device-name')
        caps = element.get_pad("src").get_caps()
        log.debug('check', 'caps: %s' % caps.to_string())

        sizes = {} # (width, height) => [{'framerate': (framerate_num,
                   #                                    framerate_denom),
                   #                      'mime': str,
                   #                      'fourcc': fourcc}]

        def forAllStructValues(struct, key, proc):
            vals = struct[key]
            if isinstance(vals, list):
                for val in vals:
                    proc(struct, val)
            elif isinstance(vals, gst.IntRange):
                val = vals.low
                while val < vals.high:
                    proc(struct, val)
                    val *= 2
                proc(struct, vals.high)
            elif isinstance(vals, gst.DoubleRange):
                # hack :)
                proc(struct, vals.high)
            elif isinstance(vals, gst.FractionRange):
                # hack :)
                val = vals.low
                while float(val) < float(vals.high):
                    proc(struct, val)
                    val.num += 5
                proc(struct, vals.high)
            else:
                # scalar
                proc(struct, vals)

        def addRatesForWidth(struct, width):

            def addRatesForHeight(struct, height):

                def addRate(struct, rate):
                    if not rate.num:
                        return
                    if (width, height) not in sizes:
                        sizes[(width, height)] = []
                    d = {'framerate': (rate.num, rate.denom),
                         'mime': struct.get_name()}
                    if 'yuv' in d['mime']:
                        d['format'] = struct['format'].fourcc
                    sizes[(width, height)].append(d)
                forAllStructValues(struct, 'framerate', addRate)
            forAllStructValues(struct, 'height', addRatesForHeight)
        for struct in caps:
            if 'yuv' not in struct.get_name():
                continue
            forAllStructValues(struct, 'width', addRatesForWidth)

        return (name, element.get_factory().get_name(), sizes)

    def tryV4L2():
        log.debug('webcam', 'trying v4l2')
        version = gstreamer.get_plugin_version('video4linux2')
        minVersion = (0, 10, 5, 1)
        if not version or version < minVersion:
            log.info('webcam', 'v4l2 version %r too old (need >=%r)',
                     version, minVersion)
            return defer.fail(NotImplementedError())

        pipeline = 'v4l2src name=source device=%s ! fakesink' % (device, )
        d = do_element_check(pipeline, 'source', probeDevice,
                             state=gst.STATE_PAUSED, set_state_deferred=True)
        return d

    def tryV4L1(_):
        log.debug('webcam', 'trying v4l1')
        pipeline = 'v4lsrc name=source device=%s ! fakesink' % (device, )
        d = do_element_check(pipeline, 'source', probeDevice,
                             state=gst.STATE_PAUSED, set_state_deferred=True)
        return d

    result = messages.Result()

    d = tryV4L2()
    d.addErrback(tryV4L1)
    d.addCallback(check.callbackResult, result)
    d.addErrback(check.errbackNotFoundResult, result, mid, device)
    d.addErrback(check.errbackResult, result, mid, device)

    return d
