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

import os
import sys

from flumotion.common import package, errors, log

import flumotion.project

__version__ = "$Rev$"


def list():
    """
    Returns a list of all add-on projects seen by Flumotion.
    """
    projects = [n for n in sys.modules.keys()
                      if n.startswith('flumotion.project')]
    paths = flumotion.project.__path__
    modules = []
    for path in paths:
        modules.extend(package.findEndModuleCandidates(
            os.path.abspath(os.path.join(path, '..', '..')),
            prefix='flumotion.project'))

    modules.remove('flumotion.project.project')

    return [n[len('flumotion.project.'):] for n in modules]


def get(project, attribute, default=None):
    """
    Get an attribute from a project's module.
    """
    log.debug('project', 'Getting attribute %s from project %s',
        attribute, project)

    moduleName = "flumotion.project.%s" % project
    try:
        exec("import %s" % moduleName)
    except ImportError, e:
        log.warning('project', 'Could not load project %s: %s',
            project, log.getExceptionMessage(e))
        raise errors.NoProjectError(moduleName)
    except SyntaxError:
        raise errors.NoProjectError(moduleName)
    m = sys.modules[moduleName]
    return getattr(m, attribute, default)
