# -*- Mode: Python -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# flumotion/common/launcher.py: launch grids
#
# Flumotion - a streaming media server
# Copyright (C) 2004 Fluendo (www.fluendo.com)

# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
# See "LICENSE.GPL" in the source distribution for more information.

# This program is also licensed under the Flumotion license.
# See "LICENSE.Flumotion" in the source distribution for more information.

import sys
sys.path.insert(0, '../..')
import pygtk
pygtk.require('2.0')

import os

import gobject
import gtk
import gtk.glade

from flumotion.config import gladedir
from flumotion.utils import log

class Stack(list):
    push = list.append
    def peek(self):
        return self[-1]

class WizardComboBox(gtk.ComboBox):
    COLUMN_NAME = 0
    COLUMN_VALUE = 1
    def __len__(self):
        model = self.get_model()
        iter = model.get_iter((0,))
        return model.iter_n_children(iter)
        
    def get_text(self):
        iter = self.get_active_iter()
        model = self.get_model()
        return model.get(iter, self.COLUMN_NAME)[0]

    def get_value(self):
        iter = self.get_active_iter()
        model = self.get_model()
        return model.get(iter, self.COLUMN_VALUE)[0]

    def set_enum(self, enum, value_filter=()):
        model = gtk.ListStore(str, int)
        self.set_model(model)
        for value, name in enum:
            # If values are specified
            if value_filter and not value in value_filter:
                continue
            iter = model.append()
            model.set(iter,
                      self.COLUMN_NAME, name,
                      self.COLUMN_VALUE, value)

        self.set_active(0)
        self.enum = enum
        
    def set_multi_active(self, *values): 
        if not hasattr(self, 'enum'):
            raise TypeError
        
        self.set_enum(self.enum, values)
        if len(values) == 1:
            self.set_sensitive(False)
        else:
            self.set_sensitive(True)

    def get_state(self):
        return self.get_text()
gobject.type_register(WizardComboBox)

class WizardEntry(gtk.Entry):
    def get_state(self):
        return self.get_text()
gobject.type_register(WizardEntry)
    
class WizardCheckButton(gtk.CheckButton):
    def get_state(self):
        return self.get_active()
    
    def __nonzero__(self):
        return self.get_active()
gobject.type_register(WizardCheckButton)

class WizardRadioButton(gtk.RadioButton):
    def get_state(self):
        return self.get_active()

    def __nonzero__(self):
        return self.get_active()
gobject.type_register(WizardRadioButton)

class WizardSpinButton(gtk.SpinButton):
    def get_state(self):
        return self.get_value()
gobject.type_register(WizardSpinButton)

class WizardStep(object, log.Loggable):
    step_name = None # Subclass sets this
    glade_file = None # Subclass sets this

    types = dict(GtkComboBox=WizardComboBox,
                 GtkEntry=WizardEntry,
                 GtkCheckButton=WizardCheckButton,
                 GtkRadioButton=WizardRadioButton,
                 GtkSpinButton=WizardSpinButton)
    
    def __init__(self, wizard):
        #self.__gobject_init__()
        self.wizard = wizard
        self.widget = None
        
        self.load_glade()
        
    def load_glade(self):
        self.wtree = gtk.glade.XML(os.path.join(gladedir, self.glade_file),
                                   typedict=self.types)
        self.wtree.signal_autoconnect(self)
        
        windows = []
        self.widgets = self.wtree.get_widget_prefix('')
        for widget in self.widgets:
            name = widget.get_name()
            if isinstance(widget, gtk.Window):
                widget.hide()
                windows.append(widget)
                continue
            
            if isinstance(widget, WizardComboBox):
                widget.set_active(0)
            
            if hasattr(self, name):
                raise TypeError
            setattr(self, name, widget)

        if len(windows) != 1:
            raise AssertionError, "only one window per glade file allowed"

        self.window = windows[0]
        child = self.window.get_children()[0]
        self.window.remove(child)
        self.widget = child
        
    def get_main_widget(self):
        return self.widget

    def get_state(self):
        widget_prefixes = { WizardComboBox    : 'combobox',
                            WizardCheckButton : 'checkbutton',
                            WizardEntry       : 'entry',
                            WizardSpinButton  : 'spinbutton',
                            WizardRadioButton : 'radiobutton' }

        state_dict = {}
        for widget in self.widgets:
            name = widget.get_name()
            prefix = widget_prefixes.get(widget.__class__, None)
            if not prefix:
                continue
            key = name.split('_', 1)[1]
            state_dict[key] = widget

        return state_dict
    
    def next_step(self):
        "A subclass must implement this"
        raise NotImplementedError

    def activated(self):
        "This can be implemented in a subclass"
        
    def deactivated(self):
        "This can be implemented in a subclass"

    def setup(self):
        "This can be implemented in a subclass"
