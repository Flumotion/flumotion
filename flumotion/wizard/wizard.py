# -*- Mode: Python; test-case-name: flumotion.test.test_wizard -*-
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
from flumotion.common import log, errors, worker
from flumotion.wizard import enums, save
from flumotion.ui import fgtk
from flumotion.twisted import flavors

from flumotion.common.pygobject import gsignal

def escape(text):
    return text.replace('&', '&amp;')

class Stack(list):
    push = list.append
    def peek(self):
        return self[-1]
    

class WizardStep(object, log.Loggable):
    step_name = None # Subclass sets this
    glade_file = None # Subclass sets this
    icon = 'placeholder.png'
    has_worker = True
    widget_prefixes = { fgtk.FComboBox    : 'combobox',
                        fgtk.FCheckButton : 'checkbutton',
                        fgtk.FEntry       : 'entry',
                        fgtk.FSpinButton  : 'spinbutton',
                        fgtk.FRadioButton : 'radiobutton' }

    def __init__(self, wizard):
        self.wizard = wizard
        self.widget = None
        self.visited = False
        
        self.load_glade()

    def __repr__(self):
        return '<WizardStep object %s>' % self.step_name
    
    def load_glade(self):
        glade_filename = os.path.join(configure.gladedir, self.glade_file)
        
        self.wtree = gtk.glade.XML(glade_filename,
                                   typedict=fgtk.WidgetMapping())
        
        windows = []
        self.widgets = self.wtree.get_widget_prefix('')
        for widget in self.widgets:
            # So we can access the step from inside the widget
            widget.set_data('wizard-step', self)

            if isinstance(widget, gtk.Window):
                if widget.get_property('visible'):
                    raise AssertionError('window for %r is visible' % self)
                widget.hide()
                windows.append(widget)
                continue
            
            name = widget.get_name()
            if hasattr(self, name):
                raise AssertionError("There is already an attribute called %s in %r" % (name, self))
            
            setattr(self, name, widget)

        if len(windows) != 1:
            raise AssertionError("only one window per glade file allowed, got %r in %r" % (
                windows, self))

        self.window = windows[0]
        child = self.window.get_children()[0]
        self.window.remove(child)
        self.widget = child

        # And at last, connect signals.
        self.wtree.signal_autoconnect(self)
        
    def get_component_properties(self):
        return self.get_state()
    
    def get_main_widget(self):
        return self.widget

    # returns a new dict. is this necessary?
    def get_state(self):
        state_dict = {}
        for widget in self.widgets:
            name = widget.get_name()
            prefix = self.widget_prefixes.get(widget.__class__, None)
            if not prefix:
                continue
            try:
                key = name.split('_', 1)[1]
            except IndexError:
                continue
            
            # only fgtk widgets implement get_state
            state_dict[key] = widget.get_state()

        return state_dict

    def get_name(self):
        return self.step_name
    
    def get_sidebar_name(self):
        return getattr(self, 'sidebar_name', self.step_name)

    def get_section(self):
        return getattr(self, 'section', '')
        
    def workerRun(self, module, function, *args):
        """
        Run the given function and arguments on the selected worker.

        @returns: L{twisted.internet.defer.Deferred}
        """
        admin = self.wizard.get_admin()
        worker = self.worker
        
        if not admin:
            self.warning('skipping workerRun, no admin')
            return defer.fail(errors.FlumotionError('no admin'))

        if not worker:
            self.warning('skipping workerRun, no worker')
            return defer.fail(errors.FlumotionError('no worker'))

        return admin.workerRun(worker, module, function, *args)
        
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


    def before_show(self):
        """This is called just before we show the widget, everything
        is created and in place
        
        This can be implemented in a subclass."""

    def worker_changed(self):
        pass

