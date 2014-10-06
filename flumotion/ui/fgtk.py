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
        self.enum_objects = []
        self.init_model() 
        for enum in enum_class:
            # If values are specified, filter them out
            if value_filter and not enum in value_filter:
                continue
            values.append((enum.name,))
        
        self.prefill(values)
        self.set_active(0)
        self.emit('changed')


    def init_model(self):
        """ """
        liststore = gtk.ListStore(str)
        self.set_model(liststore)
        cell = gtk.CellRendererText()
        self.pack_start(cell, True)
        self.add_attribute(cell, 'text', 0)
        return liststore
 
        
    def get_selected(self):
        """ """
        tIter = self.get_active_iter()
        model = self.get_model()
        row =  model.get(tIter, *range(model.get_n_columns()))
        if hasattr(self, 'prefill_objects'):
            for o in self.prefill_objects:
                if row[0] == o[0]:
                    print("Got selected object...%s" % str(o))
                    return o[1]
        return row
        

    def select_item_by_data(self, value):
        """ """
        model = self.get_model()
        if not model:
            model = self.init_model()
        tIter = model.get_iter_first()
        while tIter:
            row = model.get(tIter, *range(model.get_n_columns()))
            print("Got the following row from the combobox: %s" % str(row))
            print("Value to compare against is: %s" % value)
            if hasattr(self, 'prefill_objects'):
                for o in self.prefill_objects:
                    if row[0] == o[0] and value in o[1]:
                        print("Matched value to object...%s" % o[1])
                        self.set_active_iter(tIter)
                        tIter = None
                if tIter:
                    tIter = model.iter_next(tIter)
            elif row[0] == value or value in [i for i in row[0]]:
                    self.set_active_iter(tIter)
                    tIter = None
            else:
                tIter = model.iter_next(tIter)



    def prefill(self, itemdata):
        print("Just got prefill data for the combobox: %s" % str(itemdata))
        model = self.get_model()
        if model is None:
            model = self.init_model()
        values = set()
        is_tuple = False
        self.prefill_objects = itemdata
        for item in itemdata:
            if type(item) == str:
                text = item
                data = None  
            else:
                text = item[0]
                is_tuple = True
            orig = text
            count = 1
            while text in values:
                text = orig + ' (%d)' % count
                count += 1
            values.add(text)
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
