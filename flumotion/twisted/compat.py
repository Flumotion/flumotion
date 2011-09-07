# -*- Mode: Python; test-case-name: flumotion.test.test_compat -*-
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

"""
Flumotion Twisted compatibility assistance

"""

import warnings

import zope.interface as zi

__version__ = "$Rev$"

from twisted.internet import reactor

try:
    reactor.seconds  # Introduced in Twisted 8.0.0
except AttributeError:
    from twisted.python import runtime
    reactor.seconds = runtime.seconds


# The following functions are deprecated; do not use them. They no longer
# provide any backwards compatibility.


def implementsInterface(object, interface):
    warnings.warn(
        "This module is deprecated, use zope.interface directly instead",
        DeprecationWarning, stacklevel=2)
    return interface.providedBy(object)


def implementedBy(object):
    warnings.warn(
        "This module is deprecated, use zope.interface directly instead",
        DeprecationWarning, stacklevel=2)
    return zi.implementedBy(object)


def isInterface(object):
    warnings.warn(
        "This module is deprecated, use zope.interface directly instead",
        DeprecationWarning, stacklevel=2)
    return isinstance(object, zi.InterfaceClass)

Interface = zi.Interface
implements = zi.implements
