# -*- Mode: Python -*-
# vi:si:et:sw=4:sts=4:ts=4

# Flumotion - a video streaming server
# Copyright (C) 2004 Fluendo
# 
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
# 
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Street #330, Boston, MA 02111-1307, USA.

import socket
import sys

import gobject
import gst

from flumotion.twisted import errors

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
    except socket.error, e:
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

    
