# -*- Mode: Python -*-
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


import pygtk
pygtk.require('2.0')

import gobject


class Foo(gobject.GObject):
    __gproperties__ = {'frob': (
        bool, 'frob', 'frob foo', False,
        gobject.PARAM_READWRITE|gobject.PARAM_CONSTRUCT)}

    def __init__(self):
        gobject.GObject.__init__(self)

    def do_get_property(self, prop):
        print self, prop
        return self.properties[prop.name]

    def do_set_property(self, prop, value):
        print self, prop, value
        if not getattr(self, 'properties', None):
            self.properties = {}
        self.properties[prop.name] = value
gobject.type_register(Foo)

x = Foo()

# should return False, instead raises an AttributeError because the
# object the property was set on is not the object we received from the
# constructor. Strange.
print x.get_property('frob')
