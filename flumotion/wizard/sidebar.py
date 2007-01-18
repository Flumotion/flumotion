# -*- Mode: Python -*-
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
# Streaming Server license may use this file in accordance with the
# Flumotion Advanced Streaming Server Commercial License Agreement.
# See "LICENSE.Flumotion" in the source distribution for more information.

# Headers in this file shall remain intact.


import gobject
import gtk

from flumotion.common import pygobject
from flumotion.common.pygobject import gsignal


__all__ = ['WizardSidebar']


class SidebarButton(gtk.Button):
    bg = None
    fg = None
    fgi = None
    pre_bg = None
    sensitive = False

    def __init__(self, name, padding=0):
        gtk.Button.__init__(self)
        self.set_name(name)
        a = gtk.Alignment(0.0, 0.5)
        a.set_property('left-padding', padding)
        a.show()
        self.label = gtk.Label()
        self.label.show()
        a.add(self.label)
        self.add(a)
        self.set_relief(gtk.RELIEF_NONE)
        self.set_property('can_focus', False) # why?
        self.connect_after('realize', SidebarButton.on_realize)
        self.set_sensitive(True)

    def on_realize(self):
        # have to get the style from the theme, but it's not really
        # there until we're realized
        style = self.get_style()

        self.bg = style.bg[gtk.STATE_SELECTED]
        self.fg = style.fg[gtk.STATE_SELECTED]
        self.fgi = style.light[gtk.STATE_SELECTED]
        self.pre_bg = style.bg[gtk.STATE_ACTIVE]

        self.set_sensitive(self.sensitive)
        self.modify_bg(gtk.STATE_NORMAL, self.bg)
        self.modify_bg(gtk.STATE_INSENSITIVE, self.bg)
        self.modify_bg(gtk.STATE_PRELIGHT, self.pre_bg)
        self.modify_bg(gtk.STATE_ACTIVE, self.pre_bg)
        self.label.modify_fg(gtk.STATE_NORMAL, self.fg)

    def set_sensitive(self, sensitive):
        self.sensitive = sensitive
        if not self.fgi:
            return

        def pc(c):
            return '#%02x%02x%02x' % (c.red>>8, c.green>>8, c.blue>>8)

        # CZECH THIS SHIT. You *can* set the fg/text on a label, but it
        # will still emboss the color in the INSENSITIVE state. The way
        # to avoid embossing is to use pango attributes (e.g. via
        # <span>), but then in INSENSITIVE you get stipple. Where is
        # this documented? Grumble.
        if sensitive:
            m = '<small>%s</small>' % self.name
        else:
            m = ('<small><span foreground="%s">%s</span></small>'
                 % (pc(self.fgi), self.name))
        self.label.set_markup(m)

        gtk.Button.set_sensitive(self, sensitive)
pygobject.type_register(SidebarButton)


class SidebarSection(gtk.VBox):
    title = None
    steps = None

    gsignal('step-chosen', str)

    def __init__(self, title, name):
        gtk.VBox.__init__(self)

        self.set_name(title)
        self.steps = []

        self.title = SidebarButton(title, 10)
        self.title.show()
        self.title.set_sensitive(False)
        self.pack_start(self.title, False, False)
        self.title.connect('clicked', lambda b: self.emit('step-chosen', name))

    def __repr__(self):
        return '<SidebarSection object %s>' % self.name

    def set_active(self, active):
        if active:
            for w in self.steps:
                w.show()
        else:
            for w in self.steps:
                w.hide()

    def push_header(self):
        assert not self.steps
        assert not self.title.sensitive
        self.title.set_sensitive(True)

    def pop_header(self):
        assert not self.steps
        assert self.title.sensitive
        self.title.set_sensitive(False)

    def push_step(self, step_name, step_title):
        assert self.title.sensitive

        def clicked_cb(b, name):
            self.emit('step-chosen', name)

        b = SidebarButton(step_title, 20)
        b.show()
        self.pack_start(b, False, False)

        self.steps.append(b)
        b.connect('clicked', clicked_cb, step_name)

    def pop_step(self):
        b = self.steps.pop()
        self.remove(b)
pygobject.type_register(SidebarSection)


class WizardSidebar(gtk.EventBox):
    gsignal('step-chosen', str)

    def __init__(self):
        gtk.EventBox.__init__(self)
        self.set_size_request(160, -1)
        self.vbox = gtk.VBox()
        self.vbox.set_border_width(5)
        self.vbox.show()
        self.add(self.vbox)
        self.active = -1
        self.top = -1
        self.sections = []
        self.connect_after('realize', WizardSidebar.on_realize)

    # private
    def on_realize(self):
        # have to get the style from the theme, but it's not really
        # there until we're realized
        style = self.get_style()
        self.modify_bg(gtk.STATE_NORMAL, style.bg[gtk.STATE_SELECTED])

    def set_active(self, i):
        if self.active >= 0:
            self.sections[self.active].set_active(False)
        self.active = i
        if self.active >= 0:
            self.sections[self.active].set_active(True)
        csp = self.vbox.child_set_property
        l = len(self.sections)
        for i in range(l):
            if i <= self.active:
                csp(self.sections[i], 'pack_type', gtk.PACK_START)
                self.vbox.reorder_child(self.sections[i], i)
            else:
                csp(self.sections[i], 'pack_type', gtk.PACK_END)
                self.vbox.reorder_child(self.sections[i], l - i)

    # public
    def set_sections(self, titles_and_names):
        for w in self.sections:
            self.vbox.remove(w)
            del w

        def clicked_cb(b, name):
            self.emit('step-chosen', name)

        self.sections = []
        self.active = self.top = -1

        for x in titles_and_names:
            w = SidebarSection(*x)
            w.connect('step-chosen', clicked_cb)
            w.show()
            w.set_active(False)
            self.vbox.pack_start(w, False, False)
            self.sections.append(w)

    def show_step(self, section_name, step_name):
        for i in range(len(self.sections)):
            if self.sections[i].name == section_name:
                self.set_active(i)
                return
        raise AssertionError()

    def push(self, section_name, step_name, step_title):
        if self.sections[self.active].name == section_name:
            # same section
            self.sections[self.active].push_step(step_name, step_title)
        else:
            # new section
            assert self.sections[self.active + 1].name == section_name
            self.set_active(self.active + 1)
            self.top += 1
            self.sections[self.active].push_header()
            
    def pop(self):
        if self.sections[self.top].steps:
            self.sections[self.top].pop_step()
        else:
            self.sections[self.top].pop_header()
            self.top -= 1
            if self.top < 0:
                return False
            if self.top < self.active:
                self.set_active(self.top)
        return True
pygobject.type_register(WizardSidebar)
