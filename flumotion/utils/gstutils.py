# -*- Mode: Python -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# flumotion/utils/gstutils.py: GStreamer utility functions
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

import socket
import sys

# moving this down causes havoc when running this file directly for some reason
from flumotion.common import errors

import gobject
import gst


def caps_repr(caps):
    value = str(caps)
    pos = value.find('streamheader')
    if pos != -1:
        return 'streamheader=<...>'
    else:
        return value
        
def verbose_deep_notify_cb(object, orig, pspec, component):
    value = orig.get_property(pspec.name)
    if pspec.value_type == gobject.TYPE_BOOLEAN:
        if value:
            value = 'TRUE'
        else:
            value = 'FALSE'
        output = value
    elif pspec.value_type == gst.Caps.__gtype__:
        output = caps_repr(value)
    else:
        output = value

    # Filters
    if pspec.name == 'active':
        return
    if pspec.name == 'caps' and output == 'None':
        return
    
    component.debug('%s: %s = %s' % (orig.get_path_string(),
                                   pspec.name,
                                   output))

# XXX: move this to a separate file
def is_port_free(port):
    assert type(port) == int
    fd = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        fd.bind(('', port))
    except socket.error:
        return False
    
    return True
    
def get_free_port(start):
    port = start
    while 1:
        if is_port_free(port):
            return port
        port += 1


def gobject_set_property(object, property, value):
    for pspec in gobject.list_properties(object):
        if pspec.name == property:
            break
    else:
        raise errors.PropertyError("Property '%s' in element '%s' does not exist" % (property, object.get_property('name')))
        
    if pspec.value_type in (gobject.TYPE_INT, gobject.TYPE_UINT,
                            gobject.TYPE_INT64, gobject.TYPE_UINT64):
        try:
            value = int(value)
        except ValueError:
            msg = "Invalid value given for property '%s' in element '%s'" % (property, object.get_property('name'))
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
        raise errors.PropertyError('Unknown property type: %s' % pspec.value_type)

    object.set_property(property, value)

def gsignal(name, *args):
    """
    Add a GObject signal to the current object.
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

def element_factory_has_property(element_factory, property_name):
    """
    Check if the given element factory has the given property.
    """
    # FIXME: find a better way than instantiating one
    # FIXME: add simple unit test
    e = gst.element_factory_make(element_factory)
    for pspec in gobject.list_properties(e):
        if pspec.name == property_name:
            return True
    return False
  
