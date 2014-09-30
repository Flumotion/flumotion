# -*- Mode: Python; test-case-name: flumotion.test.test_ui_fgtk -*-
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
I am a collection of extended GTK widgets for use in Flumotion.
"""

import gobject
import gtk

__version__ = "$Rev$"


class FProxyComboBox(gtk.ComboBox):

    def set_enum(self, enum_class, value_filter=()):
        """
        Set the given enum_class on the combobox.
        As a side effect, this makes the combobox an enum-based one.
        This also sets the combobox to the first enum value.
        """

        values = []
        liststore = gtk.ListStore(str, str)  
        self.set_model(liststore)
        cell_nick = gtk.CellRendererText()
        cell_name = gtk.CellRendererText()
        self.pack_start(cell_nick, True)
        self.pack_start(cell_name, True)
        self.add_attribute(cell_nick, 'text', 0)
        self.add_attribute(cell_name, 'text', 1)
        for enum in enum_class:
            # If values are specified, filter them out
            if value_filter and not enum in value_filter:
                continue
            values.append((enum.nick, enum))
        
        self.prefill(values)
        self.set_active(0)
        self.emit('changed')

    def create_model(self, itemdata):
        """ """
        if len(itemdata) < 1 or type(itemdata[0]) not in (list, tuple):
            liststore = gtk.ListStore(str)
        else:
            liststore = gtk.ListStore(*[type(x) for x in itemdata[0]])
        #import pdb; pdb.set_trace()     
        for ind, item in enumerate(itemdata):
            if type(item) not in (list, tuple):
                item = [item]
            liststore.insert(ind, item)
        self.set_model(liststore)
        return liststore
        

    def prefill(self, itemdata):
        model = self.get_model()
        if model is None:
            model = self.create_model(itemdata)
        values = set()
        is_tuple = False
        for item in itemdata:
            if type(item) == str:
                text = item
                data = None  
            else:
                text, data = item
                is_tuple = True
            orig = text
            count = 1
            while text in values:
                text = orig + ' (%d)' % count
                count += 1
            values.add(text)
            if is_tuple:
                model.append((text, data))
            else:
                model.append((text,))

gobject.type_register(FProxyComboBox)

class ProxyWidgetMapping:
    # In PyGTK 2.4.0 gtk.glade.XML type_dict parameter is buggy
    # If it can't find the name it raises a silent KeyError which
    # will be raised at random point later (as soon some code call
    # PyErr_Occurred()), to avoid this, we reimplement the function
    # as it is internally, eg failback to the real GType, by doing
    # this PyMapping_GetItemString will never set the error.

    types = {'GtkComboBox': FProxyComboBox}

    def __getitem__(self, name):
        if name in self.types:
            return self.types[name]
        else:
            return gobject.type_from_name(name)
