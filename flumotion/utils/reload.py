# -*- Mode: Python -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# flumotion/utils/reload.py: code reload functionality
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
This module provides utility functions for Flumotion.
"""

import sys
from twisted.python.rebuild import rebuild
from flumotion.common import log

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
