# -*- Mode: Python -*-
# vi:si:et:sw=4:sts=4:ts=4

# Flumotion - a video streaming server
# Copyright (C) 2004 Fluendo
#
# flumotion/utils/__init__.py: Flumotion utility functions
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
This module provides utility functions for Flumotion.
"""

import sys
from twisted.python.rebuild import rebuild
from flumotion.utils import log
def reload():
    """Properly reload all flumotion-related modules currently loaded."""
    _ignore = (
        'flumotion.twisted.pygtk',
        'flumotion.twisted.gst',
        'flumotion.twisted.gobject',
        # added because for some reason rebuilding it makes all log.Loggable
        # subclass objects lose their log methods ...
        'flumotion.utils.log',
    )
    for name in sys.modules.keys():
        if name in _ignore:
            continue
        if not name.startswith('flumotion'):
            continue

        if not sys.modules.has_key(name):
            log.warning("reload", "hm, %s disappeared from the modules" % name)
            continue
        module = sys.modules[name]
        if not module:
            log.log("reload", "hm, module '%s' is None" % name)
            continue
        log.log("reload", "rebuilding %s" % module)
        rebuild(module, doLog=0)
