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


import os

import gst
import gst.interfaces

from twisted.internet import defer, reactor

from flumotion.common import gstreamer, errors, log
    
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

    def callback(self, result):
        """
        Make the result succeed, calling the callbacks with the given result.
        If a result was already reached, do nothing."
        """
        if not self.returned:
            self.returned = True
            self.d.callback(result)
    
    def errback(self, exception):
        """
        Make the result fail, calling the errbacks with the given exception.
        If a result was already reached, do nothing."
        """
        if not self.returned:
            self.returned = True
            self.d.errback(exception)
    
class CheckProcError(Exception):
    'Utility error for element checker procedures'
    data = None

    def __init__(self, data):
        self.data = data

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
    def error_cb(pipeline, element, error, _, resolution):
        resolution.errback(errors.GstError(error.message))

    bin = gst.parse_launch(pipeline_str)
    resolution = Resolution()
    bin.connect('state-change', state_changed_cb, resolution)
    bin.connect('error', error_cb, resolution)
    bin.set_state(state)

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
                
    autoprobe = "autoprobe=false"
    # added in gst-plugins 0.8.6
    if gstreamer.element_factory_has_property('v4lsrc', 'autoprobe-fps'):
        autoprobe += " autoprobe-fps=false"

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

        try:
            return (element.get_property('device-name'),
                    [track.label for track in element.list_tracks()])
        except AttributeError:
            # list_tracks was added in gst-python 0.7.94
            v = gst.pygst_version
            msg = 'Your version of gstreamer-python is %d.%d.%d. ' % v\
                  + 'Please upgrade gstreamer-python to 0.7.94 or higher.'
            log.debug('checks', "returning failure: %s" % msg)
            raise CheckProcError(msg)
                
    pipeline = '%s name=source device=%s ! fakesink' % (source_factory, device)
    return do_element_check(pipeline, 'source', get_tracks)

def check1394():
    """
    Probe the firewire device.

    Return a deferred firing a dictionary with width, height,
    and a pixel aspect ratio pair.
    
    @rtype: L{twisted.internet.defer.Deferred}
    """
    def iterate(bin, resolution):
        pad = bin.get_by_name('dec').get_pad('video')

        if not bin.iterate():
            resolution.errback('Failed to iterate bin')
            return
        elif pad.get_negotiated_caps() == None:
            reactor.callLater(0, iterate, bin, resolution)
            return

        caps = pad.get_negotiated_caps()
        s = caps.get_structure(0)
        w = s.get_int('width')
        h = s.get_int('height')
        # from the height we can know the aspect ratio, because PAL has
        # one height and NTSC the other. but, we don't know if it's wide
        # or not, because we haven't wrapped gststructure properly. yet.
        # so, assume it's 4/3.
        p = h==576 and (59,54) or (10,11)
        reactor.callLater(0, bin.set_state, gst.STATE_NULL)
        resolution.callback(dict(width=w, height=h, par=p))
        
    def do_check(element):
        bin = element.get_parent()
        resolution = Resolution()
        reactor.callLater(0, iterate, bin, resolution)
        return resolution.d

    # first check if the obvious device node exists
    if not os.path.exists('/dev/raw1394'):
        return defer.fail(errors.DeviceNotFoundError(
            'device node /dev/raw1394 does not exist'))

    pipeline = 'dv1394src name=source ! dvdec name=dec ! fakesink'
    return do_element_check(pipeline, 'source', do_check,
                            state=gst.STATE_PLAYING)
