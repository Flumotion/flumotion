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
PyGTK helper functions
"""

# moving this down causes havoc when running this file directly for some reason
from flumotion.common import errors

import sys

import gobject

def gobject_set_property(object, property, value):
    """
    Set the given property to the given value on the given object.

    @type object:   L{gobject.GObject}
    @type property: string
    @param value:   value to set property to
    """
    for pspec in gobject.list_properties(object):
        if pspec.name == property:
            break
    else:
        raise errors.PropertyError(
            "Property '%s' in element '%s' does not exist" % (
                property, object.get_property('name')))
        
    if pspec.value_type in (gobject.TYPE_INT, gobject.TYPE_UINT,
                            gobject.TYPE_INT64, gobject.TYPE_UINT64):
        try:
            value = int(value)
        except ValueError:
            msg = "Invalid value given for property '%s' in element '%s'" % (
                property, object.get_property('name'))
            raise errors.PropertyError(msg)
        
    elif pspec.value_type == gobject.TYPE_BOOLEAN:
        if value == 'False':
            value = False
        elif value == 'True':
            value = True
        else:
            value = bool(value)
    elif pspec.value_type in (gobject.TYPE_DOUBLE, gobject.TYPE_FLOAT):
        value = float(value)
    elif pspec.value_type == gobject.TYPE_STRING:
        value = str(value)
    # FIXME: this is superevil ! we really need to find a better way
    # of checking if this property is a param enum  
    # also, we only allow int for now
    elif repr(pspec.__gtype__).startswith("<GType GParamEnum"):
        value = int(value)
    else:
        raise errors.PropertyError('Unknown property type: %s' %
            pspec.value_type)

    object.set_property(property, value)

def gsignal(name, *args):
    """
    Add a GObject signal to the current object.
    To be used from class definition scope.

    @type name: string
    @type args: mixed
    """
    frame = sys._getframe(1)
    locals = frame.f_locals
    
    if not '__gsignals__' in locals:
        dict = locals['__gsignals__'] = {}
    else:
        dict = locals['__gsignals__']

    dict[name] = (gobject.SIGNAL_RUN_FIRST, None, args)
