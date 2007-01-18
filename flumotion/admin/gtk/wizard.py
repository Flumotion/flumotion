# -*- Mode: Python; test-case-name: flumotion.test.test_greeter -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# Flumotion - a streaming media server
# Copyright (C) 2004,2005,2006,2007 Fluendo, S.L. (www.fluendo.com).
# All rights reserved.

# This file may be distributed and/or modified under the terms of
# the GNU General Public License version 2 as published by
# the Free Software Foundation.
# This file is distributed without any warranty; without even the implied
# warranty of merchantability or fitness for a particular purpose.
# See "LICENSE.GPL" in the source distribution for more information.

# Licensees having purchased or holding a valid Flumotion Advanced
# Streaming Server license may use this file in accordance with th
# Flumotion Advanced Streaming Server Commercial License Agreement.
# See "LICENSE.Flumotion" in the source distribution for more information.

# Headers in this file shall remain intact.


import os

import sys

import gobject
import gtk
import gtk.glade

from flumotion.configure import configure

from flumotion.common import pygobject
from flumotion.common.pygobject import gsignal
from flumotion.ui.glade import GladeWidget, GladeWindow


# This file implements a generic wizard framework suitable for processes with
# few steps. Processes with 5 or more steps should use something more like the
# wizard in flumotion.wizard, because it has a history-sensitive navigation bar
# as well. For simple processes, this wizard is sufficient.
#
# You will first have to define the steps in your wizard. They are defined by
# subclassing WizardStep. You define the required class variables, the on_next
# method, and optionally the other methods documented in then WizardStep class.
#
# class FirstStep(WizardStep):
#     name = 'first-step'
#     title = 'First step'
#     text = 'Please fill in your bank details below.'
#     next_pages = ['second-step']
#
#     def on_next(self, state):
#         state['bank-account'], self.bank_account_entry.get_text()
#         return '*finished*'
#
# The on_next method is expected to save any relevant information to the state
# object (a dict) and return the name of the next step, or '*finished*' if this
# is the last step.
#
# Besides control flow, the name of the step is also used to load up a glade
# file describing the step's contents. The wizard will look for it as
# WNAME-SNAME.glade, where WNAME is the name of the wizard and SNAME is the name
# of the step. The widget taken will be the direct child of the first toplevel
# window. Each widget in the glade file will be set as an attribute on the
# WizardStep, e.g. bank_account_entry in the example above.
#
# The "text" is shown above the widget created from the glade file. next_pages
# is a list of possible next steps. Before the widget is shown, the is_available
# method will be called on the steps listed in next_pages, and the names of
# those steps that are actually available will be put in the available_pages
# attribute on the current step. This is useful to allow early steps to show
# if a later step is not available, perhaps by desensitizing an option.
#
# Methods other than on_next and is_available are documented in the WizardStep
# class.
#
# To conjure up a new wizard, call Wizard(NAME, FIRST_PAGE_NAME, STEP1,
# STEP2...). NAME is the name of the wizard, for instance 'greeter'. FIRST_PAGE
# is the name of the first page that should be shown, for instance 'first-step'
# in the example above. STEP1... are the WizardStep specialized classes (not
# instances).
#
# The wizard is run with the run() method. It returns the state object
# accumulated by the pages, or None if the user closes the wizard window.
#
# w = Wizard('foo', 'first-step', FirstStep)
# w.show()
# w.run() => {'bank-account': 'foo'}


# fixme: doc vmethods
class WizardStep(GladeWidget):
    # all values filled in by subclasses
    name = None
    title = None
    on_next = None
    button_next = None
    next_pages = None
    # also, all widgets from the glade file will become attributes
    page = None # filled from glade

    def __init__(self, glade_prefix=''):
        self.glade_file = glade_prefix + self.name + '.glade'
        GladeWidget.__init__(self)

    def is_available(self):
        return True

    def setup(self, state, available_pages):
        # vmethod
        pass

class Wizard(GladeWindow):
    '''
    A generic wizard.
    '''

    # should by filled by subclasses
    name = None
    steps = []

    # private
    glade_file = 'admin-wizard.glade'
    page = None
    page_stack = []
    pages = {}
    state = {}

    gsignal('finished')

    def __init__(self, initial_page):
        GladeWindow.__init__(self)

        # these should be filled by subclasses
        assert self.name
        assert self.steps

        for x in self.steps:
            p = self.pages[x.name] = x(self.name+'-')
            p.show()

        self.loop = gobject.MainLoop()
        self._setup_ui()
        self.set_page(initial_page)

    def _setup_ui(self):
        w = self.widgets

        iconfile = os.path.join(configure.imagedir, 'fluendo.png')
        self.window.set_icon_from_file(iconfile)
        w['image_icon'].set_from_file(iconfile)

        # have to get the style from the theme, but it's not really there until
        # it's realized
        w['label_title'].realize()
        style = w['label_title'].get_style()

        title_bg = style.bg[gtk.STATE_SELECTED]
        title_fg = style.fg[gtk.STATE_SELECTED]
        w['eventbox_top'].modify_bg(gtk.STATE_NORMAL, title_bg)
        w['eventbox_top'].modify_bg(gtk.STATE_INSENSITIVE, title_bg)
        w['label_title'].modify_fg(gtk.STATE_NORMAL, title_fg)
        w['label_title'].modify_fg(gtk.STATE_INSENSITIVE, title_fg)
        normal_bg = style.bg[gtk.STATE_NORMAL]
        w['textview_text'].modify_base(gtk.STATE_INSENSITIVE, normal_bg)
        w['textview_text'].modify_bg(gtk.STATE_INSENSITIVE, normal_bg)
        w['eventbox_content'].modify_base(gtk.STATE_INSENSITIVE, normal_bg)
        w['eventbox_content'].modify_bg(gtk.STATE_INSENSITIVE, normal_bg)

    def set_page(self, name):
        try:
            page = self.pages[name]
        except KeyError:
            raise AssertionError ('No page named %s in %r' % (name, self.pages))

        w = self.widgets
        page.button_next = w['button_next']
            
        available_pages = [p for p in page.next_pages
                                if self.pages[p].is_available()]

        w['button_prev'].set_sensitive(bool(self.page_stack))

        self.page = page
        for x in w['page_bin'].get_children():
            w['page_bin'].remove(x)
        w['page_bin'].add(page)
        w['label_title'].set_markup('<big><b>%s</b></big>' % page.title)
        w['textview_text'].get_buffer().set_text(page.text)
        w['button_next'].set_sensitive(True)
        page.setup(self.state, available_pages)

    def on_delete_event(self, *window):
        self.state = None
        self.loop.quit()

    def on_next(self, *button):
        next_page = self.page.on_next(self.state)
        
        if not next_page:
            # the input is incorrect
            pass
        elif next_page == '*finished*':
            self.emit('finished')
        else:
            self.page_stack.append(self.page)
            self.set_page(next_page)
        
    def on_prev(self, button):
        self.set_page(self.page_stack.pop().name)

    def show(self):
        self.window.show()

    def destroy(self):
        assert hasattr(self, 'window')
        self.window.destroy()
        del self.window

    def set_sensitive(self, is_sensitive):
        self.window.set_sensitive(is_sensitive)

    def run(self):
        assert self.window
        self.set_sensitive(True)
        self.show()
        def finished(x):
            self.disconnect(i)
            self.loop.quit()
        i = self.connect('finished', finished)
        self.loop.run()
        return self.state

pygobject.type_register(Wizard)
