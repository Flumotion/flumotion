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

from flumotion.common.pygobject import gsignal

__all__ = ['WizardSidebar']
__version__ = "$Rev$"


class SidebarButton(gtk.Button):

    def __init__(self, name, padding=0):
        self.bg = None
        self.fg = None
        self.fgi = None
        self.pre_bg = None
        self.sensitive = False

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
gobject.type_register(SidebarButton)


class SidebarSection(gtk.VBox):
    gsignal('step-chosen', str)

    def __init__(self, title, name):
        gtk.VBox.__init__(self)

        self.set_name(title)
        self.buttons = []

        self.title = SidebarButton(title, 10)
        self.title.show()
        self.title.set_sensitive(False)
        self.pack_start(self.title, False, False)
        self.title.connect('clicked', lambda b: self.emit('step-chosen', name))

    def __repr__(self):
        return '<SidebarSection object %s>' % self.name

    def set_active(self, active):
        if active:
            for button in self.buttons:
                button.show()
        else:
            for button in self.buttons:
                button.hide()

    def push_header(self):
        assert not self.buttons
        assert not self.title.sensitive
        self.title.set_sensitive(True)

    def pop_header(self):
        assert not self.buttons
        assert self.title.sensitive
        self.title.set_sensitive(False)

    def push_step(self, step_name, step_title):
        assert self.title.sensitive

        def clicked_cb(b, name):
            self.emit('step-chosen', name)

        button = SidebarButton(step_title, 20)
        button.connect('clicked', clicked_cb, step_name)
        self.pack_start(button, False, False)
        button.show()
        self.buttons.append(button)

    def pop_step(self):
        b = self.buttons.pop()
        self.remove(b)
gobject.type_register(SidebarSection)


class WizardSidebar(gtk.EventBox):
    gsignal('step-chosen', str)

    def __init__(self):
        gtk.EventBox.__init__(self)
        self._active = -1
        self._top = -1
        self._sections = []

        self.set_size_request(160, -1)
        self.vbox = gtk.VBox()
        self.vbox.set_border_width(5)
        self.vbox.show()
        self.add(self.vbox)
        self.connect_after('realize', self.after_realize)

    # Public API

    def set_sections(self, titles_and_names):
        for w in self._sections:
            self.vbox.remove(w)
            del w

        def clicked_cb(b, name):
            self.emit('step-chosen', name)

        sections = []
        self._active = self._top = -1

        for title, name in titles_and_names:
            w = SidebarSection(title, name)
            w.connect('step-chosen', clicked_cb)
            w.show()
            w.set_active(False)
            self.vbox.pack_start(w, False, False)
            sections.append(w)
        self._sections = sections

    def show_step(self, section_name):
        for i, section in enumerate(self._sections):
            if section.name == section_name:
                self._set_active(i)
                return
        raise AssertionError()

    def push(self, section_name, step_name, step_title):
        active_section = self._sections[self._active]
        if active_section.name == section_name:
            # same section
            active_section.push_step(step_name, step_title)
        else:
            # new section
            assert self._sections[self._active + 1].name == section_name
            self._set_active(self._active + 1)
            self._top += 1
            self._sections[self._active].push_header()

    def pop(self):
        top_section = self._sections[self._top]
        if top_section.buttons:
            top_section.pop_step()
        else:
            top_section.pop_header()
            self._top -= 1
            if self._top < 0:
                return False
            if self._top < self._active:
                self._set_active(self._top)
        return True

    # Private

    def _set_active(self, i):
        if self._active >= 0:
            self._sections[self._active].set_active(False)
        self._active = i
        if self._active >= 0:
            self._sections[self._active].set_active(True)

        l = len(self._sections)
        for i, section in enumerate(self._sections):
            if i <= self._active:
                pos = i
                pack_type = gtk.PACK_START
            else:
                pos = l - i
                pack_type = gtk.PACK_END
            self.vbox.child_set_property(section, 'pack_type', pack_type)
            self.vbox.reorder_child(section, pos)

    # Callbacks

    def after_realize(self, eventbox):
        # have to get the style from the theme, but it's not really
        # there until we're realized
        style = self.get_style()
        self.modify_bg(gtk.STATE_NORMAL, style.bg[gtk.STATE_SELECTED])

gobject.type_register(WizardSidebar)
