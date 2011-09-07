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

"""reloading of code
"""

import sys

from twisted.python.rebuild import rebuild

from flumotion.common import log

__version__ = "$Rev$"


def reloadFlumotion():
    """Properly reload all flumotion-related modules currently loaded."""
    needs_reload = lambda name: name.startswith('flumotion')
    for name in filter(needs_reload, sys.modules.keys()):
        if not name in sys.modules:
            log.warning("reload", "hm, %s disappeared from the modules" % name)
            continue
        module = sys.modules[name]
        if not module:
            log.log("reload", "hm, module '%s' == None" % name)
            continue
        log.log("reload", "rebuilding %s" % module)
        try:
            rebuild(module, doLog=0)
        except SyntaxError, msg:
            from flumotion.common import errors
            raise errors.ReloadSyntaxError(msg)

    # FIXME: ignores programmatic FLU_DEBUG changes over the life of a
    # process
    reinitialize = {'flumotion.extern.log.log':
                    lambda mod: mod.init('FLU_DEBUG')}
    for name in reinitialize:
        if name in sys.modules:
            reinitialize[name](sys.modules[name])
