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

import gobject
import gtk

from flumotion.common import log
from flumotion.ui.fgtk import ProxyWidgetMapping
from flumotion.ui.glade import GladeWidget

__version__ = "$Rev$"


class WizardPlugLine(GladeWidget, log.Loggable):
    """
    """

    logCategory = 'wizard'
    gladeTypedict = ProxyWidgetMapping()

    def __init__(self, wizard, model, description):
        if self.gladeFile:
            GladeWidget.__init__(self)
        else:
            gtk.VBox.__init__(self)
        self.checkbutton = gtk.CheckButton()

        label = gtk.Label(description)
        label.set_use_underline(True)

        self.checkbutton.add(label)
        self.pack_start(self.checkbutton)
        self.checkbutton.connect('toggled',
                                 self.on_checkbutton_toggled)

        self.reorder_child(self.checkbutton, 0)
        self.checkbutton.show_all()

        self.wizard = wizard
        self.model = model

    # Public API

    def setActive(self, active):
        self.checkbutton.set_active(active)

    def getActive(self):
        """Aks wether the plug line is active or not.
        """
        return self.checkbutton.get_active()

    def plugActiveChanged(self, active):
        """Called when the checkbutton state changes.
        Has to be overwritten by subclasses as for beeing aware of when the
        state changes.
        """
        raise NotImplementedError()

    # Callbacks

    def on_checkbutton_toggled(self, cb):
        self.plugActiveChanged(cb.get_active())

gobject.type_register(WizardPlugLine)


class WizardPlugArea(gtk.VBox):
    """I am plugin area representing all available plugins. I keep track
    of the plugins and their internal state. You can ask me to add new plugins
    or get the internal models of the plugins.
    """

    def __init__(self):
        gtk.VBox.__init__(self, spacing=6)
        self._lines = []

    # Public

    def addLine(self, line):
        self._lines.append(line)
        self.pack_start(line, False, False)
        line.show()

    def clean(self):
        self.foreach(self.remove)
        self._lines = []

    def getEnabledLines(self):
        for line in self._lines:
            if line.getActive():
                yield line
