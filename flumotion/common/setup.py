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

"""initalizing logging and package paths.
"""

__version__ = "$Rev$"


def setup():
    """
    Set up the logging system.
    """
    from flumotion.common import log
    log.init()

def setupPackagePath():
    """
    set up all project paths specified in the FLU_PROJECT_PATH environment
    variable.

    This should be called by every Flumotion binary before starting/importing
    any other flumotion code.
    """
    import os
    from flumotion.common import package, log
    from flumotion.configure import configure

    registryPaths = [configure.pythondir, ]
    if 'FLU_PROJECT_PATH' in os.environ:
        paths = os.environ['FLU_PROJECT_PATH']
        registryPaths += paths.split(':')

    log.debug('setup', 'registry paths: %s' % ", ".join(registryPaths))
    for path in registryPaths:
        log.debug('setup', 'registering package path: %s' % path)
        # we register with the path as part of the key, since
        # these aren't meant to be replaced
        package.getPackager().registerPackagePath(path,
            "FLU_PROJECT_PATH_" + path)
