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

import os
import gtk

from flumotion.common import errors

from flumotion.component.base.admin_gtk import BaseAdminGtk
from flumotion.component.base.baseadminnode import BaseAdminGtkNode

__version__ = "$Rev$"


class SwitchingNode(BaseAdminGtkNode):

    def __init__(self, state, admin, title=None):
        BaseAdminGtkNode.__init__(self, state, admin, title)
        # create widget
        self.widget = gtk.Table(2, 1)
        self.radioButton = {}
        self.radioButton["backup"] = gtk.RadioButton(label="Backup")
        self.radioButton["master"] = gtk.RadioButton(
            self.radioButton["backup"],
            label="Master")
        self.radioButtonHandlers = {}
        currentRow = 0
        for eaterName in self.radioButton:
            self.widget.attach(self.radioButton[eaterName], 0, 1, currentRow,
                currentRow+1, yoptions=gtk.FILL, xpadding=6, ypadding=6)
            currentRow = currentRow + 1
            self.radioButton[eaterName].show()
            sigID = self.radioButton[eaterName].connect(
                "toggled", self.cb_toggled, eaterName)
            self.radioButtonHandlers[eaterName] = sigID
        self.widget.show()

    def cb_toggled(self, button, eaterName):
        if button.get_active():
            if eaterName == "master":
                self.callRemote("switchToMaster")
            else:
                self.callRemote("switchToBackup")

    def setUIState(self, state):
        BaseAdminGtkNode.setUIState(self, state)
        self.stateSet(state, 'active-eater', state.get('active-eater'))

    def stateSet(self, state, key, value):
        if key == 'active-eater':
            if not self.radioButton[value].get_active():
                self.radioButton[value].handler_block(
                    self.radioButtonHandlers[value])
                self.radioButton[value].set_active(True)
                self.radioButton[value].handler_unblock(
                    self.radioButtonHandlers[value])


class SwitcherAdminGtk(BaseAdminGtk):

    def setup(self):
        swNode = SwitchingNode(self.state, self.admin, "Switching")
        self.nodes['Switcher'] = swNode
        return BaseAdminGtk.setup(self)

GUIClass = SwitcherAdminGtk
