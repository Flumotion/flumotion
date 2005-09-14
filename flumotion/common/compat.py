# -*- Mode: Python -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# Flumotion - a streaming media server
# Copyright (C) 2004,2005 Fluendo, S.L. (www.fluendo.com). All rights reserved.

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
Compatibility for various versions of supporting libraries
"""

import gtk
import gobject

# We don't want to get the loud deprecation warnings from PyGtk for using
# gobject.type_register() if we don't need it
def type_register(type):
  (major, minor, patch) = gtk.pygtk_version
  if(major <= 1 and minor < 8):
    gobject.type_register(type)
  elif(not (hasattr(type, '__gtype_name__' or hasattr(type, '__gproperties__')
         or hasattr(type, '__gsignals__'))):
    gobject.type_register(type)

