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


import gtk

from twisted.internet import defer

from flumotion.common import log, errors
from flumotion.ui import fgtk
from flumotion.ui.glade import GladeWidget


class WizardStep(GladeWidget, log.Loggable):
    glade_typedict = fgtk.WidgetMapping()

    # set by subclasses
    name = None
    section = None
    icon = 'placeholder.png'

    # optional
    sidebar_name = None
    has_worker = True

    # set by Wizard when going through steps
    visited = False
    worker = None

    def __init__(self, wizard):
        """
        @param wizard: the wizard this step is a part of
        @type  wizard: L{Wizard}
        """
        GladeWidget.__init__(self)
        self.set_name(self.name)
        if not self.sidebar_name:
            self.sidebar_name = self.name
        self.wizard = wizard
        self.setup()

    def __repr__(self):
        return '<WizardStep object %s>' % self.name
    
    def get_component_properties(self):
        return self.get_state()
    
    def iterate_widgets(self):
        # depth-first
        def iterator(w):
            if isinstance(w, gtk.Container):
                for c in w.get_children():
                    for cc in iterator(c):
                        yield cc
            yield w
        return iterator(self)

    # returns a new dict. is this necessary?
    def get_state(self):
        state_dict = {}
        for w in self.iterate_widgets():
            if hasattr(w, 'get_state') and w != self:
                # only fgtk widgets implement get_state
                key = w.get_name().split('_', 1)[1]
                state_dict[key] = w.get_state()

        return state_dict

    def info_msg(self, *args, **kwargs):
        self.wizard.info_msg(*args, **kwargs)

    def error_msg(self, *args, **kwargs):
        self.wizard.error_msg(*args, **kwargs)

    def clear_msg(self, *args, **kwargs):
        self.wizard.clear_msg(*args, **kwargs)

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

        d = admin.workerRun(worker, module, function, *args)
        # FIXME: add errback
        return d
        
    # Required vmethods
    def get_next(self):
        """
        @returns name of next step
        @rtype   string

        Called when the user presses next in the wizard."""
        
        raise NotImplementedError

    # Optional vmethods
    def activated(self):
        """Called just before the step is shown, so the step can
        do some logic, eg setup the default state"""
        
    def deactivated(self):
        """Called after the user pressed next"""

    def setup(self):
        """This is called after the step is constructed, to be able to
        do some initalization time logic in the steps."""

    def before_show(self):
        """This is called just before we show the widget, everything
        is created and in place"""

    def worker_changed(self):
        pass

class WizardSection(WizardStep):
    def __init__(self, *args):
        if not self.name:
            self.name = self.section
        WizardStep.__init__(self, *args)

    def __repr__(self):
        return '<WizardSection object %s>' % self.name
