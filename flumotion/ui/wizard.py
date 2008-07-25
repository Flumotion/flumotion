# -*- Mode: Python; test-case-name: flumotion.test.test_wizard -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# Flumotion - a streaming media server
# Copyright (C) 2004,2005,2006,2007,2008 Fluendo, S.L. (www.fluendo.com).
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

import gettext
import os
import types

import gobject
import gtk
from twisted.internet.defer import Deferred

from flumotion.configure import configure
from flumotion.common import log, messages
from flumotion.common.i18n import gettexter
from flumotion.common.pygobject import gsignal
from flumotion.ui.fgtk import ProxyWidgetMapping
from flumotion.ui.glade import GladeWidget, GladeWindow

__version__ = "$Rev$"
__pychecker__ = 'no-classattr no-argsused'
T_ = gettexter()
_ = gettext.gettext

# pychecker doesn't like the auto-generated widget attrs
# or the extra args we name in callbacks

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

    def skipTo(self, key):
        for i, item in enumerate(self.l):
            if key(item):
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
    gladeTypedict = ProxyWidgetMapping()

    # set by subclasses
    name = None
    title = None
    section = None
    icon = 'placeholder.png'

    # optional
    sidebarName = None

    def __init__(self, wizard):
        """
        @param wizard: the wizard this step is a part of
        @type  wizard: L{SectionWizard}
        """
        self.visited = False
        self.wizard = wizard

        GladeWidget.__init__(self)
        self.set_name(self.name)
        if not self.sidebarName:
            self.sidebarName = self.title
        self.setup()

    def __repr__(self):
        return '<WizardStep object %r>' % self.name

    # Required vmethods

    def getNext(self):
        """Called when the user presses next in the wizard.
        @returns: name of next step
        @rtype: L{WizardStep} instance, deferred or None.
          The deferred must return a WizardStep instance.
          None means that the next section should be fetched or if there are
          no more sections, to finish the wizard.
        """
        raise NotImplementedError

    # Optional vmethods

    def setup(self):
        """This is called after the step is constructed, to be able to
        do some initalization time logic in the steps."""

    def activated(self):
        """Called just before the step is shown, so the step can
        do some logic, eg setup the default state"""


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
        # FIXME: This breaks when calling sidebar.remove_section(),
        #        remove_section will have to update self._active or
        #        preferably just rewrite the whole BEEP thing
        #assert self.title.sensitive
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


