# -*- Mode: Python; test-case-name: flumotion.test.test_feedcomponent010 -*-
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
import gtk
import locale
import os

from flumotion.common import log
from flumotion.common import format as formatting

from flumotion.common.errors import SleepingComponentError
from flumotion.common.i18n import getLL, gettexter
from flumotion.common.planet import moods

_ = gettext.gettext
__version__ = "$Rev$"
T_ = gettexter()

# stupid pychecker
dir(locale)


class ComponentOverview(gtk.Expander, log.Loggable):

    def __init__(self, label):
        self.total_mem = 0.0
        self.num_cpus = 1
        gtk.Expander.__init__(self, '<b>%s</b>'%label)
        self.set_use_markup(True)
        table = gtk.Table(2, 2)
        cpu_label = gtk.Label('cpu')
        cpu_label.set_alignment(0, 1)
        mem_label = gtk.Label('mem')
        mem_label.set_alignment(0, 1)
        table.attach(cpu_label, 0, 1, 0, 1, gtk.FILL, 0, 2, 2)
        table.attach(mem_label, 0, 1, 1, 2, gtk.FILL, 0, 2, 2)
        self.cpu = gtk.ProgressBar()
        self.cpu.set_text(_('Unknown'))
        table.attach(self.cpu, 1, 2, 0, 1, gtk.EXPAND|gtk.FILL,
                     gtk.EXPAND|gtk.FILL, 2, 2)
        self.mem = gtk.ProgressBar()
        self.mem.set_text(_('Unknown'))
        table.attach(self.mem, 1, 2, 1, 2, gtk.EXPAND|gtk.FILL,
                     gtk.EXPAND|gtk.FILL, 2, 2)
        self.add(table)
        self.set_expanded(True)

    def update_cpu(self, fraction):
        if not fraction:
            fraction = 0
        self.cpu.set_fraction(fraction/self.num_cpus)
        self.cpu.set_text('%.2f %%'%(fraction * 100))

    def update_mem(self, size):
        if not size:
            size = _('Unknown')
            fraction = 0
        else:
            fraction = size / self.total_mem
            size = '%sB' % formatting.formatStorage(size)

        self.mem.set_text(size)
        self.mem.set_fraction(fraction)

    def set_total_memory(self, total_mem):
        self.total_mem = float(total_mem)

    def set_num_cpus(self, num):
        self.num_cpus = num


class MultipleComponentsAdminGtk(log.Loggable):
    """
    I am a view of multiple components' properties.
    """

    logCategory = "admingtk"
    gettextDomain = None

    def __init__(self, multistate, admin):
        """
        @type  multistate: {f.a.g.c.MultipleAdminComponentStates}
        @param multistate: state of component this is a UI for
        @type  admin: L{flumotion.admin.admin.AdminModel}
        @param admin: the admin model that interfaces with the manager for us
        """
        self.widget = gtk.ScrolledWindow()
        self.widget.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        self.widget.set_border_width(0)
        self.widget.set_shadow_type(gtk.SHADOW_NONE)
        vbox = gtk.VBox(spacing=6)
        vbox.set_border_width(12)
        self._debugEnabled = False
        self.multistate = multistate
        self.name = 'multiple_components'
        self.admin = admin
        self.debug('creating admin gtk for state %r' % multistate)
        self.uiStates = []
        self._stateValues = dict()

        for state in multistate.getComponentStates():
            co = ComponentOverview(state.get('name'))
            vbox.pack_start(co, False, True)
            vbox.pack_start(gtk.HSeparator(), False, True)
            if state.get('mood') in [moods.lost.value,
                                     moods.sleeping.value,
                                     moods.sad.value]:
                co.set_expanded(False)
                continue
            d = admin.componentCallRemote(state, 'getUIState')
            d.addCallback(self.setUIState, co)
            d.addErrback(lambda failure: failure.trap(SleepingComponentError))

        self.widget.add_with_viewport(vbox)
        vbox.show_all()

    def cleanup(self):
        for uiState in self.uiStates:
            uiState.removeListener(self)

    def setUIState(self, state, widget):
        self.debug('starting listening to state %r', state)
        state.addListener(self, set_=self.stateSet)
        self.uiStates.append(state)
        self._stateValues[state] = widget
        widget.set_total_memory(state.get('total-memory', 0))
        widget.set_num_cpus(state.get('num-cpus', 1))
        for key in state.keys():
            val = state.get(key)
            if val is not None:
                self.stateSet(state, key, state.get(key))

    def callRemote(self, methodName, *args, **kwargs):
        return self.admin.componentCallRemote(self.state, methodName,
                                              *args, **kwargs)

    def getWidget(self):
        return self.widget

    def stateSet(self, object, key, value):
        if key == 'cpu-percent':
            self._stateValues[object].update_cpu(value)
        elif key == 'virtual-size':
            self._stateValues[object].update_mem(value)
