# -*- Mode: Python; test-case-name: flumotion.test.test_wizard -*-
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


import os

import gtk
import gtk.gdk
import gtk.glade
from kiwi.interfaces import IProxyWidget

from flumotion.configure import configure
from flumotion.common import log, pygobject, messages
from flumotion.common.pygobject import gsignal
from flumotion.ui.fgtk import ProxyWidgetMapping
from flumotion.ui.glade import GladeWidget, GladeWindow

T_ = messages.gettexter('flumotion')

# pychecker doesn't like the auto-generated widget attrs
# or the extra args we name in callbacks
__pychecker__ = 'no-classattr no-argsused'

def escape(text):
    return text.replace('&', '&amp;')


class _WalkableStack(object):
    def __init__(self):
        self.l = []
        self.height = -1
        self.pos = -1

    def __repr__(self):
        return '<stack %r>' % self.l

    def __len__(self):
        return len(self.l)

    def push(self, x):
        if self.pos == self.height:
            self.height += 1
            self.pos += 1
            self.l.append(x)
            return True
        elif x == self.l[self.pos + 1]:
            self.pos += 1
            return True
        else:
            return False

    def current(self):
        return self.l[self.pos]

    def skip_to(self, key):
        for i in range(0, len(self.l)):
            if key(self.l[i]):
                self.pos = i
                return
        raise AssertionError()

    def back(self):
        assert self.pos > 0
        self.pos -= 1
        return self.l[self.pos]

    def pop(self):
        self.height -= 1
        if self.height < self.pos:
            self.pos = self.height
        return self.l.pop()


class WizardStep(GladeWidget, log.Loggable):
    glade_typedict = ProxyWidgetMapping()

    # set by subclasses
    name = None
    section = None
    icon = 'placeholder.png'

    # optional
    sidebar_name = None

    def __init__(self, wizard):
        """
        @param wizard: the wizard this step is a part of
        @type  wizard: L{Wizard}
        """
        self.visited = False
        self.wizard = wizard

        GladeWidget.__init__(self)
        self.set_name(self.name)
        if not self.sidebar_name:
            self.sidebar_name = self.name
        self.setup()

    def __repr__(self):
        return '<WizardStep object %r>' % self.name

    # Public API

    def get_state(self):
        state = {}
        for name, widget in self.widgets.items():
            if not IProxyWidget.providedBy(widget):
                continue
            name = name.replace('_', '-')
            state[name] = widget.read()
        return state

    # Required vmethods

    def get_next(self):
        """Called when the user presses next in the wizard.
        @returns: name of next step or next_step instance
        @rtype:  string or an L{WizardStep} instance
        """
        raise NotImplementedError

    # Optional vmethods
    def setup(self):
        """This is called after the step is constructed, to be able to
        do some initalization time logic in the steps."""

    def activated(self):
        """Called just before the step is shown, so the step can
        do some logic, eg setup the default state"""

    def before_show(self):
        """This is called just before we show the widget, everything
        is created and in place"""


