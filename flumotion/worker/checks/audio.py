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
import dbus

from flumotion.common import messages, log, errors, gstreamer
from flumotion.common.i18n import N_, gettexter
from flumotion.worker.checks import check
from twisted.internet import defer

from gst010 import do_element_check

T_ = gettexter()


def getAudioDevices(source_factory, mid=None):
    """
    Search the available devices in worker for the specified factory.
    Return a deferred firing a result.

    The result is either:
     - succesful, with an empty list: no device found
     - succesful, with the list of found devices
     - failed

    @rtype: L{twisted.internet.defer.Deferred}
    """
    result = messages.Result()
    devices = []

    def getOssDevices():
        bus = dbus.SystemBus()
        hal = dbus.Interface(bus.get_object('org.freedesktop.Hal',
                                            '/org/freedesktop/Hal/Manager'),
                             'org.freedesktop.Hal.Manager')
        udis = hal.FindDeviceStringMatch('oss.type', 'pcm')

        for udi in udis:
            dev = dbus.Interface(bus.get_object('org.freedesktop.Hal', udi),
                                 'org.freedesktop.Hal.Device')
            if not dev.PropertyExists('oss.device'):
                continue
            if dev.GetProperty('oss.device') != 0:
                continue

            devices.append((str(dev.GetProperty('info.product')),
                            str(dev.GetProperty('oss.device_file'))))

    def getAlsaDevices():
        source = gst.element_factory_make('alsasrc')
        pipeline = 'alsasrc name=source device=%s ! fakesink'

        for device in source.probe_get_values_name('device'):
            p = gst.parse_launch(pipeline % device)
            p.set_state(gst.STATE_READY)
            s = p.get_by_name('source')
            devices.append((s.get_property('device-name'),
                            device.split(',')[0]))
            p.set_state(gst.STATE_NULL)

    try:
        {'alsasrc': getAlsaDevices,
         'osssrc': getOssDevices}[source_factory]()

    except dbus.DBusException, e:
        devices = [("/dev/dsp", "/dev/dsp"),
                   ("/dev/dsp1", "/dev/dsp1"),
                   ("/dev/dsp2", "/dev/dsp2")]

        result.succeed(devices)

        failure = defer.failure.Failure()
        m = messages.Warning(T_(
             N_("There has been an error while fetching the OSS audio devices "
                "through Hal.\nThe listed devices have been guessed and may "
                "not work properly.")), debug=check.debugFailure(failure))
        m.id = mid
        result.add(m)
        return defer.succeed(result)
    except:
        failure = defer.failure.Failure()
        log.debug('check', 'unhandled failure: %r (%s)\nTraceback:\n%s' % (
                  failure, failure.getErrorMessage(), failure.getTraceback()))
        m = messages.Error(T_(N_("Could not probe devices.")),
                           debug=check.debugFailure(failure))

        m.id = mid
        result.add(m)
        return defer.fail(result)
    else:
        result.succeed(devices)
        if not devices:
            m = messages.Error(T_(
                    N_("Could not find any device in the system.\n"
                       "Please check whether the device is correctly plugged "
                       "in and whether the modules are correctly loaded."),
                    sound_system))

            m.id = mid
            result.add(m)

        return defer.succeed(result)


def checkMixerTracks(source_factory, device, mid=None):
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
            msg = 'Cannot get mixer tracks from the device. '\
                  'Check permissions on the mixer device.'
            log.debug('checks', "returning failure: %s" % msg)
            raise check.CheckProcError(msg)

        devName = element.get_property('device-name')
        tracks = [track.label for track in element.list_tracks()]
        structs = []
        for structure in element.get_pad('src').get_caps():
            structDict = dict(structure)
            for key, value in structDict.items()[:]:
                # Filter items which are not serializable over pb
                if isinstance(value, gst.IntRange):
                    structDict[key] = (value.high, value.low)
            structs.append(structDict)
        return (devName, tracks, structs)

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

    pipeline = ('%s name=source device=%s ! fakesink') % (
                source_factory, device)
    d = do_element_check(pipeline, 'source', get_tracks,
                         set_state_deferred=True)

    pipeline = ('%s name=source device=%s ! fakesink') % (
                source_factory, device)
    d = do_element_check(pipeline, 'source', get_tracks,
                         set_state_deferred=True)

    d.addCallback(check.callbackResult, result)
    d.addErrback(check.errbackNotFoundResult, result, mid, device)
    d.addErrback(errbackAlsaBugResult, result, mid, device)
    d.addErrback(check.errbackResult, result, mid, device)

    return d