class WizardSidebar(gtk.EventBox, log.Loggable):
    gsignal('step-chosen', str)

    logCategory = 'wizard'

    def __init__(self, wizard):
        # FIXME: Remove this reference
        self._wizard = wizard

        # FIXME: Join these three into one
        self._sections = []
        self._sections2 = []
        self._sectionsByName = {}

        self._active = -1
        self._currentSection = 0
        self._currentStep = None
        self._stack = _WalkableStack()
        self._steps = {}
        self._top = -1

        gtk.EventBox.__init__(self)
        self.connect_after('realize', self.after_realize)
        self.set_size_request(160, -1)

        self.vbox = gtk.VBox()
        self.vbox.set_border_width(5)
        self.vbox.show()
        self.add(self.vbox)

    # Public API

    def appendSection(self, title, name):
        """Adds a new section to the sidebar
        @param title: title of the section
        @param name: name of the section
        """
        def clicked_cb(b, name):
            self.emit('step-chosen', name)

        section = SidebarSection(title, name)
        section.connect('step-chosen', clicked_cb)
        section.show()
        section.set_active(False)
        self.vbox.pack_start(section, False, False)
        self._sections.append(section)
        self._sectionsByName[name] = section

    def removeSection(self, name):
        """Removes a section by name
        @param name: name of the section
        """
        section = self._sectionsByName.pop(name)
        self._sections.remove(section)
        self.vbox.remove(section)

    def jumpTo(self, section_name):
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
            if self._sections[self._active + 1].name != section_name:
                raise AssertionError(
                    "Expected next section to be %r, but is %r" % (
                    section_name, self._sections[self._active + 1].name))

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

    def cleanFutureSteps(self):
        oldSections = self._sections2[self._currentSection+1:][:]
        for i, oldSection in enumerate(oldSections):
            self.removeSection(oldSection.title)
            self._sections2.remove(oldSection)

    def addStepSection(self, section):
        self.appendSection(section.section, section.title)
        self._sections2.append(section)

    def getStep(self, stepname):
        for step in self._steps.values():
            if step.get_name() == stepname:
                return step
        else:
            raise KeyError(stepname)

    def hasStep(self, stepName):
        for step in self._steps.values():
            if step.get_name() == stepName:
                return True
        return False

    def getVisitedSteps(self):
        for step in self._steps.values():
            if step.visited:
                yield step

    def pushSteps(self):
        sectionClass = self._sections2[self._currentSection]
        if isinstance(sectionClass, (type, types.ClassType)):
            section = sectionClass(self._wizard)
        else:
            section = sectionClass

        self.push(section.section, None, section.section)
        self._stack.push(section)
        self._setStep(section)

    def canGoBack(self):
        return self._stack.pos != 0

    def prepareNextStep(self, step):
        if hasattr(step, 'lastStep'):
            self._wizard.finish(completed=True)
            return

        next = step.getNext()
        if isinstance(next, WizardStep):
            nextStep = next
        elif isinstance(next, Deferred):
            d = next
            def getStep(step):
                if step is None:
                    step = self._getNextStep()
                if step is None:
                    return
                self._showNextStep(step)
            d.addCallback(getStep)
            return
        elif next is None:
            nextStep = self._getNextStep()
            if nextStep is None:
                return
        else:
            raise AssertionError(next)

        self._showNextStep(nextStep)

    def jumpToStep(self, name):
        # If we're jumping to the same step don't do anything to
        # avoid unnecessary ui flashes
        if self.getStep(name) == self._currentStep:
            return
        self._stack.skipTo(lambda x: x.name == name)
        step = self._stack.current()
        self.sidebar.jumpTo(step.section)
        self._currentSection = self._getSectionByName(step.section)
        self._setStep(step)

    def showPreviousStep(self):
        step = self._stack.back()
        self._currentSection = self._getSectionByName(step.section)
        self._setStep(step)
        self._wizard.updateButtons(hasNext=True)
        self.jumpTo(step.section)
        hasNext = not hasattr(step, 'lastStep')
        self._wizard.updateButtons(hasNext)

    def getCurrentStep(self):
        return self._currentStep

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

    def _showNextStep(self, step):
        while not self._stack.push(step):
            s = self._stack.pop()
            s.visited = False
            self.pop()

        hasNext = not hasattr(step, 'lastStep')
        if not step.visited and hasNext:
            self.push(step.section,
                      step.title,
                      step.sidebarName)
        else:
            self.jumpTo(step.section)

        step.visited = True
        self._setStep(step)

        self._wizard.updateButtons(hasNext)

    def _setStep(self, step):
        self._steps[step.name] = step
        self._currentStep = step

        self._wizard.blockNext(False)
        self._wizard.packStep(step)

        self._wizard.beforeShowStep(step)

        self.debug('showing step %r' % step)
        step.show()
        step.activated()

    def _getSectionByName(self, section_name):
        for sectionClass in self._sections2:
            if sectionClass.section == section_name:
                return self._sections2.index(sectionClass)

    def _getNextStep(self):
        if self._currentSection + 1 == len(self._sections2):
            self._wizard.finish(completed=True)
            return

        self._currentSection += 1
        nextStepClass = self._sections2[self._currentSection]
        return nextStepClass(self._wizard)

    # Callbacks

    def after_realize(self, eventbox):
        # have to get the style from the theme, but it's not really
        # there until we're realized
        style = self.get_style()
        self.modify_bg(gtk.STATE_NORMAL, style.bg[gtk.STATE_SELECTED])

gobject.type_register(WizardSidebar)


