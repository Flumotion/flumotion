# -*- Mode: Python -*-
# vi:si:et:sw=4:sts=4:ts=4
#
#
# flumotion/common/errors.py: common errors for flumotion
#
# Flumotion - a streaming media server
# Copyright (C) 2004 Fluendo (www.fluendo.com)

# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
# See "LICENSE.GPL" in the source distribution for more information.

# This program is also licensed under the Flumotion license.
# See "LICENSE.Flumotion" in the source distribution for more information.

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
