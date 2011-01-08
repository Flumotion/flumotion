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
import gst.interfaces
from twisted.internet.threads import deferToThread
from twisted.internet import defer

from flumotion.common import log, messages
from flumotion.common.i18n import N_, gettexter

__version__ = "$Rev: 7678 $"
T_ = gettexter()


def fetchDevices(mid, factories, parameter):
    """
    Fetches the available devices on the system according to the specified
    factories. If the first factory succeeds the other are ignored.

    The result is either:
     - succesful, with a list of tuples with guid and device-name
     - succesful, with an error
     - failed

    @param mid: the id to set on the message.
    @param factories: The gstreamer elements to check
    @type  factories: L{str}
    @param parameter: The parameter that specifies the device
    @type  parameter: str

    @rtype: L{twisted.internet.defer.Deferred} of
            L{flumotion.common.messages.Result}
    """
    result = messages.Result()

    factory = factories.pop()

    element = gst.element_factory_make(factory)

    if not element:
        log.debug("device-check",
                  "Could not instantiate the %s factory.",
                  factory)
        if not factories:
            log.debug("device-check", "No more factories were specified.")
            m = messages.Error(T_(
                N_("GStreamer error, %s factory could not be found.\n"
                   "Maybe the plugin is not properly installed.")), mid=mid)
            result.add(m)

            return defer.succeed(result)
        else:
            return fetchDevices(mid, factories, parameter)

    element.probe_property_name(parameter)
    values = element.probe_get_values_name(parameter)

    pipeline_str = "%s name=source %s" % (factory, parameter)
    pipeline_str += "=%s ! fakesink"

    devices = []

    for value in values:
        pipeline = gst.parse_launch(pipeline_str % value)
        pipeline.set_state(gst.STATE_READY)
        source = pipeline.get_by_name("source")
        name = source.get_property("device-name")
        log.debug("device-check", "New device found: %s with values=%s",
                  name, value)
        devices.append((name, value))
        pipeline.set_state(gst.STATE_NULL)

    if devices:
        result.succeed(devices)
        return defer.succeed(result)
    else:
        log.debug("device-check",
                  "No devices were found using %s factory.",
                  factory)
        if factories:
            return fetchDevices(mid, factories, parameter)
        else:

            m = messages.Error(T_(
                N_("No devices were found for %s."), factory), mid=mid)
            result.add(m)
            return defer.succeed(result)
