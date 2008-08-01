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

"""
functions based on twisted.python.reflect
"""

# FIXME: clean up unused imports
from twisted.cred import checkers, credentials
from twisted.cred.portal import IRealm, Portal
from twisted.internet import protocol
from twisted.python import log, reflect
from twisted.spread import pb, flavors
from twisted.spread.pb import PBClientFactory

__version__ = "$Rev$"


### stolen from twisted.python.reflect and changed
### the version in Twisted 1.3.0 checks length of backtrace as metric for
### ImportError; for me this fails because two lines of ihooks.py are in
### between
### filed as http://www.twistedmatrix.com/users/roundup.twistd/twisted/issue698
### remove this when fixed and depending on new upstream twisted


def namedAny(name):
    """Get a fully named package, module, module-global object, or attribute.
    """
    names = name.split('.')
    topLevelPackage = None
    moduleNames = names[:]
    while not topLevelPackage:
        try:
            trialname = '.'.join(moduleNames)
            topLevelPackage = __import__(trialname)
        except ImportError:
            import sys
            # if the ImportError happened in the module being imported,
            # this is a failure that should be handed to our caller.
            shortname = trialname.split('.')[-1]
            r = str(sys.exc_info()[1])
            if not (r.startswith('No module named') and
                    r.endswith(shortname)):
                raise

            #if str(sys.exc_info()[1]) != "No module named %s" % trialname:
            #    raise
            moduleNames.pop()

    obj = topLevelPackage
    for n in names[1:]:
        obj = getattr(obj, n)

    return obj