#gobject.type_register(WizardStep)

class Wizard:
    def __init__(self):
        self.wtree = gtk.glade.XML(os.path.join(gladedir, 'wizard.glade'))
        self.wtree.signal_autoconnect(self)
        self.window = self.wtree.get_widget('wizard')
        self.content_area = self.wtree.get_widget('content_area')
        self.label_title = self.wtree.get_widget('label_title')
        self.button_prev = self.wtree.get_widget('button_prev')
        self.button_next = self.wtree.get_widget('button_next')
        
        self.steps = {}
        self.stack = Stack()
        self.current_step = None
        
    def get_step_option(self, stepname, option):
        step = self[stepname]
        state = self.get_step_state(step)
        return state[option]

    def __getitem__(self, stepname):
        return self.steps[stepname]
    
    def add_step(self, step_class, initial=False):
        # If we don't have step_name set, count it as a base class
        name = step_class.step_name
        if name == None:
            return
        
        if self.steps.has_key(name):
            raise TypeError, "%s added twice" % name
        
        self.steps[name] = step = step_class(self)

        state = self.get_step_state(step)
        assert type(state) == dict
        assert state, state
        
        step.setup()
        
        if initial:
            self.stack.push(step)

    def set_step(self, step):
        # Remove previous step
        for child in self.content_area.get_children():
            self.content_area.remove(child)

        # Add current
        widget = step.get_main_widget()
        self.content_area.add(widget)

        title = step.step_name
        title = title.replace('&', '&amp;')
        self.label_title.set_markup('<span size="large">' + title + '</span>')

        if self.current_step:
            self.current_step.deactivated()

        # Finally show
        widget.show()
        step.activated()
        
        self.current_step = step

    def on_wizard_delete_event(self, wizard, event):
        gtk.main_quit()

    def on_button_prev_clicked(self, button):
        self.stack.pop()
        prev_step = self.stack.peek()
        self.set_step(prev_step)

        self.update_buttons()

    def get_step_state(self, step):
        state = step.get_state()
        dict = {}
        for key, widget in state.items():
            dict[key] = widget.get_state()
        return dict
    
    def on_button_next_clicked(self, button):
        print self.get_step_state(self.current_step)
        
        next = self.current_step.get_next()
        if not next:
            self.finish()
            return

        try:
            next_step = self.steps[next]
        except KeyError:
            raise TypeError, "Wizard step %s is missing" % `next`
    
        self.stack.push(next_step)
        self.set_step(next_step)

        self.update_buttons()

    def update_buttons(self):
        if len(self.stack) == 1:
            self.button_prev.set_sensitive(False)
        else:
            self.button_prev.set_sensitive(True)

        current_step = self.stack.peek()
        if not current_step.get_next():
            self.button_next.set_label(gtk.STOCK_QUIT)
        else:
            self.button_next.set_label(gtk.STOCK_GO_FORWARD)

    def block_next(self, block):
        self.button_next.set_sensitive(not block)

    def block_prev(self, block):
        self.button_prev.set_sensitive(not block)

    def finish(self):
        gtk.main_quit()
        
    def run(self):
        if not self.stack:
            raise TypeError, "need an initial step"
        
        self.set_step(self.stack.peek())
        
        self.window.show_all()
        gtk.main()

#INITIAL_STEP = 'WizardStepSource'
INITIAL_STEP = 'WizardStepConsumption'

if __name__ == '__main__':
    from flumotion.wizard import wizard_step as ws
    wiz = Wizard()
    for attrname in dir(ws):
        if attrname.startswith('__'):
            continue

        initial = False
        if attrname == INITIAL_STEP:
            initial = True
        
        attr = getattr(ws, attrname)
        if type(attr) == type:
            # EEEEEEEVIL
            if 'WizardStep' in attr.__bases__[0].__name__:
                wiz.add_step(attr, initial)
    wiz.run()
