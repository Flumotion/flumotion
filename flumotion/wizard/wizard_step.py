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
from flumotion.utils.gstutils import gsignal

class MyComboBox(gtk.ComboBox):
    def get_text(self):
        iter = self.get_active_iter()
        model = self.get_model()
        return model.get(iter, 0)[0]
gobject.type_register(MyComboBox)

class WizardStep(gobject.GObject, log.Loggable):
    gsignal('sanity-changed', bool)

    step_name = None # Subclass sets this
    glade_file = None # Subclass sets this
    
    def __init__(self):
        self.__gobject_init__()
        self.widget = None
        self.load_glade()
        self._sane = False
        
    def load_glade(self):
        self.wtree = gtk.glade.XML(os.path.join(gladedir, self.glade_file),
                                   typedict=dict(GtkComboBox=MyComboBox))
        self.wtree.signal_autoconnect(self)
        
        windows = []
        for widget in self.wtree.get_widget_prefix(''):
            name = widget.get_name()
            if isinstance(widget, gtk.Window):
                widget.hide()
                windows.append(widget)
                continue
            
            if isinstance(widget, gtk.ComboBox):
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

    def set_sane(self, sane):
        self._sane = sane
        self.emit('sanity-changed', sane)
        
    def is_sane(self):
        return self._sane

    def get_state(self):
        "A subclass must implement this"
        raise NotImplementedError

    def next_step(self):
        "A subclass must implement this"
        raise NotImplementedError
        
gobject.type_register(WizardStep)

class WizardStepSource(WizardStep):
    step_name = 'Source'
    glade_file = 'wizard_source.glade'

    def on_checkbutton_video_toggled(self, button):
        self.combobox_video.set_sensitive(button.get_active())
        self.verify()
        
    def on_checkbutton_audio_toggled(self, button):
        self.combobox_audio.set_sensitive(button.get_active())
        self.verify()

    def verify(self):
        if (not self.checkbutton_audio.get_active() and not
            not self.checkbutton_video.get_active()):
            self.set_sane(False)
            return
        
        self.set_sane(True)

    def get_state(self):
        return dict(video_source=self.combobox_video.get_text(),
                    audio_source=self.combobox_audio.get_text(),
                    worker=self.combobox_workers.get_text())

    def get_next(self):
        if self.checkbutton_video.get_active():
            return 'Test Source'
        else:
            return 'Audio Source'
            
class WizardStepTestSource(WizardStep):
    step_name = 'Test Source'
    glade_file = 'wizard_testsource.glade'

    def get_next(self):
        return 'TV Card'
    
class WizardStepTVCard(WizardStep):
    step_name = 'TV Card'
    glade_file = 'wizard_tvcard.glade'

    def get_next(self):
        return 'Audio Source'

class WizardStepAudioSource(WizardStep):
    step_name = 'Audio Source'
    glade_file = 'wizard_audiosource.glade'

    def get_next(self):
        return

class Stack(list):
    push = list.append
    def peek(self):
        return self[-1]
    
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
        
    def add_step(self, step_class, initial=False):
        name = step_class.step_name
        assert not self.steps.has_key(name)
        self.steps[name] = step = step_class()

        if initial:
            self.stack.push(step)

    def set_step(self, step):
        # Remove previous step
        for child in self.content_area.get_children():
            self.content_area.remove(child)

        # Add current
        widget = step.get_main_widget()
        self.content_area.add(widget)

        self.label_title.set_text(step.step_name)
        
        # Finally show
        widget.show()

        self.current_step = step

    def on_wizard_delete_event(self, wizard, event):
        gtk.main_quit()

    def on_button_prev_clicked(self, button):
        self.stack.pop()
        prev_step = self.stack.peek()
        self.set_step(prev_step)

        self.update_buttons()
        
    def on_button_next_clicked(self, button):
        next = self.current_step.get_next()
        if not next:
            self.finish()
            return
        next_step = self.steps[next]
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

    def finish(self):
        print 'FINISHED'
        gtk.main_quit()
        
    def run(self):
        if not self.stack:
            raise TypeError, "need an initial step"
        
        self.set_step(self.stack.peek())
        
        self.window.show_all()
        gtk.main()
        
if __name__ == '__main__':
    wiz = Wizard()
    wiz.add_step(WizardStepSource, initial=True)
    wiz.add_step(WizardStepTestSource)
    wiz.add_step(WizardStepTVCard)
    wiz.add_step(WizardStepAudioSource)
    wiz.run()
