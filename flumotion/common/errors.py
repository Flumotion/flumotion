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

"""
serializable Flumotion exceptions
"""

from twisted.spread import pb

class OptionError(Exception):
    "Error in options"
class ConfigError(Exception):
    "Error during parsing of configuration"
class NoProjectError(Exception):
    "The given project does not exist"

# connection errors
class ConnectionError(pb.Error):
    "General connection error"

class NotConnectedError(ConnectionError):
    "Not connected"

class ConnectionRefusedError(ConnectionError):
    "Connection refused"

class ConnectionFailedError(ConnectionError):
    "Connection failed"

class ManagerNotConnectedError(NotConnectedError):
    "Manager not connected"

class AlreadyConnectedError(ConnectionError):
    "Already connected"

class PipelineParseError(pb.Error):
    "An error occurred while trying to parse the pipeline"

# remote method errors
class RemoteMethodError(pb.Error):
    "Generic remote method error"

class RemoteRunError(RemoteMethodError):
    "Error while running remote code"

class NoMethodError(RemoteMethodError):
    "The remote method does not exist"

# FIXME: subclass from both entry/bundle and syntax errors ?
# FIXME: name ?
class EntrySyntaxError(pb.Error):
    "Syntax error while getting entry point in a bundle"

# other errors
class NotReadyError(pb.Error):
    "The component is not ready yet"

class PropertyError(pb.Error):
    "An error occurred while setting a property on the component"

class NoPerspectiveError(pb.Error):
    "The component does not have a perspective"
    
class SystemError(pb.Error):
    "A system error, is usually fatal"

class ReloadSyntaxError(pb.Error):
    "A syntax error during a reload of a module"

# component errors
class ComponentError(pb.Error):
    "Error while doing something to a component"
    
# FIXME: rename, component first
class SleepingComponentError(ComponentError):
    "Component is sleeping, cannot handle request"

class ComponentAlreadyStartingError(ComponentError):
    "Component told to start, but is already starting"

class ComponentMoodError(ComponentError):
    "Component is in the wrong mood to perform the given function"

class ComponentNoWorkerError(ComponentError):
    "Component does not have its worker available"

class BusyComponentError(ComponentError):
    "Component is busy doing something"

class ComponentCreate(ComponentError):
    "An error during creation of a component"

class ComponentStart(ComponentError):
    "An error during starting of a component"

class UnknownComponentError(ComponentError):
    "A given component or component type does not exist"

# effect errors
class UnknownEffectError(pb.Error):
    "A given effect or effect type does not exist"

class FlumotionError(pb.Error):
    "Generic Flumotion error"

class NoBundleError(pb.Error):
    "The requested bundle was not found"

# an exception for gst.Error
class GstError(Exception):
    """Takes an element, gst.Error.message and gst.Error.debug"""

# serializable GStreamer errors
class GStreamerError(pb.Error):
    "Generic GStreamer error"

class StateChangeError(GStreamerError):
    "The state change failed"

class UnknownDeviceError(GStreamerError):
    "The device does not exist"

class PermissionDeniedError(GStreamerError):
    "Permission denied"

class DeviceNotFoundError(GStreamerError):
    "Device could not be found"

class DeviceBusyError(GStreamerError):
    "Generic GStreamer error"
