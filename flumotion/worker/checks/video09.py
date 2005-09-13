# -*- Mode: Python -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# Flumotion - a streaming media server
# Copyright (C) 2004,2005 Fluendo, S.L. (www.fluendo.com). All rights reserved.

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

import gobject
import gst
import gst.interfaces

from twisted.internet import defer, reactor

from flumotion.common import gstreamer, errors, log
    
def _(str):
    return str

class Resolution:
    """
    I am a helper class to make sure that the deferred is fired only once
    with either a result or exception.

    @ivar d: the deferred that gets fired as part of the resolution
    @type d: L{twisted.internet.defer.Deferred}
    """
    def __init__(self):
        self.d = defer.Deferred()
        # have to have a returned field here because we can return
        # either from the error signal or from the state changed signal,
        # and we have to make sure we return only once.
        self.returned = False
        self.watch_id = None
        self.pipeline = None

    def cleanup(self):
        if self.watch_id:
            gobject.source_remove(self.watch_id)
            self.watch_id = None
        if self.pipeline:
            self.pipeline.set_state(gst.STATE_NULL)
            self.pipeline = None

    def callback(self, result):
        """
        Make the result succeed, calling the callbacks with the given result.
        If a result was already reached, do nothing.
        """
        if not self.returned:
            self.returned = True
            self.cleanup()
            self.d.callback(result)
    
    def errback(self, exception):
        """
        Make the result fail, calling the errbacks with the given exception.
        If a result was already reached, do nothing.
        """
        if not self.returned:
            self.returned = True
            self.cleanup()
            self.d.errback(exception)
    
class CheckProcError(Exception):
    'Utility error for element checker procedures'
    data = None

    def __init__(self, data):
        self.data = data

def do_element_check(pipeline_str, element_name, check_proc):
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
    def run_check(pipeline, resolution):
        element = pipeline.get_by_name(element_name)
        try:
            retval = check_proc(element)
            resolution.callback(retval)
        except CheckProcError, e:
            resolution.errback(errors.RemoteRunError(e.data))
        except Exception, e:
            resolution.errback(errors.RemoteRunError(e))

    def message_rcvd(bus, message, pipeline, resolution):
        t = message.type
        if t == gst.MESSAGE_STATE_CHANGED:
            if message.src == pipeline:
                old, new = message.parse_state_changed()
                if new == gst.STATE_PLAYING:
                    run_check(pipeline, resolution)
        elif t == gst.MESSAGE_ERROR:
            err, debug = message.parse_error()
            resolution.errback(errors.GstError(err.message, debug))
        elif t == gst.MESSAGE_EOS:
            resolution.errback(errors.GstError("Unexpected end of stream"))
        else:
            print '%s: %s:' % (message.src.get_path_string(),
                               message.type.value_nicks[1])
            if message.structure:
                print '    %s' % message.structure.to_string()
            else:
                print '    (no structure)'
        return True

    resolution = Resolution()

    try:
        pipeline = gst.parse_launch(pipeline_str)
    except gobject.GError, e:
        resolution.errback(errors.GstError(e.message))
        return resolution.d

    bus = pipeline.get_bus()
    watch_id = bus.add_watch(message_rcvd, pipeline, resolution)

    resolution.watch_id = watch_id
    resolution.pipeline = pipeline
    
    # Setting the play-timeout calling watch_for_state_change ensures
    # that we get messages on the bus regardless of the outcome of the
    # set_state. It's the only way to handle all of the cases properly.
    pipeline.set_property('play-timeout', 0L)
    pipeline.set_state(gst.STATE_PLAYING)
    pipeline.watch_for_state_change()

    return resolution.d

def checkTVCard(device):
    """
    Probe the given device node as a TV card.
    Return a deferred firing a human-readable device name, a list of channel
    names (Tuner/Composite/...), and a list of norms (PAL/NTSC/SECAM/...).
    
    @rtype: L{twisted.internet.defer.Deferred}
    """
    def get_name_channels_norms(element):
        deviceName = element.get_property('device-name')
        channels = [channel.label for channel in element.list_channels()]
        norms = [norm.label for norm in element.list_norms()]
        return (deviceName, channels, norms)

    pipeline = 'v4lsrc name=source device=%s ! fakesink' % device
    return do_element_check(pipeline, 'source', get_name_channels_norms)

def checkWebcam(device):
    """
    Probe the given device node as a webcam.
    Return a deferred firing a human-readable device name.
    
    @rtype: L{twisted.internet.defer.Deferred}
    """
    def get_device_name(element):
        return element.get_property('device-name')
                
    autoprobe = "autoprobe=false autoprobe-fps=false"

    pipeline = 'v4lsrc name=source device=%s %s ! fakesink' % (device,
        autoprobe)
    return do_element_check(pipeline, 'source', get_device_name)

def checkMixerTracks(source_factory, device):
    """
    Probe the given GStreamer element factory with the given device for
    mixer tracks.
    Return a deferred firing a human-readable device name and a list of mixer
    track labels.
    
    @rtype: L{twisted.internet.defer.Deferred}
    """
    def get_tracks(element):
        # Only mixers have list_tracks. Why is this a perm error? FIXME in 0.9?
        if not element.implements_interface(gst.interfaces.Mixer):
            msg = 'Cannot get mixer tracks from the device.  '\
                  'Check permissions on the mixer device.'
            log.debug('checks', "returning failure: %s" % msg)
            raise CheckProcError(msg)

        return (element.get_property('device-name'),
                [track.label for track in element.list_tracks()])
                
    pipeline = '%s name=source device=%s ! fakesink' % (source_factory, device)
    return do_element_check(pipeline, 'source', get_tracks)

def check1394():
    """
    Probe the firewire device.

    Return a deferred firing a dictionary with width, height,
    and a pixel aspect ratio pair.
    
    @rtype: L{twisted.internet.defer.Deferred}
    """
    def do_check(demux):
        pad = demux.get_pad('video')

        if pad.get_negotiated_caps() == None:
            raise errors.GstError('Pipeline failed to negotiate?')

        caps = pad.get_negotiated_caps()
        s = caps.get_structure(0)
        w = s['width']
        h = s['height']
        par = s['pixel-aspect-ratio']
        result = dict(width=w, height=h, par=(par.num, par.denom))
        log.debug('returning dict %r' % result)
        return result
        
    # first check if the obvious device node exists
    if not os.path.exists('/dev/raw1394'):
        return defer.fail(errors.DeviceNotFoundError(
            _('device node /dev/raw1394 does not exist')))

    pipeline = 'dv1394src name=source ! dvdemux name=demux ! fakesink'
    return do_element_check(pipeline, 'demux', do_check)
