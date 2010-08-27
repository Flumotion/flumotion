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

"""exceptions used by Flumotion, serializable and normal
"""

from twisted.spread import pb

__version__ = "$Rev$"


class CancelledError(Exception):
    "An operation was cancelled"


class OptionError(Exception):
    "Error in options"


class ConfigError(Exception):
    """
    Error during parsing of configuration

    args[0]: str
    """


class NoProjectError(Exception):
    """
    The given project does not exist

    @ivar projectName: name of the project
    @type projectName: str
    @ivar debug:       optional additional debug message
    @type debug:       str
    """

    def __init__(self, projectName, debug=None):
        self.projectName = projectName
        self.debug = debug
        # work like a normal Exception too
        self.args = (projectName, debug)


class NoSSLError(Exception):
    "SSL is not available"


# connection errors


class ConnectionError(pb.Error):
    "General connection error"


class NotConnectedError(ConnectionError):
    "Not connected"


class NotAuthenticatedError(ConnectionError):
    "Not authenticated"


class ConnectionRefusedError(ConnectionError):
    "Connection refused"


class ConnectionFailedError(ConnectionError):
    "Connection failed"


class ConnectionCancelledError(ConnectionError):
    "Connection attempt cancelled"


class ManagerNotConnectedError(NotConnectedError):
    "Manager not connected"


class AlreadyConnectingError(ConnectionError):
    "Already connecting"


class AlreadyConnectedError(ConnectionError):
    "Already connected"


class PipelineParseError(pb.Error):
    "An error occurred while trying to parse the pipeline"


# remote method errors


class RemoteMethodError(pb.Error):
    """
    Generic remote method error.

    @ivar methodName: name of the method
    @type methodName: str
    @ivar debug:      optional additional debug message
    @type debug:      str
    """

    def __init__(self, methodName, debug=None):
        self.methodName = methodName
        self.debug = debug
        # work like a normal Exception too
        self.args = (methodName, debug)

    # this allows us to decide how it gets serialized

    def __str__(self):
        msg = "%s on method '%s'" % (self.__class__.__name__, self.methodName)
        if self.debug:
            msg += " (%s)" % self.debug
        return msg


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


class FatalError(pb.Error):
    "A fatal error"

# F0.10
__pychecker__ = 'no-shadowbuiltin'


class SystemError(FatalError):

    def __init__(self, *args, **kwargs):
        import warnings
        warnings.warn("Please use builtin SystemError or errors.FatalError",
            DeprecationWarning, stacklevel=2)
        pb.Error.__init__(self, *args, **kwargs)
__pychecker__ = ''


class ReloadSyntaxError(pb.Error):
    "A syntax error during a reload of a module"


class WrongStateError(pb.Error):
    "The remote object was in the wrong state for this command"


class InsufficientPrivilegesError(pb.Error):
    "You do not have the necessary privileges to complete this operation"


# component errors


class ComponentError(pb.Error):
    """
    Error while doing something to a component.

    args[0]: ComponentState
    """


# FIXME: rename, component first


class SleepingComponentError(ComponentError):
    "Component is sleeping, cannot handle request"


class ComponentAlreadyStartingError(ComponentError):
    "Component told to start, but is already starting"


class ComponentAlreadyRunningError(ComponentError):
    "Component told to start, but is already running"


class ComponentMoodError(ComponentError):
    "Component is in the wrong mood to perform the given function"


class ComponentNoWorkerError(ComponentError):
    "Component does not have its worker available"


class BusyComponentError(ComponentError):
    """
    Component is busy doing something.

    args[0]: ComponentState
    args[1]: str
    """


class ComponentConfigError(ComponentError):
    """
    An error in the configuration of the component.

    args[0]: ComponentState
    args[1]: str
    """


class ComponentAlreadyExistsError(ComponentError):
    """
    A component name is already used.

    args[0]: L{flumotion.common.common.componentId}
    """


class ComponentCreateError(ComponentError):
    """
    An error during creation of a component.  Can be raised during a
    remote_create call on a worker.
    """


class HandledException(Exception):
    """
    An exception that has already been adequately handled, but still needs
    to be propagated to indicate failure to callers.

    This allows callers and defgens to propagate gracefully without
    doing a traceback, while still doing tracebacks for unhandled exceptions.

    Only argument is the original exception or failure.
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


class ComponentSetupHandledError(ComponentSetupError, HandledException):
    """
    An error during setup of a component, that's already handled in a
    different way (for example, through a message).
    Can be raised during a remote_setup call on a component.
    """


class ComponentStartHandledError(ComponentStartError, HandledException):
    """
    An error during starting of a component, that's already handled in a
    different way (for example, through a message).
    Can be raised during a remote_start call on a component.
    """


class UnknownComponentError(ComponentError):
    "A given component or component type does not exist"


class ComponentValidationError(ComponentError):
    "The configuration for the component is not valid"


class UnknownPlugError(pb.Error):
    "A given plug type does not exist"


# effect errors


class UnknownEffectError(pb.Error):
    "A given effect or effect type does not exist"


class FlumotionError(pb.Error):
    "Generic Flumotion error"


class NoBundleError(pb.Error):
    "The requested bundle was not found"


class TimeoutException(Exception):
    "Timed out"


# serializable GStreamer errors


class GStreamerError(pb.Error):
    "Generic GStreamer error"


class GStreamerGstError(GStreamerError):
    """GStreamer-generated error with source, GError and
    debug string as args"""


class MissingElementError(GStreamerError):
    "A needed element is missing"


class AccessDeniedError(Exception):
    "Access is denied to this object, usually a file or directory"


class NotDirectoryError(Exception):
    "Access to an object that is not a directory"
