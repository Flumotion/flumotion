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
from flumotion.wizard import enums

def escape(text):
    return text.replace('&', '&amp;')

class Stack(list):
    push = list.append
    def peek(self):
        return self[-1]

class WizardComboBox(gtk.ComboBox):
    COLUMN_NICK = 0
    COLUMN_NAME = 1
    COLUMN_VALUE = 2

    _column_types = str, str, int
    
    def __len__(self):
        model = self.get_model()
        iter = model.get_iter((0,))
        return model.iter_n_children(iter)

    def get_column_content(self, column):
        iter = self.get_active_iter()
        if iter:
            model = self.get_model()
            return model.get(iter, column)[0]
        
    def get_text(self):
        return self.get_column_content(self.COLUMN_NICK)
    
    def get_string(self):
        return self.get_column_content(self.COLUMN_NAME)

    def get_value(self):
        return self.get_column_content(self.COLUMN_VALUE)

    def get_enum(self):
        return self.enum_class.get(self.get_value())
    
    def set_enum(self, enum_class, value_filter=()):
        model = self.get_model()
        model.clear()
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
        
    def set_multi_active(self, *values): 
        if not hasattr(self, 'enum_class'):
            raise TypeError
        
        self.set_enum(self.enum_class, values)
        if len(values) == 1:
            self.set_sensitive(False)
        else:
            self.set_sensitive(True)

    def set_active(self, item):
        if isinstance(item, enums.Enum):
            gtk.ComboBox.set_active(self, item.value)
        else:
            gtk.ComboBox.set_active(self, item)
            
    def get_active(self):
        value = gtk.ComboBox.get_active(self)
        if hasattr(self, 'enum_class'):
            value = self.enum_class.get(value)
        return value

    def copy_model(self, old):
        model = gtk.ListStore(*self._column_types)
        value = 0
        for item in old:
            name = old.get(item.iter, 0)[0]
            iter = model.append()
            model.set(iter,
                      self.COLUMN_NAME, name,
                      self.COLUMN_NICK, name,
                      self.COLUMN_VALUE, value)
            value += 1
        self.set_model(model)
        
    def get_state(self):
        return int(self.get_value())
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
    widget_prefixes = { WizardComboBox    : 'combobox',
                        WizardCheckButton : 'checkbutton',
                        WizardEntry       : 'entry',
                        WizardSpinButton  : 'spinbutton',
                        WizardRadioButton : 'radiobutton' }

    def __init__(self, wizard):
        self.wizard = wizard
        self.widget = None
        
        self.load_glade()

    def __repr__(self):
        return '<WizardStep object %s>' % self.step_name
    
    def load_glade(self):
        glade_filename = os.path.join(gladedir, self.glade_file)
        
        # In PyGTK 2.4.0 this raises an AttributeError which
        # is silently ignored. We need to find out a way to call
        # PyErr_Clear() if we want to support it, otherwise things
        # will go wrong in mysterious places later on.
        self.wtree = gtk.glade.XML(glade_filename,
                                   typedict=self.types)
        
        windows = []
        self.widgets = self.wtree.get_widget_prefix('')
        for widget in self.widgets:
            name = widget.get_name()
            if isinstance(widget, gtk.Window):
                widget.hide()
                windows.append(widget)
                continue
            
            if isinstance(widget, WizardComboBox):
                old = widget.get_model()
                widget.copy_model(old)
                widget.set_active(0)
                    
            if hasattr(self, name):
                raise TypeError
            setattr(self, name, widget)

        if len(windows) != 1:
            raise AssertionError("only one window per glade file allowed")

        self.window = windows[0]
        child = self.window.get_children()[0]
        self.window.remove(child)
        self.widget = child

        # And at last, connect signals.
        self.wtree.signal_autoconnect(self)
        
    def get_component_properties(self):
        return self.wizard.get_step_state(self)
    
    def get_main_widget(self):
        return self.widget

    def get_state(self):
        state_dict = {}
        for widget in self.widgets:
            name = widget.get_name()
            prefix = self.widget_prefixes.get(widget.__class__, None)
            if not prefix:
                continue
            key = name.split('_', 1)[1]
            state_dict[key] = widget

        return state_dict
    
    def get_next(self):
        """
        @returns name of next step
        @rtype   string

        This is called when the user presses next in the wizard,
        
        A subclass must implement this"""
        
        raise NotImplementedError

    def activated(self):
        """Called just before the step is shown, so the step can
        do some logic, eg setup the default state

        This can be implemented in a subclass"""
        
    def deactivated(self):
        """Called after the user pressed next

        This can be implemented in a subclass"""

    def setup(self):
        """This is called after the step is constructed, to be able to
        do some initalization time logic in the steps.

        This can be implemented in a subclass."""

        

