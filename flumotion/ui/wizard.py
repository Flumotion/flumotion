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


class SectionWizard(GladeWindow, log.Loggable):
    gsignal('destroy')

    logCategory = 'wizard'

    gladeFile = 'sectionwizard.glade'

    def __init__(self, parent_window=None):
        self._steps = {}
        self._sections = []
        self._currentSection = 0
        self._stack = _WalkableStack()
        self._currentStep = None
        self._useMain = True

        GladeWindow.__init__(self, parent_window)
        for k, v in self.widgets.items():
            setattr(self, k, v)
        self.window.set_icon_from_file(os.path.join(configure.imagedir,
                                                    'fluendo.png'))
        self.window.connect_after('realize', self.on_window_realize)
        self.window.connect('destroy', self.on_window_destroy)

        self.sidebar.connect('step-chosen', self.on_sidebar_step_chosen)

    def __nonzero__(self):
        return True

    def __len__(self):
        return len(self._steps)

    # Override this in subclass

    def completed(self):
        pass

    # Public API

    def cleanFutureSteps(self):
        """Removes all the steps in front of the current one"""
        oldSections = self._sections[self._currentSection+1:][:]
        for i, oldSection in enumerate(oldSections):
            self.sidebar.remove_section(oldSection.title)
            self._sections.remove(oldSection)

    def addStepSection(self, section):
        """Adds a new step section
        @param section: section to add
        @type section: a WizardStep subclass
        """
        self.sidebar.append_section(section.section, section.title)
        self._sections.append(section)

    def getStep(self, stepname):
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

    def hasStep(self, stepName):
        """Find out if a step with name stepName exists
        @returns: if the stepName exists
        """
        for step in self._steps.values():
            if step.get_name() == stepName:
                return True
        return False

    def getVisitedSteps(self):
        """Returns a sequence of steps which has been visited.
        Visited means that the state of the step should be considered
        when finishing the wizard.
        @returns: sequence of visited steps.
        @rtype: sequence of L{WizardStep}
        """
        for step in self._steps.values():
            if step.visited:
                yield step

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
        self.prepareNextStep(self._currentStep)

    def blockNext(self, block):
        self.button_next.set_sensitive(not block)
        # work around a gtk+ bug #56070
        if not block:
            self.button_next.hide()
            self.button_next.show()

    def run(self, main=True):
        self._useMain = main
        sectionClass = self._sections[self._currentSection]
        if isinstance(sectionClass, (type, types.ClassType)):
            section = sectionClass(self)
        else:
            section = sectionClass
        self.sidebar.push(section.section, None, section.section)
        self._stack.push(section)
        self._setStep(section)

        self.window.present()
        self.window.grab_focus()

        if self._useMain:
            try:
                gtk.main()
            except KeyboardInterrupt:
                pass

    def prepareNextStep(self, step):
        if hasattr(step, 'lastStep'):
            self._finish(completed=True)
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

    # Private

    def _getNextStep(self):
        if self._currentSection + 1 == len(self._sections):
            self._finish(completed=True)
            return

        self._currentSection += 1
        nextStepClass = self._sections[self._currentSection]
        return nextStepClass(self)

    def _updateButtons(self, hasNext):
        # update the forward and next buttons
        # hasNext: whether or not there is a next step
        can_go_back = self._stack.pos != 0
        self.button_prev.set_sensitive(can_go_back)

        # XXX: Use the current step, not the one on the top of the stack
        if hasNext:
            self.button_next.set_label(gtk.STOCK_GO_FORWARD)
        else:
            self.button_next.set_label(_('_Finish'))

    def _setStepIcon(self, icon):
        icon_filename = os.path.join(configure.imagedir, 'wizard', icon)
        assert os.path.exists(icon_filename)
        self.image_icon.set_from_file(icon_filename)

    def _setStepTitle(self, title):
        self.label_title.set_markup(
            '<span size="x-large">%s</span>' % escape(title or ''))

    def _packStep(self, step):
        # Remove previous step
        map(self.content_area.remove, self.content_area.get_children())
        self.message_area.clear()

        # Add current
        self.content_area.pack_start(step, True, True, 0)

    def _finish(self, main=True, completed=True):
        if completed:
            self.completed()

        if self._useMain:
            try:
                gtk.main_quit()
            except RuntimeError:
                pass

    def _showNextStep(self, step):
        while not self._stack.push(step):
            s = self._stack.pop()
            s.visited = False
            self.sidebar.pop()

        hasNext = not hasattr(step, 'lastStep')
        if not step.visited and hasNext:
            self.sidebar.push(step.section, step.title,
                              step.sidebarName)
        else:
            self.sidebar.show_step(step.section)

        step.visited = True
        self._setStep(step)

        self._updateButtons(hasNext)

    def _setStep(self, step):
        self._steps[step.name] = step
        self._currentStep = step
        self._packStep(step)
        self._setStepIcon(step.icon)
        self._setStepTitle(step.title)

        self._updateButtons(hasNext=True)
        self.blockNext(False)

        self.beforeShowStep(step)

        self.debug('showing step %r' % step)
        step.show()
        step.activated()

    def _jumpToStep(self, name):
        step = self.getStep(name)
        # If we're jumping to the same step don't do anything to
        # avoid unnecessary ui flashes
        if step == self._currentStep:
            return
        self._stack.skipTo(lambda x: x.name == name)
        step = self._stack.current()
        self.sidebar.show_step(step.section)
        self._currentSection = self._getSectionByName(step.section)
        self._setStep(step)

    def _showPreviousStep(self):
        step = self._stack.back()
        self._currentSection = self._getSectionByName(step.section)
        self._setStep(step)
        self._updateButtons(hasNext=True)
        self.sidebar.show_step(step.section)
        hasNext = not hasattr(step, 'lastStep')
        self._updateButtons(hasNext)

    def _getSectionByName(self, section_name):
        for sectionClass in self._sections:
            if sectionClass.section == section_name:
                return self._sections.index(sectionClass)

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
        self._finish(self._useMain, completed=False)

    def on_button_prev_clicked(self, button):
        self._showPreviousStep()

    def on_button_next_clicked(self, button):
        self.goNext()

    def on_sidebar_step_chosen(self, sidebar, name):
        self._jumpToStep(name)


gobject.type_register(SectionWizard)
