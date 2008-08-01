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

import os

import gst
from twisted.internet import defer

from flumotion.common import errors, log, messages, gstreamer
from flumotion.common.i18n import N_, gettexter

__version__ = "$Rev$"
T_ = gettexter()


def handleGStreamerDeviceError(failure, device, mid=None):
    """
    Handle common GStreamer GstErrors or other.
    Return a message or None.
    """
    if not mid:
        log.warning('check',
            'handleGStreamerDeviceError: no message id specified')

    m = None

    if failure.check(errors.GStreamerGstError):
        source, gerror, debug = failure.value.args
        log.debug('check',
            'GStreamer GError: %s (domain %s, code %d, debug %s)' % (
                gerror.message, gerror.domain, gerror.code, debug))

        if gerror.domain == "gst-resource-error-quark":
            if gerror.code == int(gst.RESOURCE_ERROR_OPEN_READ):
                m = messages.Error(T_(
                    N_("Could not open device '%s' for reading.  "
                       "Check permissions on the device."), device), mid=mid)
            if gerror.code == int(gst.RESOURCE_ERROR_OPEN_WRITE):
                m = messages.Error(T_(
                    N_("Could not open device '%s' for writing.  "
                       "Check permissions on the device."), device), mid=mid)
            elif gerror.code == int(gst.RESOURCE_ERROR_OPEN_READ_WRITE):
                m = messages.Error(T_(
                    N_("Could not open device '%s'.  "
                       "Check permissions on the device."), device), mid=mid)
            elif gerror.code == int(gst.RESOURCE_ERROR_BUSY):
                m = messages.Error(T_(
                    N_("Device '%s' is already in use."), device), mid=mid)
            elif gerror.code == int(gst.RESOURCE_ERROR_SETTINGS):
                m = messages.Error(T_(
                    N_("Device '%s' did not accept the requested settings."),
                    device),
                    debug="%s\n%s" % (gerror.message, debug), mid=mid)

        # fallback GStreamer GstError handling
        if not m:
            m = messages.Error(T_(N_("Internal unhandled GStreamer error.")),
                debug="%s\n%s: %d\n%s" % (
                    gerror.message, gerror.domain, gerror.code, debug),
                               mid=mid)
    elif failure.check(errors.GStreamerError):
        m = messages.Error(T_(N_("Internal GStreamer error.")),
            debug=debugFailure(failure), mid=mid)
    log.debug('check', 'handleGStreamerError: returning %r' % m)
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


def errbackResult(failure, result, mid, device):
    """
    I am an errback to add to a do_element_check deferred, after your
    specific one.

    I handle several generic cases, including some generic GStreamer errors.

    @param mid: the id to set on the message
    """
    m = None
    if failure.check(errors.GStreamerGstError):
        m = handleGStreamerDeviceError(failure, device, mid=mid)

    if not m:
        log.debug('check', 'unhandled failure: %r (%s)\nTraceback:\n%s' % (
            failure, failure.getErrorMessage(), failure.getTraceback()))
        m = messages.Error(T_(N_("Could not probe device '%s'."), device),
            debug=debugFailure(failure))

    m.id = mid
    result.add(m)
    return result


def errbackNotFoundResult(failure, result, mid, device):
    """
    I am an errback to add to a do_element_check deferred
    to check for RESOURCE_ERROR_NOT_FOUND, and add a message to the result.

    @param mid: the id to set on the message
    """
    failure.trap(errors.GStreamerGstError)
    source, gerror, debug = failure.value.args

    if gerror.domain == "gst-resource-error-quark" and \
        gerror.code == int(gst.RESOURCE_ERROR_NOT_FOUND):
        m = messages.Warning(T_(
            N_("No device found on %s."), device), mid=mid)
        result.add(m)
        return result

    # let failure fall through otherwise
    return failure


class CheckProcError(Exception):
    'Utility error for element checker procedures'
    data = None

    def __init__(self, data):
        self.data = data


def checkImport(moduleName):
    log.debug('check', 'checkImport: %s', moduleName)
    __import__(moduleName)


def checkElements(elementNames):
    log.debug('check', 'checkElements: element names to check %r',
               elementNames)
    ret = []
    for name in elementNames:
        try:
            gst.element_factory_make(name)
            ret.append(name)
        except gst.PluginNotFoundError:
            log.debug('check', 'no plugin found for element factory %s', name)
            pass
    log.debug('check', 'checkElements: returning elements names %r', ret)
    return ret


def checkDirectory(pathName):
    """
    Check if a path is a directory and that it is readable and
    executable
    @param pathName: path to check
    @type pathName: string
    @returns: if the path is a directory and readable
    @rtype: L{messages.Result}
    """

    result = messages.Result()
    succeeded = False
    if (os.path.isdir(pathName) and
        os.access(pathName, os.R_OK|os.X_OK)):
        succeeded = True

    result.succeed(succeeded)
    return result


def checkPlugin(pluginName, packageName, minimumVersion=None,
                featureName=None, featureCheck=None):
    """
    Check if the given plug-in is available.
    Return a result with an error if it is not, or not new enough.

    @param pluginName: name of the plugin to check
    @param packageName: name of the package to tell the user to install
    if the check fails
    @param minimumVersion: minimum version of the plugin, as a tuple.
    Optional.
    @param featureName: name of a specific feature to check for in the
    plugin. Optional. Overrides the minimum version check, if given.
    @param featureCheck: function to call on the found feature, which
    should return a boolean representing whether the feature is good or
    not. Optional, and only makes sense if you specify featureName.
    @rtype: L{messages.Result}
    """
    result = messages.Result()
    version = gstreamer.get_plugin_version(pluginName)

    if not version:
        m = messages.Error(T_(
            N_("This host is missing the '%s' GStreamer plug-in.\n"),
                pluginName))
        m.add(T_(N_(
            "Please install '%s'.\n"), packageName))
        result.add(m)
    elif featureName:
        r = gst.registry_get_default()
        features = r.get_feature_list_by_plugin(pluginName)
        byname = dict([(f.get_name(), f) for f in features])
        if (featureName not in byname
            or (featureCheck and not featureCheck(byname[featureName]))):
            m = messages.Error(T_(
                N_("Your '%s' GStreamer plug-in is too old.\n"), pluginName),
                id = 'plugin-%s-check' % pluginName)
            m.add(T_(N_(
                "Please upgrade '%s' to version %s or higher."),
                packageName, ".".join([str(x) for x in minimumVersion])))
            result.add(m)
    elif version < minimumVersion:
        m = messages.Error(T_(
            N_("Version %s of the '%s' GStreamer plug-in is too old.\n"),
               ".".join([str(x) for x in version]), pluginName),
            id = 'plugin-%s-check' % pluginName)
        m.add(T_(N_(
            "Please upgrade '%s' to version %s."), packageName,
               ".".join([str(x) for x in minimumVersion])))
        result.add(m)

    result.succeed(None)
    return defer.succeed(result)

# FIXME: I would prefer to have this in flumotion/component/base/check.py


def do_check(obj, callable, *args, **kwargs):
    """
    This method can be used in component do_check vmethods.
    It will add messages from the result to the UI state.

    @param obj:      an object having a addMessage method
    @param callable: a callable which returns a deferred method
                     returning a Result.

    @rtype: L{twisted.internet.defer.Deferred}
    """

    def checkCallback(result):
        for m in result.messages:
            obj.addMessage(m)

    d = callable(*args, **kwargs)
    d.addCallback(checkCallback)
    return d
