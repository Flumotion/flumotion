# -*- Mode: Python -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# flumotion/common/auth.py: authenticator helper
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

from twisted.python import components

from flumotion.common import interfaces

def getAuth(config, name):
    entry = config.getEntry(name)
    component = entry.getComponent()
    if not components.implements(component, interfaces.IAuthenticate):
        raise TypeError, "%s (%r) component must implement IAuthenticate" % (type, klass)
    
    return component