class SectionWizard(GladeWindow, log.Loggable):
    gsignal('destroy')

    logCategory = 'wizard'

    gladeFile = 'sectionwizard.glade'

    def __init__(self, parent_window=None):
        self._useMain = True

        GladeWindow.__init__(self, parent_window)
        for k, v in self.widgets.items():
            setattr(self, k, v)
        self.window.set_icon_from_file(os.path.join(configure.imagedir,
                                                    'fluendo.png'))
        self.window.connect_after('realize', self.on_window_realize)
        self.window.connect('destroy', self.on_window_destroy)

        self.sidebar = WizardSidebar(self)
        self.sidebar.connect('step-chosen', self.on_sidebar_step_chosen)
        self.sidebar.set_size_request(160, -1)
        self.hbox_main.pack_start(self.sidebar, False, False)
        self.hbox_main.reorder_child(self.sidebar, 0)
        self.sidebar.show()

    def __nonzero__(self):
        return True

    def __len__(self):
        return len(self._steps)

    # Override this in subclass

    def completed(self):
        pass

    def beforeShowStep(self, step):
        pass

    # Public API

    def cleanFutureSteps(self):
        """Removes all the steps in front of the current one"""
        self.sidebar.cleanFutureSteps()

    def addStepSection(self, section):
        """Adds a new step section
        @param section: section to add
        @type section: a WizardStep subclass
        """
        self.sidebar.addStepSection(section)

    def getStep(self, stepname):
        """Fetches a step. KeyError is raised when the step is not found.
        @param stepname: name of the step to fetch
        @type stepname: str
        @returns: a L{WizardStep} instance or raises KeyError
        """
        return self.sidebar.getStep(stepname)

    def hasStep(self, stepName):
        """Find out if a step with name stepName exists
        @returns: if the stepName exists
        """
        return self.sidebar.hasStep(stepName)

    def getVisitedSteps(self):
        """Returns a sequence of steps which has been visited.
        Visited means that the state of the step should be considered
        when finishing the wizard.
        @returns: sequence of visited steps.
        @rtype: sequence of L{WizardStep}
        """
        return self.sidebar.getVisitedSteps()

    def getCurrentStep(self):
        return self.sidebar.getCurrentStep()

    def hide(self):
        self.window.hide()

    def clear_msg(self, id):
        self.message_area.clearMessage(id)

    def add_msg(self, msg):
        self.message_area.addMessage(msg)

    def goNext(self):
        """Show the next step, this is called when
        the next button is clicked
        """
        self.sidebar.prepareNextStep(self.sidebar.getCurrentStep())

    def blockNext(self, block):
        self.button_next.set_sensitive(not block)
        # work around a gtk+ bug #56070
        if not block:
            self.button_next.hide()
            self.button_next.show()

    def run(self, main=True):
        self._useMain = main
        self.sidebar.pushSteps()

        self.window.present()
        self.window.grab_focus()

        if self._useMain:
            try:
                gtk.main()
            except KeyboardInterrupt:
                pass

    def packStep(self, step):
        # Remove previous step
        map(self.content_area.remove, self.content_area.get_children())
        self.message_area.clear()

        # Add current
        self.content_area.pack_start(step, True, True, 0)
        self._setStepIcon(step.icon)
        self._setStepTitle(step.title)
        self.updateButtons(hasNext=True)

    def finish(self, main=True, completed=True):
        if completed:
            self.completed()

        if self._useMain:
            try:
                gtk.main_quit()
            except RuntimeError:
                pass

    def updateButtons(self, hasNext):
        # update the forward and next buttons
        # hasNext: whether or not there is a next step
        canGoBack = self.sidebar.canGoBack()
        self.button_prev.set_sensitive(canGoBack)

        # XXX: Use the current step, not the one on the top of the stack
        if hasNext:
            self.button_next.set_label(gtk.STOCK_GO_FORWARD)
        else:
            self.button_next.set_label(_('_Finish'))

    # Private

    def _setStepIcon(self, icon):
        icon_filename = os.path.join(configure.imagedir, 'wizard', icon)
        assert os.path.exists(icon_filename)
        self.image_icon.set_from_file(icon_filename)

    def _setStepTitle(self, title):
        self.label_title.set_markup(
            '<span size="x-large">%s</span>' % escape(title or ''))

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
        self.finish(self._useMain, completed=False)

    def on_button_prev_clicked(self, button):
        self.sidebar.showPreviousStep()

    def on_button_next_clicked(self, button):
        self.goNext()

    def on_sidebar_step_chosen(self, sidebar, name):
        self.sidebar.jumpToStep(name)


gobject.type_register(SectionWizard)
