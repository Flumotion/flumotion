# -*- Mode: Python; test-case-name: flumotion.test.test_common_pygobject -*-
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

"""pygobject helper functions
"""

# moving this down causes havoc when running this file directly for some reason
from flumotion.common import errors

import sys

import gobject

__version__ = "$Rev$"


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
    _locals = frame.f_locals

    if not '__gsignals__' in _locals:
        _dict = _locals['__gsignals__'] = {}
    else:
        _dict = _locals['__gsignals__']

    _dict[name] = (gobject.SIGNAL_RUN_FIRST, None, args)

PARAM_CONSTRUCT = 1<<9

def gproperty(type_, name, desc, *args, **kwargs):
    """
    Add a GObject property to the current object.
    To be used from class definition scope.

    @type type_: type object
    @type name: string
    @type desc: string
    @type args: mixed
    """
    frame = sys._getframe(1)
    _locals = frame.f_locals
    flags = 0

    def _do_get_property(self, prop):
        try:
            return self._gproperty_values[prop.name]
        except (AttributeError, KeyError):
            raise AttributeError('Property was never set', self, prop)

    def _do_set_property(self, prop, value):
        if not getattr(self, '_gproperty_values', None):
            self._gproperty_values = {}
        self._gproperty_values[prop.name] = value

    _locals['do_get_property'] = _do_get_property
    _locals['do_set_property'] = _do_set_property

    if not '__gproperties__' in _locals:
        _dict = _locals['__gproperties__'] = {}
    else:
        _dict = _locals['__gproperties__']

    for i in 'readable', 'writable':
        if not i in kwargs:
            kwargs[i] = True

    for k, v in kwargs.items():
        if k == 'construct':
            flags |= PARAM_CONSTRUCT
        elif k == 'construct_only':
            flags |= gobject.PARAM_CONSTRUCT_ONLY
        elif k == 'readable':
            flags |= gobject.PARAM_READABLE
        elif k == 'writable':
            flags |= gobject.PARAM_WRITABLE
        elif k == 'lax_validation':
            flags |= gobject.PARAM_LAX_VALIDATION
        else:
            raise Exception('Invalid GObject property flag: %r=%r' % (k, v))

    _dict[name] = (type_, name, desc) + args + tuple((flags,))

def type_register(klass):
    if klass.__gtype__.pytype is not klass:
        # all subclasses will at least have a __gtype__ from their
        # parent, make sure it corresponds to the exact class
        gobject.type_register(klass)
