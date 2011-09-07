# -*- Mode: Python -*-
# vi:si:et:sw=4:sts=4:ts=4

# Flumotion - a streaming media server
# Copyright (C) 2004,2005,2006,2007,2008,2009 Fluendo, S.L.
# Copyright (C) 2010,2011 Flumotion Services, S.A.
# All rights reserved.
#
# This file may be distributed and/or modified under the terms of
# the GNU Lesser General Public License version 2.1 as published by
# the Free Software Foundation.
# This file is distributed without any warranty; without even the implied
# warranty of merchantability or fitness for a particular purpose.
# See "LICENSE.LGPL" in the source distribution for more information.
#
# Headers in this file shall remain intact.

import os

# import custom glade handler
from flumotion.ui import glade
from flumotion.component.base.effectsnode import EffectAdminGtkNode

__version__ = "$Rev$"


class AudioresyncAdminGtkNode(EffectAdminGtkNode):
    logCategory = 'audioresync-delay'
    gladeFile = os.path.join('flumotion', 'component', 'effects',
                              'audioresync', 'audioresync.glade')

    uiStateHandlers = None

    def haveWidgetTree(self):
        self.widget = self.wtree.get_widget('audioresync-widget')
        self._resync_spinbutton = \
            self.wtree.get_widget('delay-spinbutton')

        # do the callbacks for the mode setting
        self._resync_spinbutton.connect('value-changed', self._cb_delay_set)

    def setUIState(self, state):
        EffectAdminGtkNode.setUIState(self, state)
        if not self.uiStateHandlers:
            self.uiStateHandlers = {'audioresync-delay': self.delaySet}
        for k, handler in self.uiStateHandlers.items():
            handler(state.get(k))

    def stateSet(self, state, key, value):
        handler = self.uiStateHandlers.get(key, None)
        if handler:
            handler(value)

    def delaySet(self, diff):
        self._resync_spinbutton.set_value(diff)

    def setResyncErrback(self, failure):
        self.warning("Failure %s setting mode: %s" % (
            failure.type, failure.getErrorMessage()))
        return None

    def _cb_delay_set(self, widget):
        diff = widget.get_value()
        d = self.effectCallRemote("setDelay", diff)
        d.addErrback(self.setResyncErrback)
