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


import gst
import gst.interfaces

from twisted.internet import defer, reactor

from flumotion.common import gstreamer, errors
    

class Result:
    def __init__(self):
        self.d = defer.Deferred()
        # have to have a returned field here because we can return
        # either from the error signal or from the state changed signal,
        # and we have to make sure we return only once.
        self.returned = False

    def callback(self, result):
        if not self.returned:
            self.returned = True
            self.d.callback(result)
    
    def errback(self, result):
        if not self.returned:
            self.returned = True
            self.d.errback(result)

    
class CheckProcError(Exception):
    'Utility error for element checker procedures'
    data = None

    def __init__(self, data):
        self.data = data


def make_element_checker(pipeline_str, element_name, check_proc):
    def state_changed_cb(pipeline, old, new, res):
        if not (old == gst.STATE_NULL and new == gst.STATE_READY):
            return
        element = pipeline.get_by_name(element_name)
        reactor.callLater(0, pipeline.set_state, gst.STATE_NULL)
        try:
            res.callback(check_proc(element))
        except CheckProcError, e:
            res.errback(e.data)

    def error_cb(pipeline, element, error, _, res):
        res.errback(errors.GstError(error.message))

    def element_checker(*args):
        bin = gst.parse_launch(pipeline_str)
        result = Result()
        bin.connect('state-change', state_changed_cb, result)
        bin.connect('error', error_cb, result)
        bin.set_state(gst.STATE_PLAYING)

        return result.d

    return element_checker

                    
def checkChannels(device):
    def get_channels_norms(element):
        deviceName = element.get_property('device-name')
        channels = [channel.label for channel in element.list_channels()]
        norms = [norm.label for norm in element.list_norms()]
        return (deviceName, channels, norms)

    pipeline = 'v4lsrc name=source device=%s ! fakesink' % device

    # make a checker and call it
    return make_element_checker(pipeline, 'source', get_channels_norms)()


# FIXME: rename, only for v4l stuff
def checkDeviceName(device):
    def get_device_name(element):
        return element.get_property('device-name')
                
    autoprobe = "autoprobe=false"
    # added in gst-plugins 0.8.6
    if gstreamer.element_factory_has_property('v4lsrc', 'autoprobe-fps'):
        autoprobe += " autoprobe-fps=false"

    pipeline = 'v4lsrc name=source device=%s %s ! fakesink' % (device,
        autoprobe)

    return make_element_checker(pipeline, 'source', get_device_name)()


def checkTracks(source_element, device):
    def get_tracks(element):
        # Only mixers have list_tracks. Why is this a perm error? FIXME in 0.9?
        if not element.implements_interface(gst.interfaces.Mixer):
            raise CheckProcError('Cannot get mixer tracks from the device.  '\
                                 'Check permissions on the mixer device.')

        try:
            return (element.get_property('device-name'),
                    [track.label for track in element.list_tracks()])
        except AttributeError:
            # list_tracks was added in gst-python 0.7.94
            v = gst.pygst_version
            msg = 'Your version of gstreamer-python is %d.%d.%d. ' % v\
                  + 'Please upgrade gstreamer-python to 0.7.94 or higher.'
            raise CheckProcError(msg)
                
    def error_cb(pipeline, element, error, _, res):
        if not res.returned:
            res.returned = True
            res.d.errback(errors.GstError(error.message))

    pipeline = '%s name=source device=%s ! fakesink' % (source_element, device)

    return make_element_checker(pipeline, 'source', get_tracks)()


def check1394():
    def do_check(element):
        # if we made it into ready, we're golden
        return True

    pipeline = 'dv1394src name=source ! dvdec ! fakesink'
    return make_element_checker(pipeline, 'source', do_check)()