class Wizard(gobject.GObject, log.Loggable):
    sidebar_bg = None
    sidebar_fg = None
    sidebar_fgi = None
    sidebar_pre_bg = None
    
    gsignal('finished', str)
    
    logCategory = 'wizard'

    __implements__ = flavors.IStateListener,

    def __init__(self, admin=None):
        self.__gobject_init__()
        self.wtree = gtk.glade.XML(os.path.join(configure.gladedir, 'wizard.glade'))
        for widget in self.wtree.get_widget_prefix(''):
            setattr(self, widget.get_name(), widget)
        self.wtree.signal_autoconnect(self)

        # have to get the style from the theme, but it's not really there until
        # it's attached
        self.label_title.realize()
        style = self.label_title.get_style()

        self.sidebar_bg = style.bg[gtk.STATE_SELECTED]
        self.sidebar_fg = style.fg[gtk.STATE_SELECTED]
        self.sidebar_fgi = style.light[gtk.STATE_SELECTED]
        self.sidebar_pre_bg = style.bg[gtk.STATE_ACTIVE]
        self.eventbox_top.modify_bg(gtk.STATE_NORMAL, self.sidebar_bg)
        self.label_title.modify_fg(gtk.STATE_NORMAL, self.sidebar_fg)
        self.window.set_icon_from_file(os.path.join(configure.imagedir,
                                                    'fluendo.png'))
        self._admin = admin
        self._save = save.WizardSaver(self)
        self._use_main = True
        self._workerHeavenState = None
        self.steps = []
        self.stack = Stack()
        self.current_step = None
        self._last_worker = 0 # combo id last worker from step to step
        self._worker_box = None # gtk.Widget containing worker combobox

    def __getitem__(self, stepname):
        for item in self.steps:
            if item.get_name() == stepname:
                return item
        else:
            raise KeyError

    def __len__(self):
        return len(self.steps)
            
    def error_dialog(self, message):
        """
        Show an error message dialog.
                                                                                
        @param message the message to display.
        @param parent the gtk.Window parent window.
        @param response whether the error dialog should go away after response.

        returns: the error dialog.
        """
        d = gtk.MessageDialog(self.window, gtk.DIALOG_MODAL,
                              gtk.MESSAGE_ERROR, gtk.BUTTONS_OK,
                              message)
        d.connect("response", lambda self, response: self.destroy())
        d.show_all()
        return d

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

    def add_step(self, step_class, initial=False):
        # If we don't have step_name set, count it as a base class
        name = step_class.step_name
        if name == None:
            return
        
        #if self.steps.has_key(name):
        #    raise TypeError("%s added twice" % name)

        # FIXME: document why steps need to ref their parent. otherwise
        # remove this
        step = step_class(self)
        self.steps.append(step)

        step.setup()

        if initial:
            self.stack.push(step)

    def set_step(self, step):
        # Remove previous step
        map(self.content_area.remove, self.content_area.get_children())

        # Add current
        widget = step.get_main_widget()
        self.content_area.pack_start(widget, True, True, 0)

        self._append_workers(step)
        icon_filename = os.path.join(configure.imagedir, 'wizard', step.icon)
        self.image_icon.set_from_file(icon_filename)
            
        self.label_title.set_markup('<span size="x-large">' + escape(step.get_name()) + '</span>')

        if self.current_step:
            self.current_step.deactivated()

        self.current_step = step
        
        self.update_sidebar(step)
        self.update_buttons(has_next=True)

        self._setup_worker(step)
        step.before_show()

        self.debug('showing step %r' % step)
        widget.show()
        step.activated()

    def _combobox_worker_changed(self, combobox, step):
        self._last_worker = combobox.get_active()
        self._setup_worker(step)
        step.worker_changed()
        
    def _append_workers(self, step):
        # called for each new page to put in the worker drop down box
        # if the step needs a worker
        if not step.has_worker:
            self.combobox_worker = None
            return
        
        # Horizontal, under step
        hbox = gtk.HBox()
        self.content_area.pack_end(hbox, False, False)
        hbox.set_border_width(6)
        hbox.show()
        
        frame = gtk.Frame('Worker')
        hbox.pack_end(frame, False, False, 0)
        frame.show()

        # Internal, so we can add border width
        box = gtk.HBox()
        frame.add(box)
        box.set_border_width(6)
        box.show()
        self.combobox_worker = gtk.combo_box_new_text()
        box.pack_start(self.combobox_worker, False, False, 6)
        self._rebuild_worker_combobox()
        self.combobox_worker.connect('changed',
                                     self._combobox_worker_changed, step)
        self.combobox_worker.show()

    def _rebuild_worker_combobox(self):
        model = self.combobox_worker.get_model()
        model.clear()

        # re-add all worker names
        names = self._workerHeavenState.get('names')
        for name in names:
            model.append((name,))
        self.combobox_worker.set_active(self._last_worker)
        
    def show_previous(self):
        step = self.stack.pop()

        self._setup_worker(step)

        prev_step = self.stack.peek()
        
        self.set_step(prev_step)
        self._set_worker_from_step(prev_step)

        self.update_buttons(has_next=True)

    def get_admin(self):
        return self._admin
    
    def check_elements(self, workerName, *elementNames):
        """
        Check if the given list of GStreamer elements exist on the given worker.

        @param workerName: name of the worker to check on
        @param elementNames: names of the elements to check
        """
        if not self._admin:
            self.debug('No admin connected, not checking presents of elements')
            return
        
        asked = sets.Set(elementNames)
        def _checkElementsCallback(existing, workerName):
            existing = sets.Set(existing)
            unexisting = asked.difference(existing)
            # if we're missing elements, we cannot unblock the next button
            if unexisting:
                self.warning('elements %s does not exist' % ', '.join(unexisting))
                message = "Worker %s is missing GStreamer elements '%s'.  " % (
                    workerName, "', '".join(unexisting)) \
                        + "You will not be able to go forward."
                # FIXME: parent
                self.error_dialog(message)
            else:
                self.block_next(False)
            return tuple(existing)
        
        self.block_next(True)
        d = self._admin.checkElements(workerName, elementNames)
        d.addCallback(_checkElementsCallback, workerName)
        return d

    def _setup_worker(self, step):
        # get name of active worker
        if self.combobox_worker:
            model = self.combobox_worker.get_model()
            iter = self.combobox_worker.get_active_iter()
            if iter:
                text = model.get(iter, 0)[0]
                self.debug('%r setting worker to %s' % (step, text))
                step.worker = text
                return

        self.debug('%r no worker set' % step)
            
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

    def show_next(self):
        next = self.current_step.get_next()
        if not next:
            self.finish(save=True)
            return

        self._setup_worker(self.current_step)

        try:
            next_step = self[next]
        except KeyError:
            raise TypeError("Wizard step %s is missing" % `next`)

        
        next_step.visited = True

        self.stack.push(next_step)
        self.set_step(next_step)

        has_next = not hasattr(next_step, 'last_step')
        self.update_buttons(has_next)

    def update_buttons(self, has_next):
        # update the forward and next buttons
        # has_next: whether or not there is a next step
        if len(self.stack) == 1:
            self.button_prev.set_sensitive(False)
        else:
            self.button_prev.set_sensitive(True)

        # XXX: Use the current step, not the one on the top of the stack
        if has_next:
            self.button_next.set_label(gtk.STOCK_GO_FORWARD)
        else:
            # use APPLY, just like in gnomemeeting
            self.button_next.set_label(gtk.STOCK_APPLY)

    def _sidebar_clean(self):
        # First remove the old the VBox if we can find one
        parent = self.vbox_sidebar.get_parent()
        if parent:
            parent.remove(self.vbox_sidebar)
        else:
            parent = self.eventbox_sidebar

        parent.modify_bg(gtk.STATE_NORMAL, self.sidebar_bg)
        self.vbox_sidebar = gtk.VBox()
        self.vbox_sidebar.set_border_width(5)
        parent.add(self.vbox_sidebar)

    def _sidebar_add_placeholder(self):
        # Placeholder label, which expands vertically
        ph = gtk.Label()
        ph.show()
        self.vbox_sidebar.pack_start(ph)
        
    # FIXME: use theme-sensitive colors instead of hardcoding
    def _sidebar_add_step(self, step, name, active, padding):
        hbox = gtk.HBox(0, False)
        hbox.show()

        text = escape(name)
        button = gtk.Button('')
        button.modify_bg(gtk.STATE_PRELIGHT, self.sidebar_pre_bg)
        button.modify_bg(gtk.STATE_ACTIVE, self.sidebar_pre_bg)

        # CZECH THIS SHIT. You *can* set the fg/text on a label, but it
        # will still emboss the color in the INSENSITIVE state. The way
        # to avoid embossing is to use pango attributes (e.g. via
        # <span>), but then in INSENSITIVE you get stipple. Where is
        # this documented? Grumble.
        label = button.get_children()[0]
        label.modify_fg(gtk.STATE_NORMAL, self.sidebar_fg)
        # label.modify_fg(gtk.STATE_INSENSITIVE, gtk.gdk.color_parse('red'))
        button.modify_bg(gtk.STATE_NORMAL, self.sidebar_bg)
        button.modify_bg(gtk.STATE_INSENSITIVE, self.sidebar_bg)
        label.set_padding(padding, 0)
        label.set_alignment(0, 0.5)
        button.set_relief(gtk.RELIEF_NONE)
        hbox.pack_start(button, True, True)
        self.vbox_sidebar.pack_start(hbox, False, False)

        if not step:
            steps = [step for step in self.steps
                              if getattr(step, 'section_name', '') == name]
            assert len(steps) == 1
            step = steps[0]

        def button_clicked_cb(button, step):
            self.set_step(step)
            
        if step:
            button.connect('clicked', button_clicked_cb, step)
        else:
            button.connect('clicked', button_clicked_cb, steps[0])
            
        current = self.current_step

        # We want to mark what the current step is, but I don't think
        # that using sensitivity is a good idea, because your text will
        # either be embossed or stippled by pango.
        #if current == step:
        #    button.set_sensitive(False)
            
        def pc(c):
            return '#%02x%02x%02x' % (c.red>>8, c.green>>8, c.blue>>8)

        if active or step.visited:
            button.set_property('can_focus', False)
            s = '<small>%s</small>' % name
        else:
            button.set_sensitive(False)
            s = ('<small><span foreground="%s">%s</span></small>'
                 % (pc(self.sidebar_fgi), name))
            
        label.set_markup(s)

        button.show()
        return button
    
    def _sidebar_add_substeps(self, section):
        filtered_steps = [step for step in self.steps
                                   if (step.get_section() == section and
                                       step.visited == True and
                                       not hasattr(step, 'section_name'))]
        for step in filtered_steps:
            label = step.get_sidebar_name()
            self._sidebar_add_step(step, label, True, 20)

    def update_sidebar(self, step):
        current = step.get_section()

        self._sidebar_clean()
        
        sidebar_steps = ('Welcome',
                         'Production', 'Conversion',
                         'Consumption', 'License')
        active = True
        for stepname in sidebar_steps:
            self._sidebar_add_step(None, stepname, active, 10)

            if current == stepname:
                self._sidebar_add_substeps(stepname)
                self._sidebar_add_placeholder()
                active = False
            else:
                continue
            
        self.vbox_sidebar.show()
        
    def on_wizard_delete_event(self, wizard, event):
        self.finish(self._use_main, save=False)

    def on_button_prev_clicked(self, button):
        self.show_previous()

    def on_button_next_clicked(self, button):
        self.show_next()

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
        self._use_main = main
        workerHeavenState.addListener(self)
        
        if not self.stack:
            raise TypeError("need an initial step")

        self.set_step(self.stack.peek())
        
        if not interactive:
            while self.current_step.get_next():
                self.show_next()
                
            return self.finish(False)

        self.window.present()
        self.window.grab_focus()
        if not self._use_main:
            return
        
        try:
            gtk.main()
        except KeyboardInterrupt:
            pass

    ### IStateListener methods
    def stateAppend(self, state, key, value):
        if not isinstance(state, worker.AdminWorkerHeavenState):
            return
        self.info('worker %s logged in to manager' % value)
        #FIXME: make this work correctly
        #self._rebuild_worker_combobox()
        
    def stateRemove(self, state, key, value):
        if not isinstance(state, worker.AdminWorkerHeavenState):
            return
        self.info('worker %s logged out of manager' % value)
        #FIXME: make this work correctly
        #self._rebuild_worker_combobox()

    def load_steps(self):
        global _steps
        import flumotion.wizard.steps
        
        self.add_step(_steps[0], initial=True)
        
        for step_class in _steps[1:]:
            self.add_step(step_class)
            
    def printOut(self):
        print self._save.getXML()[:-1]

    def getConfig(self):
        dict = {}
        for component in self._save.getComponents():
            dict[component.name] = component

        return dict
gobject.type_register(Wizard)

_steps = []

        
def register_step(klass):
    global _steps

    _steps.append(klass)

def get_steps():
    global _steps
    return _steps
