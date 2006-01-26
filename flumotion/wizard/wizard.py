# -*- Mode: Python; test-case-name: flumotion.test.test_wizard -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# Flumotion - a streaming media server
# Copyright (C) 2004,2005,2006 Fluendo, S.L. (www.fluendo.com).
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
import sets

import gobject
import gtk
import gtk.gdk
import gtk.glade

from twisted.internet import defer

from flumotion.configure import configure
from flumotion.common import log, errors, worker, compat, messages

from flumotion.wizard import enums, save, step, classes
#from flumotion.wizard.sidebar import WizardSidebar
from flumotion.ui import fgtk
from flumotion.ui.glade import GladeWindow
from flumotion.twisted import flavors

from flumotion.common.pygobject import gsignal


# pychecker doesn't like the auto-generated widget attrs
# or the extra args we name in callbacks
__pychecker__ = 'no-classattr no-argsused'

def escape(text):
    return text.replace('&', '&amp;')

class Sections(classes.KeyedList):
    def __init__(self, *args):
        classes.KeyedList.__init__(self, *args)
        self.add_key(str, lambda x: x.section)

class Scenario:
    # to be provided by subclasses
    sections = None

    def __init__(self, wizard):
        self.wizard = wizard # remove?
        self.sidebar = wizard.sidebar
        assert self.sections
        self.sidebar.set_sections([(x.section, x.name) for x in self.sections])
        self.current_section = 0
        self.steps = list(self.sections)
        self.stack = classes.WalkableStack()
        self.current_step = None
        self.sidebar.connect('step-chosen', self.step_selected)
    
    def add_step(self, step_class):
        # FIXME: remove ref to wiz
        self.steps.append(step_class(self.wizard))

    def step_selected(self, sidebar, name):
        self.stack.skip_to(lambda x: x.name == name)
        step = self.stack.current()
        self.current_step = step
        self.sidebar.show_step(step.section, step.name)
        self.current_section = self.sections.index(self.sections[step.section])
        self.wizard.set_step(step)

    def show_previous(self):
        step = self.stack.back()
        self.current_section = self.sections.index(self.sections[step.section])
        self.wizard.set_step(step)
        self.current_step = step
        #self._set_worker_from_step(prev_step)
        self.wizard.update_buttons(has_next=True)
        self.sidebar.show_step(step.section, step.name)
        has_next = not hasattr(step, 'last_step')
        self.wizard.update_buttons(has_next)

    def show_next(self):
        self.wizard._setup_worker(self.current_step,
                                  self.wizard.worker_list.get_worker())
        next = self.current_step.get_next()
        if not next:
            if self.current_section + 1 == len(self.sections):
                self.wizard.finish(save=True)
                return
            self.current_section += 1
            next_step = self.sections[self.current_section]
        else:
            try:
                next_step = self.wizard[next]
            except KeyError:
                raise TypeError("%r: Wizard step %s is missing" % (
                    self, next))

        while not self.stack.push(next_step):
            s = self.stack.pop()
            s.visited = False
            self.sidebar.pop()

        if not next_step.visited:
            self.sidebar.push(next_step.section, next_step.name,
                              next_step.sidebar_name)
        else:
            self.sidebar.show_step(next_step.section, next_step.name)
        next_step.visited = True
        self.wizard.set_step(next_step)
        self.current_step = next_step

        has_next = not hasattr(next_step, 'last_step')
        self.wizard.update_buttons(has_next)

    def run(self, interactive):
        section = self.sections[self.current_section]
        self.sidebar.push(section.section, None, section.section)
        self.stack.push(section)
        self.wizard.set_step(section)
        self.current_step = section
        
        if not interactive:
            while self.show_next():
                pass
            return self.wizard.finish(False)

        self.wizard.window.present()
        self.wizard.window.grab_focus()
        if not self.wizard._use_main:
            return
        
        try:
            gtk.main()
        except KeyboardInterrupt:
            pass

