# -*- test-case-name: flumotion.test.test_greeter; fill-column: 80 -*-
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
#from flumotion.common import log

from flumotion.common.pygobject import gsignal


# This file implements a generic wizard framework.
#
# To conjure up a new wizard, call Wizard(NAME, FIRST_PAGE). NAME is the name of
# the wizard, for instance 'greeter'. FIRST_PAGE is the name of the first page
# that should be shown, for instance 'initial'.
#
# The pages of the wizard are found by putting together the names of the wizard
# and the page, e.g. greeter-initial.glade, and constructing the widget named
# 'page' from that file. 'page' must not be a toplevel window.
#
# When instantiated, the wizard will reference the module dict of the calling
# function. If there exists a class _in that module_ whose name begins with the
# page name and ends with '_handlers', for instance initial_handlers, the signal
# handlers defined in the glade file will be autoconnected to the handlers in
# that class.
# 
# When the user presses the "next" button, the wizard will call a function whose
# name begins with the page name and ends with '_cb', for instance initial_cb.
# The wizard searches for the function from within the dict described above.
# This function will be called with two arguments: the 'page' widget, and a
# dictionary provided to hold the cumulative state of the wizard. The function
# is expected to return the name of the next page, which might depend on what
# the user chooses in the current page. A return value of '*finished*' indicates
# that the wizard is finished.
#
# The wizard is run with the run() method. It returns the state object
# accumulated by the pages, or None if the user closes the wizard window.
#
# Example:
#
# def initial_cb(page, state):
#     state['foo'] = 'bar'
#     return '*finished*'
#
# w = Wizard('foo', 'initial')
# w.show()
# w.run() => {'foo': 'bar'}


class WizardStep:
    # all values filled in by subclasses
    name = None
    title = None
    on_next = None
    button_next = None
    # also, all widgets from the glade file will become attributes
    page = None # filled from glade

class Wizard(gobject.GObject):
    '''
    A generic wizard, constructed from state procedures and a set of
    corresponding glade files.
    '''

    name = None
    page = None
    page_stack = []
    pages = {}
    state = {}
    gsignal('finished')

    def __init__(self, name, initial_page, *pages):
        self.__gobject_init__()

        self.window = None
        self.page_bin = None
        for x in pages: self.pages[x.name] = x()
        self.create_ui()
        self.name = name
        self.set_page(initial_page)

    def create_ui(self):
        # called from __init__
        wtree = gtk.glade.XML(os.path.join(configure.gladedir,
                                           'admin-wizard.glade'))

        for widget in wtree.get_widget_prefix(''):
            # So we can access the step from inside the widget
            # widget.set_data('wizard-step', self)
            if isinstance(widget, gtk.Window):
                if widget.get_property('visible'):
                    raise AssertionError('window for %r is visible' % self)
            
            name = widget.get_name()
            if hasattr(self, name) and self.name:
                raise AssertionError(
                    "There is already an attribute called %s in %r" % (name,
                                                                       self))
            
            setattr(self, name, widget)

        iconfile = os.path.join(configure.imagedir, 'fluendo.png')
        self.window.set_icon_from_file(iconfile)
        self.image_icon.set_from_file(iconfile)

        title_bg = self.textview_text.get_style().bg[gtk.STATE_SELECTED]
        title_fg = self.textview_text.get_style().fg[gtk.STATE_SELECTED]
        self.eventbox_top.modify_bg(gtk.STATE_NORMAL, title_bg)
        self.label_title.modify_fg(gtk.STATE_NORMAL, title_fg)
        normal_bg = self.textview_text.get_style().bg[gtk.STATE_NORMAL]
        self.textview_text.modify_base(gtk.STATE_NORMAL, normal_bg)

        wtree.signal_autoconnect(self)

    def set_page(self, name):
        try:
            page = self.pages[name]
        except KeyError:
            raise AssertionError ('No page named %s in %r' % (name, self.pages))

        if not page['page']:
            wtree = gtk.glade.XML(os.path.join(configure.gladedir,
                                               self.name+'-'+name+'.glade'),
                                  'page')
            for widget in wtree.get_widget_prefix(''):
                wname = widget.get_name()
                if hasattr(page, wname) and page[wname]:
                    raise AssertionError (
                        "There is already an attribute called %s in %r" %
                        (wname, page))
                setattr(page, wname, widget)
                wtree.signal_autoconnect(page)

        page.button_next = self.button_next
            
        self.page = page
        for w in self.page_bin.get_children():
            self.page_bin.remove(w)
        self.page_bin.add(page.page)
        self.label_title.set_markup('<big><b>%s</b></big>' % page.title)
        self.textview_text.get_buffer().set_text(page.text)
        if hasattr(page, 'setup'):
            page.setup(self.state)

    def on_delete_event(self, *window):
        self.state = None
        gtk.main_quit()

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

    def run(self):
        def on_finished(self):
            gtk.main_quit()
        self.connect('finished', on_finished)
        gtk.main()
        return self.state

gobject.type_register(Wizard)
