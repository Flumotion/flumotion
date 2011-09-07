# -*- Mode: Python -*-
# vi:si:et:sw=4:sts=4:ts=4

# Flumotion - a streaming media server
# Copyright (C) 2004,2005,2006,2007,2008,2009 Fluendo, S.L.
# Copyright (C) 2010,2011 Flumotion Services, S.A.
# All rights reserved.
#
# This file may be distributed and/or modified under the terms of
# the GNU Lesser General Public License version 2.1 as published by
# the Free Software Foundation.
# This file is distributed without any warranty; without even the implied
# warranty of merchantability or fitness for a particular purpose.
# See "LICENSE.LGPL" in the source distribution for more information.
#
# Headers in this file shall remain intact.

from flumotion.component.plugs import base

__version__ = "$Rev$"


class DiskerPlug(base.ComponentPlug):
    """
    Base class for disker plugs.
    """

    def recordingStarted(self, file, location):
        """
        Called before disker starts writing data to a new file.

        @param file:     the file object
        @type  file:     file
        @param location: the location of the file
        @type  location: str
        """
        pass

    def recordingStopped(self, file, location):
        """
        Called after disker stops writing data to a file.

        @param file:     the file object
        @type  file:     file
        @param location: the location of the file
        @type  location: str
        """
        pass