class BasicScenario(Scenario):
    def __init__(self, wizard):
        from flumotion.wizard import steps
        self.sections = Sections()
        for klass in (steps.Welcome, steps.Production, steps.Conversion,
                      steps.Consumption, steps.License, steps.Summary):
            self.sections.append(klass(wizard))

        Scenario.__init__(self, wizard)

        for k in dir(steps):
            v = getattr(steps, k)
            try:
                if issubclass(v, step.WizardSection):
                    pass
                elif issubclass(v, step.WizardStep) and v.name:
                    self.add_step(v)
            except TypeError:
                pass

class Wizard(GladeWindow, log.Loggable):
    gsignal('finished', str)
    gsignal('destroy')
    
    logCategory = 'wizard'

    flowName = 'default'

    glade_file = 'wizard.glade'

    def __init__(self, parent_window=None, admin=None):
        GladeWindow.__init__(self, parent_window)
        for k, v in self.widgets.items():
            setattr(self, k, v)

        self.scenario = BasicScenario(self)

        self.window.set_icon_from_file(os.path.join(configure.imagedir,
                                                    'fluendo.png'))
        self._admin = admin
        self._save = save.WizardSaver(self)
        self._use_main = True
        self.current_step = None
        self._workerHeavenState = None
        self._last_worker = 0 # combo id last worker from step to step
        self.worker_list.connect('worker-selected',
                                 self._combobox_worker_changed)

        self.window.connect_after('realize', self.on_realize)
        self.window.connect('destroy', lambda *x: self.emit('destroy'))

    def on_realize(self, window):
        # have to get the style from the theme, but it's not really
        # there until it's attached
        style = self.window.get_style()
        bg = style.bg[gtk.STATE_SELECTED]
        fg = style.fg[gtk.STATE_SELECTED]
        self.eventbox_top.modify_bg(gtk.STATE_NORMAL, bg)
        self.hbuttonbox2.modify_bg(gtk.STATE_NORMAL, bg)
        self.label_title.modify_fg(gtk.STATE_NORMAL, fg)

    def present(self):
        self.window.present()

    def destroy(self):
        GladeWindow.destroy(self)
        del self._admin
        del self._save

    def __getitem__(self, stepname):
        for item in self.scenario.steps:
            if item.get_name() == stepname:
                return item
        else:
            raise KeyError

    def __len__(self):
        return len(self.scenario.steps)

    def info_msg(self, id, text):
        m = messages.Info(priority=50, id=id, text=text)
        self.message_area.add_message(m)

    def error_msg(self, id, text):
        m = messages.Error(priority=60, id=id, text=text)
        self.message_area.add_message(m)

    def clear_msg(self, id):
        self.message_area.clear_message(id)

    def get_step_option(self, stepname, option):
        state = self.get_step_options(stepname)
        return state[option]

    def get_step_options(self, stepname):
        step = self[stepname]
        return step.get_state()
    
    def block_next(self, block):
        self.button_next.set_sensitive(not block)

    def block_prev(self, block):
        self.button_prev.set_sensitive(not block)

    def set_step(self, step):
        # Remove previous step
        map(self.content_area.remove, self.content_area.get_children())
        self.message_area.clear()

        # Add current
        self.content_area.pack_start(step, True, True, 0)

        icon_filename = os.path.join(configure.imagedir, 'wizard', step.icon)
        self.image_icon.set_from_file(icon_filename)
            
        m = '<span size="x-large">%s</span>' % escape(step.name)
        self.label_title.set_markup(m)

        if self.current_step:
            self.current_step.deactivated()

        self.current_step = step
        
        self.update_buttons(has_next=True)
        self.block_next(False)

        if step.has_worker:
            self.worker_list.show()
            self.worker_list.notify_selected()
        else:
            self.worker_list.hide()
        
        self._setup_worker(step, self.worker_list.get_worker())
        step.before_show()

        self.debug('showing step %r' % step)
        step.show()
        step.activated()

    def _combobox_worker_changed(self, combobox, worker):
        if worker:
            self.clear_msg('worker-error')
            self._last_worker = worker
            if self.current_step:
                self._setup_worker(self.current_step, worker)
                self.current_step.worker_changed()
        else:
            self.error_msg('worker-error',
                           'All workers have logged out.\n'
                           'Make sure the flumotion server is running '
                           'properly and try again.')
        
    def get_admin(self):
        return self._admin
    
    def check_elements(self, workerName, *elementNames):
        """
        Check if the given list of GStreamer elements exist on the given worker.

        @param workerName: name of the worker to check on
        @param elementNames: names of the elements to check

        @returns: a deferred returning a tuple of the missing elements
        """
        if not self._admin:
            self.debug('No admin connected, not checking presence of elements')
            return
        
        asked = sets.Set(elementNames)
        def _checkElementsCallback(existing, workerName):
            existing = sets.Set(existing)
            self.block_next(False)
            return tuple(asked.difference(existing))
        
        self.block_next(True)
        d = self._admin.checkElements(workerName, elementNames)
        d.addCallback(_checkElementsCallback, workerName)
        return d

    def require_elements(self, workerName, *elementNames):
        """
        Require that the given list of GStreamer elements exists on the
        given worker. If the elements do not exist, an error message is
        posted and the next button remains blocked.

        @param workerName: name of the worker to check on
        @param elementNames: names of the elements to check
        """
        if not self._admin:
            self.debug('No admin connected, not checking presence of elements')
            return
        
        self.debug('requiring elements %r' % (elementNames,))
        def got_missing_elements(elements, workerName):
            if elements:
                self.warning('elements %r do not exist' % (elements,))
                message = "Worker %s is missing GStreamer elements '%s'.  " % (
                    workerName, "', '".join(elements)) \
                        + "You will not be able to go forward."
                self.block_next(True)
                self.error_msg('-'.join(elementNames), message)
        
        d = self.check_elements(workerName, *elementNames)
        d.addCallback(got_missing_elements, workerName)

    def _setup_worker(self, step, worker):
        # get name of active worker
        self.debug('%r setting worker to %s' % (step, worker))
        step.worker = worker
            
    def _set_worker_from_step(self, step):
        if not hasattr(step, 'worker'):
            return

        model = self.combobox_worker.get_model()
        current_text = step.worker
        for row in model:
            text = model.get(row.iter, 0)[0]
            if current_text == text:
                self.combobox_worker.set_active_iter(row.iter)
                break

    def update_buttons(self, has_next):
        # update the forward and next buttons
        # has_next: whether or not there is a next step
        if self.scenario.stack.pos == 0:
            self.button_prev.set_sensitive(False)
        else:
            self.button_prev.set_sensitive(True)

        # XXX: Use the current step, not the one on the top of the stack
        if has_next:
            self.button_next.set_label(gtk.STOCK_GO_FORWARD)
        else:
            # use APPLY, just like in gnomemeeting
            self.button_next.set_label(gtk.STOCK_APPLY)

    def on_wizard_delete_event(self, wizard, event):
        self.finish(self._use_main, save=False)

    def on_button_prev_clicked(self, button):
        self.scenario.show_previous()

    def on_button_next_clicked(self, button):
        self.scenario.show_next()

    def finish(self, main=True, save=True):
        if save:
            configuration = self._save.getXML()
            self.emit('finished', configuration)
        
        if self._use_main:
            try:
                gtk.main_quit()
            except RuntimeError:
                pass

    def hide(self):
        self.window.hide()

    def run(self, interactive, workerHeavenState, main=True):
        self._workerHeavenState = workerHeavenState
        self.worker_list.set_worker_heaven_state(self._workerHeavenState)
        self._use_main = main
        self.scenario.run(interactive)

    def printOut(self):
        print self._save.getXML()[:-1]

    def getConfig(self):
        dict = {}
        for component in self._save.getComponents():
            dict[component.name] = component

        return dict
compat.type_register(Wizard)
