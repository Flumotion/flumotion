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
    "Error while running remote code, before getting a result"

class RemoteRunFailure(RemoteMethodError):
    "A remote method generated a failure result"

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

class WrongStateError(pb.Error):
    "The remote object was in the wrong state for this command"

class InsufficientPrivilegesError(pb.Error):
    "You do not have the necessary privileges to complete this operation"

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

class ComponentCreateError(ComponentError):
    """
    An error during creation of a component.  Can be raised during a
    remote_create call on a worker.
    """

class ComponentSetupError(ComponentError):
    """
    An error during setup of a component.  Can be raised during a
    remote_setup call on a component.
    """

class ComponentStartError(ComponentError):
    """
    An error during starting of a component.  Can be raised during a
    remote_start call on a component.
    """

class ComponentStartHandledError(ComponentStartError):
    """
    An error during starting of a component, that's already handled in a
    different way (for example, through a message).
    Can be raised during a remote_start call on a component.
    """

class UnknownComponentError(ComponentError):
    "A given component or component type does not exist"

# effect errors
class UnknownEffectError(pb.Error):
    "A given effect or effect type does not exist"

class FlumotionError(pb.Error):
    "Generic Flumotion error"

class NoBundleError(pb.Error):
    "The requested bundle was not found"

# serializable GStreamer errors
class GStreamerError(pb.Error):
    "Generic GStreamer error"

class GStreamerGstError(GStreamerError):
    """GStreamer-generated error with source, GError and debug string as args"""

class MissingElementError(GStreamerError):
    "A needed element is missing"
