# -*- Mode: Python -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# Flumotion - a video streaming server
# Copyright (C) 2004 Fluendo
# 
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
# 
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Street #330, Boston, MA 02111-1307, USA.

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
    
class AccessDeniedError(pb.Error):
    "Access was denied"
    
class SystemError(pb.Error):
    "A system error, is usually fatal"

class ReloadSyntaxError(pb.Error):
    "A syntax error during a reload of a module"