class SectionWizard(GladeWindow, log.Loggable):
    gsignal('destroy')

    logCategory = 'wizard'

    flowName = 'default'

    glade_file = 'wizard.glade'

    sections = None

    def __init__(self, parent_window=None):
        if self.sections is None:
            raise TypeError("%r needs to have a class attribute called %r" % (
                    self, 'sections'))

        self._steps = {}
        self._current_section = 0
        self._stack = _WalkableStack()
        self._current_step = None
        self._use_main = True

        GladeWindow.__init__(self, parent_window)
        for k, v in self.widgets.items():
            setattr(self, k, v)
        self.window.set_icon_from_file(os.path.join(configure.imagedir,
                                                    'fluendo.png'))
        self.window.connect_after('realize', self.on_window_realize)
        self.window.connect('destroy', self.on_window_destroy)

        self.sidebar.set_sections([(x.section, x.name) for x in self.sections])
        self.sidebar.connect('step-chosen', self.on_sidebar_step_chosen)

        self._current_step = self.get_first_step()

    def __len__(self):
        return len(self._steps)

    # Override this in subclass
    def get_first_step(self):
        raise NotImplementedError

    def completed(self):
        pass

    # Public API

    def get_step(self, stepname):
        """Fetches a step. KeyError is raised when the step is not found.
        @param stepname: name of the step to fetch
        @type stepname: str
        @returns: a L{WizardStep} instance or raises KeyError
        """
        for step in self._steps.values():
            if step.get_name() == stepname:
                return step
        else:
            raise KeyError(stepname)

    def get_step_option(self, stepname, option):
        state = self.get_step_options(stepname)
        return state[option]

    def get_step_options(self, stepname):
        step = self.get_step(stepname)
        return step.get_state()

    def hide(self):
        self.window.hide()

    def clear_msg(self, id):
        self.message_area.clear_message(id)

    def add_msg(self, msg):
        self.message_area.add_message(msg)

    def block_next(self, block):
        self.button_next.set_sensitive(not block)
        # work around a gtk+ bug #56070
        if not block:
            self.button_next.hide()
            self.button_next.show()

    def run(self, interactive, main=True):
        self._use_main = main
        section_class = self.sections[self._current_section]
        section = section_class(self)
        self.sidebar.push(section.section, None, section.section)
        self._stack.push(section)
        self._set_step(section)

        if not interactive:
            while self.show_next():
                pass
            return self._finish(False)

        self.window.present()
        self.window.grab_focus()

        if not self._use_main:
            return

        try:
            gtk.main()
        except KeyboardInterrupt:
            pass

    def show_next_step(self, step):
        next = step.get_next()
        if isinstance(next, WizardStep):
            next_step = next
        elif next is None:
            if self._current_section + 1 == len(self.sections):
                self._finish(completed=True)
                return
            self._current_section += 1
            next_step_class = self.sections[self._current_section]
            next_step = next_step_class(self)
        else:
            raise AssertionError(next)

        self._steps[next_step.name] = next_step

        while not self._stack.push(next_step):
            s = self._stack.pop()
            s.visited = False
            self.sidebar.pop()

        if not next_step.visited:
            self.sidebar.push(next_step.section, next_step.name,
                              next_step.sidebar_name)
        else:
            self.sidebar.show_step(next_step.section)

        next_step.visited = True
        self._set_step(next_step)

        has_next = not hasattr(next_step, 'last_step')
        self._update_buttons(has_next)

    # Private

    def _update_buttons(self, has_next):
        # update the forward and next buttons
        # has_next: whether or not there is a next step
        can_go_back = self._stack.pos != 0
        self.button_prev.set_sensitive(can_go_back)

        # XXX: Use the current step, not the one on the top of the stack
        if has_next:
            self.button_next.set_label(gtk.STOCK_GO_FORWARD)
        else:
            # use APPLY, just like in gnomemeeting
            self.button_next.set_label(gtk.STOCK_APPLY)

    def _set_step_icon(self, icon):
        icon_filename = os.path.join(configure.imagedir, 'wizard', icon)
        assert os.path.exists(icon_filename)
        self.image_icon.set_from_file(icon_filename)

    def _set_step_title(self, title):
        self.label_title.set_markup(
            '<span size="x-large">%s</span>' % escape(title))

    def _pack_step(self, step):
        # Remove previous step
        map(self.content_area.remove, self.content_area.get_children())
        self.message_area.clear()

        # Add current
        self.content_area.pack_start(step, True, True, 0)

    def _finish(self, main=True, completed=True):
        if completed:
            self.completed()

        if self._use_main:
            try:
                gtk.main_quit()
            except RuntimeError:
                pass

    def _set_step(self, step):
        self._pack_step(step)
        self._set_step_icon(step.icon)
        self._set_step_title(step.name)

        self._update_buttons(has_next=True)
        self.block_next(False)

        self.before_show_step(step)

        step.before_show()

        self.debug('showing step %r' % step)
        step.show()
        step.activated()

        self._current_step = step

    def _jump_to_step(self, name):
        self._stack.skip_to(lambda x: x.name == name)
        step = self._stack.current()
        self.sidebar.show_step(step.section)
        self._current_section = self._get_section_by_name(step.section)
        self._set_step(step)

    def _show_next_step(self):
        self.show_next_step(self._current_step)

    def _show_previous_step(self):
        step = self._stack.back()
        self._current_section = self._get_section_by_name(step.section)
        self._set_step(step)
        self._update_buttons(has_next=True)
        self.sidebar.show_step(step.section)
        has_next = not hasattr(step, 'last_step')
        self._update_buttons(has_next)

    def _get_section_by_name(self, section_name):
        for section_class in self.sections:
            if section_class.section == section_name:
                return self.sections.index(section_class)

    # Callbacks

    def on_window_realize(self, window):
        # have to get the style from the theme, but it's not really
        # there until it's attached
        style = self.eventbox_top.get_style()
        bg = style.bg[gtk.STATE_SELECTED]
        fg = style.fg[gtk.STATE_SELECTED]
        self.eventbox_top.modify_bg(gtk.STATE_NORMAL, bg)
        self.hbuttonbox2.modify_bg(gtk.STATE_NORMAL, bg)
        self.label_title.modify_fg(gtk.STATE_NORMAL, fg)

    def on_window_destroy(self, window):
        self.emit('destroy')

    def on_window_delete_event(self, wizard, event):
        self._finish(self._use_main, completed=False)

    def on_button_prev_clicked(self, button):
        self._show_previous_step()

    def on_button_next_clicked(self, button):
        self._show_next_step()

    def on_sidebar_step_chosen(self, sidebar, name):
        self._jump_to_step(name)


pygobject.type_register(SectionWizard)
