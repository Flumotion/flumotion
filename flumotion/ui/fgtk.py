# -*- Mode: Python; test-case-name: flumotion.test.test_ui_fgtk -*-
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
I am a collection of extended GTK widgets for use in Flumotion.
"""

import gtk
import gtk.gdk
from gtk import gdk
# FIXME: done for pychecker; apparently these imports before make
# import gtk; import gtk.glade in later files in the checking fail
import gtk.glade
import gobject

from flumotion.common import enum, compat

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
        self.pack_start(cell, True)
        self.add_attribute(cell, 'text', 0)
        return model

    def get_state(self):
        return self.get_enum()
compat.type_register(FComboBox)

class FEntry(gtk.Entry):
    def get_state(self):
        return self.get_text()
compat.type_register(FEntry)

class FCheckButton(gtk.CheckButton):
    def get_state(self):
        return self.get_active()
    
    def __nonzero__(self):
        return self.get_active()
compat.type_register(FCheckButton)

class FRadioButton(gtk.RadioButton):
    def get_state(self):
        return self.get_active()

    def __nonzero__(self):
        return self.get_active()
compat.type_register(FRadioButton)

class FSpinButton(gtk.SpinButton):
    def get_state(self):
        return self.get_value()
compat.type_register(FSpinButton)

# this VUMeter respects IEC standard
# BS 6840-18:1996/IEC-268-18
# and is inspired by JACK's meterbridge dpm_meters.c

class FVUMeter(gtk.DrawingArea):
    __gsignals__ = { 'expose-event' : 'override',
                     'size-allocate': 'override',
                     'size-request': 'override',
                     'realize' : 'override'
             }
    __gproperties__ = {
        'peak' : (gobject.TYPE_FLOAT,
                  'peak volume level',
                  'peak volume level in dB',
                  -90.0,
                  0,
                  -90.0,
                  gobject.PARAM_READWRITE),
        'decay' : (gobject.TYPE_FLOAT,
                   'decay volume level',
                   'decay volume level in dB',
                   -90.0,
                   0,
                   -90.0,
                   gobject.PARAM_READWRITE),
        'orange-threshold': (gobject.TYPE_FLOAT,
                            'threshold for orange',
                            'threshold for orange use in dB',
                            -90.0,
                            0,
                            -10.0,
                            gobject.PARAM_READWRITE),
        'red-threshold': (gobject.TYPE_FLOAT,
                         'threshold for red',
                         'threshold for red use in dB',
                         -90.0,
                         0,
                         -1.0,
                         gobject.PARAM_READWRITE)
                            
    }
    green_gc = None
    orange_gc = None
    red_gc = None
    yellow_gc = None
    
    topborder = 7
    peaklevel = -90.0
    decaylevel = -90.0
    orange_threshold = -10.0
    red_threshold = -1.0
    bottomborder = 25
    leftborder = 15 
    rightborder = 65 

    # Returns the meter deflection percentage given a db value
    def iec_scale(self, db):
        pct = 0.0

        if db < -70.0:
            pct = 0.0
        elif db < -60.0:
            pct = (db + 70.0) * 0.25
        elif db < -50.0:
            pct = (db + 60.0) * 0.5 + 2.5
        elif db < -40.0:
            pct = (db + 50.0) * 0.75 + 7.5
        elif db < -30.0:
            pct = (db + 40.0) * 1.5 + 15.0
        elif db < -20.0:
            pct = (db + 30.0) * 2.0 + 30.0
        elif db < 0.0:
            pct = (db + 20.0) * 2.5 + 50.0
        else:
            pct = 100.0

        return pct

    def do_get_property(self, property):
        if property.name == 'peak':
            return self.peaklevel
        elif property.name == 'decay':
            return self.decaylevel
        elif property.name == 'orange-threshold':
            return self.orange_threshold
        elif property.name == 'red-threshold':
            return self.red_threshold
        else:
            raise AttributeError, 'unknown property %s' % property.name

    def do_set_property(self, property, value):
        if property.name == 'peak':
            self.peaklevel = value
        elif property.name == 'decay':
            self.decaylevel = value
        elif property.name == 'orange-threshold':
            self.orange_threshold = value
        elif property.name == 'red-threshold':
            self.red_threshold = value
        else:
            raise AttributeError, 'unknown property %s' % property.name

        self.queue_draw()
                
    def do_size_request(self, requisition):
        requisition.width = 250 
        requisition.height = 50

    def do_size_allocate(self, allocation):
        self.allocation = allocation
        if self.flags() & gtk.REALIZED:
            self.window.move_resize(*allocation)
    
    def do_realize(self):
        self.set_flags(self.flags() | gtk.REALIZED)

        self.window = gdk.Window(self.get_parent_window(),
                                 width=self.allocation.width,
                                 height=self.allocation.height,
                                 window_type=gdk.WINDOW_CHILD,
                                 wclass=gdk.INPUT_OUTPUT,
                                 event_mask=self.get_events() | gdk.EXPOSURE_MASK)

        colormap = gtk.gdk.colormap_get_system()
        green = colormap.alloc_color(0, 65535, 0)
        orange = colormap.alloc_color(65535, 32768, 0)
        red = colormap.alloc_color(65535, 0, 0)
        yellow = colormap.alloc_color(65535, 65535, 0)
        self.green_gc = gdk.GC(self.window, foreground=green)
        self.orange_gc = gdk.GC(self.window, foreground=orange)
        self.red_gc = gdk.GC(self.window, foreground=red)
        self.yellow_gc = gdk.GC(self.window, foreground=yellow)
 
	    self.window.set_user_data(self)
        self.style.attach(self.window)
        self.style.set_background(self.window, gtk.STATE_NORMAL)

    def do_expose_event(self, event):
        self.chain(event)
       
        x, y, w, h = self.allocation
        vumeter_width = w - (self.leftborder + self.rightborder)
        vumeter_height = h - (self.topborder + self.bottomborder)
        self.window.draw_rectangle(self.style.black_gc, True,
                                   self.leftborder, self.topborder,
                                   vumeter_width, 
                                   vumeter_height)
        # draw peak level
        peaklevelpct = self.iec_scale(self.peaklevel)
        peakwidth = int(vumeter_width * (peaklevelpct/100))
        draw_gc = self.green_gc
        if self.peaklevel >= self.orange_threshold:
            draw_gc = self.orange_gc
        if self.peaklevel >= self.red_threshold:
            draw_gc = self.red_gc
        self.window.draw_rectangle(draw_gc, True,
                self.leftborder, self.topborder,
                peakwidth, vumeter_height)
 
        # draw yellow decay level
        if self.decaylevel > -90.0:
            decaylevelpct = self.iec_scale(self.decaylevel)
            decaywidth = int(vumeter_width * (decaylevelpct/100)) 
            self.window.draw_line(self.yellow_gc,
                self.leftborder + decaywidth,
                self.topborder,
                self.leftborder + decaywidth,
                self.topborder + vumeter_height)

        # draw tick marks
        scalers = [
            ('-90', 0.0),
            ('-40', 0.15),
            ('-30', 0.30),
            ('-20', 0.50),
            ('-10', 0.75),
            ( '-5', 0.875),
            (  '0', 1.0),
        ]
        for level, scale in scalers:
            self.window.draw_line(self.style.black_gc, 
                self.leftborder + int (scale * vumeter_width),
                h - self.bottomborder,
                self.leftborder + int(scale * vumeter_width),
                h - self.bottomborder + 5)
            self.window.draw_line(self.style.black_gc,
                self.leftborder, h - self.bottomborder,
                self.leftborder, h - self.bottomborder + 5)
            layout = self.create_pango_layout(level)
            layout_width, layout_height = layout.get_pixel_size()
            self.window.draw_layout(self.style.black_gc,
                self.leftborder + int(scale * vumeter_width) - int(layout_width / 2),
                h - self.bottomborder + 7, layout)

        # draw the peak level to the right
        layout = self.create_pango_layout("%.2fdB" % self.peaklevel)
        layout_width, layout_height = layout.get_pixel_size()
        self.window.draw_layout(self.style.black_gc,
            self.leftborder + vumeter_width + 5,
            self.topborder + int(vumeter_height/2 - layout_height/2),
            layout)

compat.type_register(FVUMeter)

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
