# -*- Mode: Python -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# flumotion/ui/fgtk.py: Flumotion GTK widget extensions
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

"""
I am a collection of extended GTK widgets for use in Flumotion.
"""

import gtk
import gtk.gdk
# FIXME: done for pychecker; apparently these imports before make
# import gtk; import gtk.glade in later files in the checking fail
import gtk.glade

import gobject

from flumotion.common import enum

class FComboBox(gtk.ComboBox):
    """
    I am an extended combobox that can be used as a string list combobox
    or with enums, with nick/name/value columns.
    """
    COLUMN_NICK = 0
    COLUMN_NAME = 1
    COLUMN_VALUE = 2

    _column_types = str, str, int
    
    def __len__(self):
        return len(self.get_model())

    def get_column_content(self, column):
        iter = self.get_active_iter()
        if iter:
            model = self.get_model()
            return model.get(iter, column)[0]
        
    def get_text(self):
        return self.get_column_content(self.COLUMN_NICK)
    
    def get_string(self):
        return self.get_column_content(self.COLUMN_NAME)

    def get_int(self):
        """
        Get name as integer.
        """
        s = self.get_string()
        if s:
            return int(s)
        return -1

    def get_value(self):
        return self.get_column_content(self.COLUMN_VALUE)

    def get_enum(self):
        # FIXME: EVIL, this should not return an integer as a fallback,
        # because you can't call enum methods on it then
        if hasattr(self, 'enum_class'):
            return self.enum_class.get(self.get_value())
        else:
            return self.get_value()
    
    def set_enum(self, enum_class, value_filter=()):
        """
        Set the given enum_class on the combobox.
        As a side effect, this makes the combobox an enum-based one.
        This also sets the combobox to the first enum value.
        """
        # throw away the old model completely
        self._init_enum_model()
        model = self.get_model()

        for enum in enum_class:
            # If values are specified, filter them out
            if value_filter and not enum in value_filter:
                continue
            iter = model.append()
            model.set(iter,
                      self.COLUMN_NAME, enum.name,
                      self.COLUMN_VALUE, enum.value,
                      self.COLUMN_NICK, enum.nick)

        self.set_active(0)
        self.enum_class = enum_class

    def set_list(self, list):
        """
        Set the given list of strings on the combobox.
        As a side effect, turns this into a regular text combobox again.
        """
        if hasattr(self, 'enum_class'):
            delattr(self, 'enum_class')
            
        self._init_enum_model()
        model = self.get_model()
        for value in list:
            iter = model.append()
            model.set(iter, 0, value, 1, value)
        self.set_active(0)

    def set_multi_active(self, *values): 
        if not hasattr(self, 'enum_class'):
            raise TypeError
        
        self.set_enum(self.enum_class, values)

    def set_active(self, item):
        """Small wrapper around set_active() to support enums"""
        if isinstance(item, enum.Enum):
            gtk.ComboBox.set_active(self, item.value)
        else:
            gtk.ComboBox.set_active(self, item)
            
    def get_active(self):
        """Small wrapper around get_active() to support enums"""
        value = gtk.ComboBox.get_active(self)
        if hasattr(self, 'enum_class'):
            value = self.enum_class.get(value)
        return value

    def _init_enum_model(self):
        # give ourselves a fresh enum_model
        model = gtk.ListStore(*self._column_types)
        self.set_model(model)
        self.clear()
        cell = gtk.CellRendererText()
        self.pack_start(cell, gtk.TRUE)
        self.add_attribute(cell, 'text', 0)
        return model

    def get_state(self):
        return self.get_enum()
gobject.type_register(FComboBox)

class FEntry(gtk.Entry):
    def get_state(self):
        return self.get_text()
gobject.type_register(FEntry)

class FCheckButton(gtk.CheckButton):
    def get_state(self):
        return self.get_active()
    
    def __nonzero__(self):
        return self.get_active()
gobject.type_register(FCheckButton)

class FRadioButton(gtk.RadioButton):
    def get_state(self):
        return self.get_active()

    def __nonzero__(self):
        return self.get_active()
gobject.type_register(FRadioButton)

class FSpinButton(gtk.SpinButton):
    def get_state(self):
        return self.get_value()
gobject.type_register(FSpinButton)

class WidgetMapping:
    # In PyGTK 2.4.0 gtk.glade.XML type_dict parameter is buggy
    # If it can't find the name it raises a silent KeyError which
    # will be raised at random point later (as soon some code call
    # PyErr_Occurred()), to avoid this, we reimplement the function
    # as it is internally, eg failback to the real GType, by doing
    # this PyMapping_GetItemString will never set the error.
    
    types = { 'GtkCheckButton': FCheckButton,
              'GtkComboBox': FComboBox,
              'GtkEntry': FEntry,
              'GtkRadioButton': FRadioButton,
              'GtkSpinButton': FSpinButton
            }
    
    def __getitem__(self, name):
        if self.types.has_key(name):
            return self.types[name]
        else:
            return gobject.type_from_name(name)