class Wizard:
    def __init__(self):
        self.wtree = gtk.glade.XML(os.path.join(gladedir, 'wizard.glade'))
        for widget in self.wtree.get_widget_prefix(''):
            setattr(self, widget.get_name(), widget)
        self.wtree.signal_autoconnect(self)
        
        self.steps = {}
        self.stack = Stack()
        self.current_step = None

    def __getitem__(self, stepname):
        return self.steps[stepname]
    
    def get_step_option(self, stepname, option):
        state = self.get_step_options(stepname)
        return state[option]

    def get_step_options(self, stepname):
        step = self[stepname]
        return self.get_step_state(step)
    
    def get_step_state(self, step):
        state = step.get_state()
        dict = {}
        for key, widget in state.items():
            dict[key] = widget.get_state()
        return dict
    
    def block_next(self, block):
        self.button_next.set_sensitive(not block)

    def block_prev(self, block):
        self.button_prev.set_sensitive(not block)

    def add_step(self, step_class, initial=False):
        # If we don't have step_name set, count it as a base class
        name = step_class.step_name
        if name == None:
            return
        
        if self.steps.has_key(name):
            raise TypeError("%s added twice" % name)
        
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

        self.label_title.set_markup('<span size="large">' + escape(step.step_name) + '</span>')

        if self.current_step:
            self.current_step.deactivated()

        self.update_sidebar(step)
        
        # Finally show
        widget.show()
        step.activated()
        
        self.current_step = step

    def show_previous(self):
        self.stack.pop()
        prev_step = self.stack.peek()
        self.set_step(prev_step)

        self.update_buttons(has_next=True)

    def show_next(self):
        self.show_info(self.current_step)
        
        next = self.current_step.get_next()
        if not next:
            self.finish()
            return

        try:
            next_step = self.steps[next]
        except KeyError:
            raise TypeError("Wizard step %s is missing" % `next`)
    
        self.stack.push(next_step)
        self.set_step(next_step)

        self.update_buttons(next)

    def update_buttons(self, has_next):
        if len(self.stack) == 1:
            self.button_prev.set_sensitive(False)
        else:
            self.button_prev.set_sensitive(True)

        # XXX: Use the current step, not the one on the top of the stack
        current_step = self.stack.peek()
        if has_next:
            self.button_next.set_label(gtk.STOCK_GO_FORWARD)
        else:
            self.button_next.set_label(gtk.STOCK_QUIT)

    def show_info(self, step):
        if not hasattr(step, 'component_name'):
            return
        
        print '<component name="%s" type="%s">' % (step.component_name,
                                                   step.component_type)
        options = step.get_component_properties()
        for key, value in options.items():
            print '  <%s>%s</%s> ' % (key, value, key)
        print '</component>'

    def add_sidebar_step(self, name, padding):
        hbox = gtk.HBox(0, False)
        hbox.show()
        
        label = gtk.Label()
        label.set_markup(escape(name))
        label.show()
        hbox.pack_start(label, False, padding=padding)
        self.vbox_sidebar.pack_start(hbox, False, False, 6)

        return label
    
    def add_sidebar_substeps(self, section):
        # Skip the last step, since that's what we're currently showing
        stack = self.stack[:-1]

        # Filter out steps which is not the same category
        items = [item for item in stack
                          if item.section == section]
        for item in items:
            self.add_sidebar_step(item.step_name, 20)
            
    def update_sidebar(self, step):
        current = step.section

        # First remove the old the VBox if we can find one
        parent = self.vbox_sidebar.get_parent()
        if parent:
            parent.remove(self.vbox_sidebar)
        self.vbox_sidebar = gtk.VBox()
        self.hbox_main.pack_start(self.vbox_sidebar)
        self.hbox_main.reorder_child(self.vbox_sidebar, 0)

        # Then, for each section step, add a VBox with a label in it
        sidebar_steps = ('Production', 'Conversion',
                         'Consumption', 'License')
        for stepname in sidebar_steps:
            # If it's not the current step, just add it
            if current != stepname:
                markup = '<span color="grey">%s</span>' % stepname
                self.add_sidebar_step(markup, 10)
                continue
            
            markup = '<span color="black">%s</span>' % stepname                
            self.add_sidebar_step(markup, 10)

            self.add_sidebar_substeps(stepname)

            # Placeholder label, which expands vertically
            ph = gtk.Label()
            ph.show()
            self.vbox_sidebar.pack_start(ph)
            
        self.vbox_sidebar.show()
        
    def on_wizard_delete_event(self, wizard, event):
        self.finish()

    def on_button_prev_clicked(self, button):
        self.show_previous()

    def on_button_next_clicked(self, button):
        self.show_next()

    def finish(self):
        gtk.main_quit()
        
    def run(self):
        if not self.stack:
            raise TypeError("need an initial step")

        self.set_step(self.stack.peek())
        
        self.window.show()
        gtk.main()


if __name__ == '__main__':
    INITIAL_STEP = 'WizardStepSource'
    #INITIAL_STEP = 'WizardStepConsumption'

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
            # Can probably be fixed once we use another file to start from
            if 'WizardStep' in attr.__bases__[0].__name__:
                wiz.add_step(attr, initial)
    wiz.run()

