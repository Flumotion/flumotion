# -*- Mode: Python -*-
# vi:si:et:sw=4:sts=4:ts=4
#
#
# flumotion/common/errors.py: common errors for flumotion
#
# Flumotion - a streaming media server
# Copyright (C) 2004 Fluendo, S.L. (www.fluendo.com). All rights reserved.

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

"""
Flumotion exceptions and pb.Error objects.

Maintainer: U{Johan Dahlin <johan@fluendo.com>}
"""

from twisted.spread import pb

class OptionError(Exception):
    pass

class PipelineParseError(pb.Error):
    "An error occurred while trying to parse the pipeline"

class NotReadyError(pb.Error):
    "The component is not ready yet"

class PropertyError(pb.Error):
    "An error occurred while setting a property on the component"

class AlreadyConnectedError(pb.Error):
    "The component is already connected to the manager"

class NoPerspectiveError(pb.Error):
    "The component does not have a perspective"
    
class SystemError(pb.Error):
    "A system error, is usually fatal"

class ReloadSyntaxError(pb.Error):
    "A syntax error during a reload of a module"

class ComponentStart(pb.Error):
    "An error during starting of a component"

class UnknownComponentError(pb.Error):
    "A given component or component type does not exist"

class RemoteRunError(pb.Error):
    "Error while running remote code"

class FlumotionError(pb.Error):
    "Generic Flumotion error"

class NoBundleError(pb.Error):
    "The requested bundle was not found"

# GStreamer errors
class GstError(pb.Error):
    "Generic GStreamer error"

class UnknownDeviceError(pb.Error):
    "The device does not exist"

class PermissionDeniedError(GstError):
    "Permission denied"

class DeviceBusyError(GstError):
    "Generic GStreamer error"
